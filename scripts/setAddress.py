from getpass import getpass
from pathlib import Path
from ethereum import utils
from datetime import datetime
import re, os, requests

envMonitor = "monitor/backend/.env"
envServer = "servers/.env"

actualRegistryAddress = "(Actual Adress: None)"
actualPairFilter = "(Actual Adress: None)"
actualAddress = "(Actual Adress: None)"
actualEmail = "(Actual Email: None)"
actualNode = "(Actual Node: None)"

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
            print("Do you have a privateKey and Address or you want to generate the pair?")
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

def addTo(filePath, search, addText):
    file = Path(filePath)
    content = re.sub(r'\n' + re.escape(search) + r'.*'
                    ,'\n' + search + addText,
                    file.read_text())
    file.open('w').write(content)

def NodeOption(network):
    global envServer
    print("///////////")
    print("Now we will setup your RSK Node.")
    print("Enter your RSK Node address in the form of 'http://<<IP>>:<<PORT>>'")
    print("or press enter if you want to connect to the public node.")
    print("The default public node matchs the network selected previosuly.")
    print("///////////")
    node = input("Node (default: public-node):")
    if node == '':
        if network == 'testnet':
            node = 'https://omoc-test.moneyonchain.com/info'
        elif network == 'mainnet':
            node = 'https://moc.moneyonchain.com/info'
    addTo(envServer,'NODE_URL=', '"' + node  + '"')

def RegistryAddress(network):
    global envServer
    print("///////////")
    print("Now we will setup the Registry Address.")
    print("The default registry address matchs the network selected previosuly.")
    print("///////////")
    registry_address = input("Registry address:")
    if registry_address == "":
        if network == 'testnet':
            registry_address = '0xf078375a3dD89dDF4D9dA460352199C6769b5f10'
        elif network == 'mainnet':
            registry_address = '0xCD101a2414256DA8F8E25d7b483b3cf639a71683'
    addTo(envServer,'REGISTRY_ADDR=', '"' + registry_address  + '"')

def PairFilters():
    global envServer
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
    addTo(envServer,'ORACLE_COIN_PAIR_FILTER=', '[' + pairString  + ']')

def oracleOption():
    global envMonitor
    global envServer
    global actualAddress

    oracle = Account.getAccount("oracle")

    ### NO SCheduler ###
        #answ = input("You want to use the same address for the scheduler? (Yes/No) (default: Yes)").lower()
        #if (answ in ["no","n"]):
        #    scheduler = Account.getAccount("scheduler")
        #else:
        #    scheduler = Account("")
        #    scheduler.setAddress(oracle.address)
        #    scheduler.setPrivateKey(oracle.privateKey)

    #addTo(envServer,"ORACLE_ADDR=",'"' + oracle.address + '"')
    addTo(envServer,"ORACLE_PRIVATE_KEY=",'"' + oracle.privateKey + '"' )
    #addTo(envServer,"SCHEDULER_SIGNING_ADDR = ",'"' + scheduler.address  + '"')
    #addTo(envServer,"SCHEDULER_SIGNING_KEY = ", '"' + scheduler.privateKey + '"')
    addTo(envMonitor,"ORACLE_SERVER_ADDRESS=",oracle.address)

def emailOption():
    global envMonitor
    print("///////////")
    print("Now we will setup your SMTP email configuration. ")
    print("///////////")

    #user input
    smtp_host  = input("SMTP_HOST:")
    smtp_port = input("SMTP_PORT:")
    answ = input("Does the SMTP account require using TLS? (Yes/No) (default: Yes)").lower()
    if answ in ["no","n"]:
        SMTP_SSL_TLS = "no"
    else:
        SMTP_SSL_TLS= "yes"
    SMTP_user = input("SMTP user:")
    SMTP_pass = getpass("SMTP password:")
    emailFrom = input("From:")
    print("What email account will receive the messages?")
    emailTo = input("to:")
    print("How often, in minutes, are the emails sent?")
    minutes = input("minutes (default:60): ")
    seconds = str(int(minutes) * 60) if minutes.strip().isnumeric() else  str(60 * 60)
    #setup file
    addTo(envMonitor,"SMTP_HOST=", smtp_host)
    addTo(envMonitor,"SMTP_PORT=", smtp_port)
    addTo(envMonitor,"SMTP_SSL_TLS=", SMTP_SSL_TLS)
    addTo(envMonitor,"SMTP_USER=", SMTP_user)
    addTo(envMonitor,"SMTP_PWD=", SMTP_pass)
    addTo(envMonitor,"SMTP_From=", emailFrom)
    addTo(envMonitor,"ALERT_EMAILS=", emailTo)
    addTo(envMonitor,"EMAIL_REPEAT_INTERVAL=", seconds)

def checkStatus():
    global envMonitor
    global envServer
    global actualAddress
    global actualRegistryAddress
    global actualPairFilter
    global actualEmail 
    global actualNode

    fileMonitor = Path(envMonitor)
    fileServer  = Path(envServer)

    registry_address = re.search('REGISTRY_ADDR=.*',fileServer.read_text())
    pairs = re.search('ORACLE_COIN_PAIR_FILTER=.*',fileServer.read_text())
    oracle = re.search('ORACLE_SERVER_ADDRESS=.*',fileMonitor.read_text())
    mail = re.search('SMTP_HOST=.*',fileMonitor.read_text())
    node = re.search(r'^NODE_URL=.*',fileServer.read_text(),re.MULTILINE)
    print(registry_address)
    if (registry_address.group().strip() != "REGISTRY_ADDR="):
        actualRegistryAddress = "(Actual Registry Address: " + registry_address.group().strip()[14:] + ")"
    if (pairs.group().strip() != "ORACLE_COIN_PAIR_FILTER="):
        actualPairFilter = "(Actual Pairs: " + pairs.group().strip()[24:] + ")"
    if (oracle.group().strip() != "ORACLE_SERVER_ADDRESS="):
        actualAddress = "(Actual Address: " + oracle.group().strip()[22:] + ")"
    if (mail.group().strip() != "SMTP_HOST=" ): 
        actualEmail = "(Actual Email:" + mail.group().strip()[10:] +")"
    actualNode = "(Actual Node: " + node.group().strip()[10:-1] + ")"

def main():
    global envMonitor
    global envServer
    global actualAddress
    global actualEmail
    global actualNode

    folders = os.getcwd().split("/")
    if ((folders[len(folders)-1] ) == "scripts"):
        envMonitor = "../" + envMonitor
        envServer = "../" + envServer
    # Address  and privateKey
    print("///////////")
    print("We are going to configure your oracle. ")
    print("For this we will require an address and its respective privateKey to the RSK network. ")
    print("As well as an SMTP user and an email to notify about error messages.")
    print("An important thing to keep in mind is that you will need to have RBTC in this `oracle` account to pay for the system gas.")
    print("Please, enter the information that will be requested below.")
    print("Note: Private data (private keys and passwords) given by the user will not be displayed on the console")
    print("///////////")
    print("")

    valid = False
    while (valid == False):
        network = input("Select network (testnet or mainnet) where the node will run. (Default testnet): ")
        if network == '':
            network = 'testnet'
        if ( network != 'testnet' and network != 'mainnet' ):
            valid = False
        else:
            valid = True

    quit = False
    while (quit ==False):
        checkStatus()
        print("Please, select what do you want to configure right now:")
        print(" 1. Configure my oracle" + "--------" + actualAddress)
        print(" 2. Configure my email account" + "--------" + actualEmail)
        print(" 3. Set your custom RSK Node " + "--------" + actualNode)
        print(" 4. Set the registry address" + "--------" + actualRegistryAddress)
        print(" 5. Select pair filters" + "--------" + actualPairFilter)
        print(" 6. I have done the five previous items. What are the following instructions?")
        print(" 7. Exit")

        Menu = input()
        if (Menu == "1"): oracleOption()
        if (Menu == "2"): emailOption()
        if (Menu == "3"): NodeOption(network)
        if (Menu == "4"): RegistryAddress(network)
        if (Menu == "5"): PairFilters()
        if (Menu == "6"): 
            print("")
            print("////////")
            print("if everything is setup correctly, let's run the services.")
            print("Run the following commands:")
            print(" ")
            print("sudo systemctl enable supervisor.service")
            print("sudo supervisord")
            print("supervisorctl status")
            print(" ")
            print("////////")
            quit = True
        if (Menu == "7" ): quit = True

if __name__ == "__main__":
    main()
