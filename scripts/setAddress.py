from getpass import getpass
from pathlib import Path
from ethereum import utils
from datetime import datetime
from collections import OrderedDict
import re, os, requests,json
import argparse

SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))

actualRegistryAddress = "(Actual RegistryAdress: None)"
actualPairFilters = "(Actual PairFilters: None)"
actualAddress = "(Actual Adress: None)"
actualNode = "(Actual Node: None)"
actualPort = "(Actual Port: None)"

def get_parser():
    ap = argparse.ArgumentParser()
    ap.add_argument("-e","--env",required=False,help="Env file to check variables")
    args = vars(ap.parse_args())
    return args

class Account(object):
    address = ""
    privateKey = ""
    """Generete a privateKey/Account using  2 random numbers + date + an input words"""

    def __init__(self, word):
        super(Account, self).__init__()
        if (word != ""):
            now = datetime.now()
            randomFromWeb = requests.get('https://www.random.org/integers/?num=1&min=1&max=4096&col=1&base=10&format=plain&rnd=new').text
            seed_str =  (randomFromWeb 
                         + str(os.urandom(4096))
                         + now.strftime("%d/%m/%Y %H:%M:%S")
                         + word)
            privKey_Raw = utils.sha3(seed_str)
            self.address = utils.checksum_encode(utils.privtoaddr(privKey_Raw))
            self.privateKey = utils.encode_hex(privKey_Raw)

    def setAddress(self,_address):
        self.address=_address

    def setPrivateKey(self,_privateKey):
        self.privateKey=_privateKey

    """ Generate an interface to get user's address and return an instance of Account"""
    @staticmethod
    def getAccount(_purpose):
        answer =""
        while (answer not in ("1","2")):
            print("Do you have a privateKey and Address, or you want to generate the pair?")
            print("1. I have a PrivateKey and Address")
            print("2. I want to generate the pair")
            answer = input()
            if (answer == "1"):
                account = Account("")
                print("Enter the address of the " + _purpose +" wallet in RSK")
                account.setAddress(input("Adress:")) 
                print("Enter the private password that correspond to the address you just entered")
                account.setPrivateKey(getpass("PrivateKey:"))
            elif(answer == "2" ):
                words =""
                while len(words.split()) < 2:
                    print("Enter 2 or more words separated by spaces.")
                    print("We will use them as part of the seed used for generate a random privateKey")
                    words = input()
                account = Account(words)
                print("Your new address is: " + account.address)
        return (account)

def writeToEnv(filePath,line):
    f = open(filePath,"a")
    f.write(line)
    f.close()

def addToEnv(filePath, search, addText):
    file = Path(filePath)
    content = re.sub(r'\n' + re.escape(search) + r'.*'
                    ,'\n' + search + addText,
                    file.read_text())                    
    file.open('w').write(content)

def oracleOption(env_file):
    global actualAddress
    oracle = Account.getAccount("oracle")
    if actualAddress == "(Actual Adress: None)":
        writeToEnv(env_file,"\nORACLE_ADDR=\n")
        writeToEnv(env_file,"\nORACLE_PRIVATE_KEY=\n")

    priv_key = oracle.privateKey
    addToEnv(env_file,"ORACLE_PRIVATE_KEY=", oracle.privateKey)
    addToEnv(env_file,"ORACLE_ADDR=",oracle.address)
    actualAddress = f"(Actual Adress: {oracle.address})"

def NodeOption(network,env_file):
    global actualNode
    print("///////////")
    print("Now we will setup your RSK Node.")
    print("Enter your RSK Node address in the form of 'http://<<IP>>:<<PORT>>'")
    print("or press enter if you want to connect to the public node.")
    print("The default public node matchs the network selected previosuly.")
    print("///////////")
    node = input("Node (default: public-node):")
    if actualNode == "(Actual Node: None)":
        writeToEnv(env_file,"\nNODE_URL=\n")

    addToEnv(env_file,"NODE_URL=",node)
    actualNode = f"(Actual Node: {node})"

def PortOption(env_file):
    global actualPort
    print("///////////")
    print("Now we will setup the Oracle Port.")
    print("The default oracle port is 5556.")
    print("///////////")
    port = input("Oracle Port (default: 5556): ")
    if port == "":
        port = 5556
    if actualPort == "(Actual Port: None)":
        writeToEnv(env_file,"\nORACLE_PORT=\n")

    addToEnv(env_file,"ORACLE_PORT=",port)
    actualPort = f"(Actual Port: {port})"

def RegistryAddress(network,env_file):
    global actualRegistryAddress
    print("///////////")
    print("Now we will setup the Registry Address.")
    print("The default registry address matchs the network selected previosuly.")
    print("///////////")
    registry_address = input("Registry address:")
    addToEnv(env_file,'REGISTRY_ADDR=', registry_address)
    actualRegistryAddress = f"(Actual RegistryAdress: {registry_address} )"

def PairFilters(env_file):
    global actualPairFilters
    print("///////////")
    print("Now we will setup the Oracle pair filters.")
    print("By default, BTCUSD is choose.")
    print("///////////")
    pairs = []
    quit = False
    while (quit == False):
        pair = input("Select pair filter. Press ENTER for skip. (Default BTCUSD): ")
        if pair == '':
            if len(pairs) == 0 : pairs.append('BTCUSD') 
            quit = True
        else:
            pairs.append(pair)
    pairString = ''
    current_index = 0
    for current_pair in pairs:
        if current_index != 0:
            pairString += ','
        pairString += '"' + current_pair.upper() + '"'
        current_index += 1
    if actualPairFilters == "(Actual PairFilters: None)":
        writeToEnv(env_file,"\nORACLE_COIN_PAIR_FILTER=\n")

    addToEnv(env_file,'ORACLE_COIN_PAIR_FILTER=', '[' + pairString  + ']')
    actualPairFilters=f"(Actual PairFilters: [{pairString}])"

def parseEnv(line):
    return line.split("=")[1][:-1]

def getEnvData(file):
    global actualAddress
    global actualNode
    global actualRegistryAddress
    global actualPairFilters
    global actualPort

    env_data = OrderedDict()
    with open(file,"r") as f:
        line = f.readline() 
        while line:
            if "http" in line:
                env_data['NODE_URL'] = parseEnv(line)
                actualNode = f"(Actual Node: {env_data['NODE_URL']}"
            elif "CHAIN" in line:
                env_data['CHAIN_ID'] = parseEnv(line)
            elif "ORACLE_PORT" in line:
                env_data['ORACLE_PORT'] = parseEnv(line)
                actualPort = f"(Actual Port: {env_data['ORACLE_PORT']})"
            elif "ORACLE_ADDR" in line:
                env_data['ORACLE_ADDR'] = parseEnv(line)
                actualAddress = f"(Actual address: {env_data['ORACLE_ADDR']})"
            elif "REGISTRY_ADDR" in line:
                env_data['REGISTRY_ADDR'] = parseEnv(line)
                actualRegistryAddress = f"(Actual RegistryAddress: {env_data['REGISTRY_ADDR']})"
            elif "ORACLE_COIN_PAIR_FILTER" in line: 
                env_data['ORACLE_COIN_PAIR_FILTER'] = parseEnv(line)
                actualPairFilters = f"(Actual Node: {env_data['ORACLE_COIN_PAIR_FILTER']})"
            line = f.readline()
    f.close()
    if not bool(env_data):
        env_data = False
    return env_data

def showStatus(env_data):
    missing_fields = OrderedDict()
    print("----- CURRENT ORACLE SETUP ----- \n")
    print(f"---- NETWORK: {env_data['NETWORK']} --------- ")
    
    if 'NODE_URL' in env_data:
        print(f"----  NODE_URL: {env_data['NODE_URL']} ---------")
    else:
        missing_fields['NODE_URL'] = True

    if 'CHAIN_ID' in env_data:
        print(f"----  CHAIN_ID: {env_data['CHAIN_ID']} ---------")
    else:
        missing_fields['CHAIN_ID'] = True

    if 'ORACLE_PORT' in env_data:
        print(f"----  ORACLE_PORT: {env_data['ORACLE_PORT']} ---------")
    else:
        missing_fields['ORACLE_PORT'] = True

    if 'ORACLE_ADDR' in env_data:
        print(f"----  ORACLE_ADDR: {env_data['ORACLE_ADDR']} ---------")
    else:
        missing_fields['ORACLE_ADDR'] = True

    if 'REGISTRY_ADDR' in env_data:
        print(f"----  REGISTRY_ADDR: {env_data['REGISTRY_ADDR']} ---------")
    else:
        missing_fields['REGISTRY_ADDR'] = True
    
    if 'ORACLE_COIN_PAIR_FILTER' in env_data:
        print(f"----  ORACLE_COIN_PAIR_FILTER: {env_data['ORACLE_COIN_PAIR_FILTER']} ---------")
    else:
        missing_fields['ORACLE_COIN_PAIR_FILTER'] = True
    
    print (" ----------------------- ")
    return missing_fields

def showCurrentValues():
    print(" ------ CURRENT VALUES ----- ")
    print(f"{actualAddress}")
    print(f"{actualNode}")
    print(f"{actualRegistryAddress}")
    print(f"{actualPairFilters}")

def setAllMissingFields(missing_fields):
    print("---- ENV FILE EMPTY: SETTING DEFAULT VARIABLES ---- ")
    missing_fields['ORACLE_ADDR'] = True
    missing_fields['ORACLE_PORT'] = True
    missing_fields['NODE_URL'] = True
    missing_fields['CHAIN_ID'] = True
    missing_fields['REGISTRY_ADDR']  = True
    missing_fields['ORACLE_COIN_PAIR_FILTER'] = True

def main(env_file):
    global actualAddress
    global actualNode
    global actualRegistryAddress
    global actualPairFilters
    global actualPort

    quit = False
    env_data = getEnvData(env_file)
    if env_data == False:
        missing_fields = OrderedDict()
        setAllMissingFields(missing_fields)
    else:
        network = "testnet"
        env_data["NETWORK"] = network
        missing_fields = showStatus(env_data)
        for key in missing_fields.keys():
            print(f"\nPENDING CONFIGURATION: {key}\n")

    valid = False
    while (valid == False):
        network = input("\nSelect network (testnet or mainnet) where the node will run. (Default testnet): ")
        if network == '':
            network = 'testnet'
            if "CHAIN_ID" in missing_fields:
                print("--- SETTING DEFAULT CHAIN ID TO TESTNET CHAIN ID (31) ----")
                writeToEnv(env_file,"\nCHAIN_ID=\n")
                addToEnv(env_file,"CHAIN_ID=","31")
            if "NODE_URL" in missing_fields:
                print("--- SETTING DEFAULT PUBLIC RSK TESTNET NODE (https://public-node.testnet.rsk.co) ----")
                writeToEnv(env_file,"\nNODE_URL=\n")
                addToEnv(env_file,"NODE_URL=","https://public-node.testnet.rsk.co")
                actualNode = "(Actual Node: https://public-node.testnet.rsk.co)"
            if "REGISTRY_ADDR" in missing_fields:
                print("--- SETTIND DEFAULT REGISTRY ADDR (0xf078375a3dD89dDF4D9dA460352199C6769b5f10) ---- ")
                writeToEnv(env_file,"\nREGISTRY_ADDR=\n")
                addToEnv(env_file,"REGISTRY_ADDR=","0xf078375a3dD89dDF4D9dA460352199C6769b5f10")
                actualRegistryAddress="(Actual RegistryAdress: 0xf078375a3dD89dDF4D9dA460352199C6769b5f10)"
            if "ORACLE_PORT" in missing_fields:
                print("--- SETTIND DEFAULT ORACLE PORT TO (5556) ---- ")
                writeToEnv(env_file,"\nORACLE_PORT=\n")
                addToEnv(env_file,"ORACLE_PORT=","5556")
                actualPort="(Actual Port: 5556)"
        if network == 'mainnet':
            if "CHAIN_ID" in missing_fields:
                print("--- SETTING DEFAULT CHAIN ID TO TESTNET CHAIN ID (30) ----")
                writeToEnv(env_file,"\nCHAIN_ID=\n")
                addToEnv(env_file,"CHAIN_ID=","30")
            if "NODE_URL" in missing_fields:
                print("--- SETTING DEFAULT PUBLIC RSK TESTNET NODE (https://public-node.rsk.co) ----")
                writeToEnv(env_file,"\nNODE_URL=\n")
                addToEnv(env_file,"NODE_URL=","https://public-node.rsk.co")
                actualNode = "(Actual Node: https://public-node.rsk.co)"
            if "REGISTRY_ADDR" in missing_fields:
                print("--- SETTIND DEFAULT REGISTRY ADDR (0xCD101a2414256DA8F8E25d7b483b3cf639a71683) ---- ")
                writeToEnv(env_file,"\nREGISTRY_ADDR=\n")
                addToEnv(env_file,"REGISTRY_ADDR=","0xCD101a2414256DA8F8E25d7b483b3cf639a71683")
                actualRegistryAddress="(Actual RegistryAddress: 0xCD101a2414256DA8F8E25d7b483b3cf639a71683)"
            if "ORACLE_PORT" in missing_fields:
                print("--- SETTIND DEFAULT ORACLE PORT TO (5556) ---- ")
                writeToEnv(env_file,"\nORACLE_PORT=\n")
                addToEnv(env_file,"ORACLE_PORT=","5556")
                actualPort="(Actual Port: 5556)"

        if ( network != 'testnet' and network != 'mainnet' ):
            valid = False
            print("\nPlease provide a valid network name (mainnet or testnet)\n")
        else:
            valid = True
    
    while quit == False:
        print("\n")
        print("Please, select what do you want to configure right now:")
        print(" 1. Configure my oracle")
        print(" 2. Set your custom RSK Node")
        print(" 3. Set the registry address")
        print(" 4. Select pair filters")
        print(" 5. Set oracle port")
        print(" 6. I have done the five previous items. What are the following instructions?")
        print(" 7. Get current settings")
        print(" 8. Exit")

        Menu = input()
        if (Menu == "1"): oracleOption(env_file)
        if (Menu == "2"): NodeOption(network,env_file)
        if (Menu == "3"): RegistryAddress(network,env_file)
        if (Menu == "4"): PairFilters(env_file)
        if (Menu == "5"): PortOption(env_file)
        if (Menu == "6"): 
            print("")
            print("////////")
            print("if everything is setup correctly, let's run the services.")
            print("Run the following command:")
            print(" ")
            print("docker run -d --name omoc-node --env-file=PATH_TO_YOUR_ENV_FILE --publish ORACLE_HOST_PORT:ORACLE_CONTAINER_PORT omoc-node-img")
            print("Example: ")
            print("docker run -d --name omoc-node --env-file=./env_file --publish 5556:5556 omoc-node-img")
            print(" ")
            print("////////")
            quit = True
        if (Menu == "7") : showCurrentValues()
        if (Menu == "8" ): quit = True
    
        

if __name__ == "__main__":
    parser = get_parser()
    if not parser['env']:
        env_file = f"{SCRIPT_PATH}/../Docker/.env_file"
        main(env_file)
    else:
        main(parser['env'])