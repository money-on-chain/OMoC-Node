# Oracle price feeder reference implementation

## Requirements 

The server uses Python >=3.7. Run the following command to install the needed packages:

```
sudo apt-get install python3 python-dev python3-dev \
     build-essential libssl-dev libffi-dev \
     libxml2-dev libxslt1-dev zlib1g-dev \
     python3.7-dev \
     python-pip
```


## Installation
- Clone the Oracle repository.

- Go to the `server` directory inside the repo.

- Create a python virtualenv: 

      virtualenv -p python3.7 venv

- Activate the virtual environment:
    -  source venv/bin/activate
    
- Install the required python libraries:
    - pip install -r requirements.txt
    
- Build the contracts following the instructions on [contracts/README.md](../contracts/README.md)

- Configure the server by renaming the `dotenv_example` file to `.env`:
    - mv dotenv_example .env
    
- Edit the `.env` configuration file with a text editor and set the server parameters accordingly.
For more details see [Server Configuration](#server-configuration).

    - For this step you need an address (with the corresponding private key) and rsk funds in order 
    to deploy the oracle. This address/key is used to publish prices in the blockchain. 
    - Open .env: 
        - And set the followin parameters
        
        `NODE_URL = "https://public-node.testnet.rsk.co:443"`

        `CHAIN_ID=31`

        `ORACLE_PRIVATE_KEY="Your private key 0x..."`
        
    - Optionally configure the server signing port:

        `ORACLE_PORT=5556`

        Even though default configuration is 5556 you can choose any port you like as this is flexible.

- Start the oracle: 

```
./run_oracle.sh
```

- Register the Oracle and subscribe to the desired coin pairs using the web application (dapp)



# Server Configuration
The server needs three kind of configuration values
1. The server configuration parameters. Those are taken from the environment or set in a `.env` file. 
2. The address of the registry contract.
3. The contracts abi (Application Binary Interface)

The server configuration parameters are used to connect to the blockchain. After connecting to the 
blockchain, using the contracts abi and the address of the registry contract the server
get the rest of the configuration directly from the blockchain registry. This way all the Oracles
use the same parameter values.


### Contracts abi and address of the registry contract
The server expect to find the contracts abi inside the json files generated during the 
deployment process. Those files are stored in the directory `contract/build` (CONTRACT_FOLDER). Those 
files also include the contract addresses. This information is used to call the contracts. Specifically 
it is used to call the blockchain registry contract that stores the rest of the parameters.
The only mandatory parameters are the ones used to connect to the blockchain and are described bellow.

### Server configuration parameters
Except for the variables needed to connect to the block chain and the private key, the rest
of the parameters are optional. The server starts with reasonable defaults and then gets the 
parameters from the blockchain. 
 
An example of the minimal set of variables can be found in `dotenv_example` file. 
Those variables are:
- NODE_URL: The url used to access the block chain node.
- CHAIN_ID: Needed if the blockchain doesn't support the eth_chainId rpc call.
- ORACLE_PRIVATE_KEY: This is the private key of the account used to publish prices.

The rest of the parameters are optional. If they are missing they are taken from the registry smart contract.

- DEVELOP_NETWORK_ID = 12341234 
    
    This parameter is needed only if the contract were deployed to more then one network. In this
    case the json file contains more than one address and to choose the right one the 
    `DEVELOP_NETWORK_ID` is used.  
    
- CONTRACT_FOLDER = "../build/contracts"

    This parameter contains the path to the contract folder.
    
- WEB3_TIMEOUT = "30 secs" 
    
    This is the timeout used when connecting to the blockchain node.

- SCHEDULER_POOL_DELAY = "10 secs"

    Delay in which the supporters scheduler checks for round change conditions and try to execute a 
    distribute transaction.

- SCHEDULER_ROUND_DELAY = "1 days"
    
    Delay in which the supporters scheduler checks for round change after a round was successfully closed.
    
- SCHEDULER_RUN_ORACLE_SCHEDULER = True

    This parameter can be used to disable the Oracle scheduler.

- SCHEDULER_RUN_SUPPORTERS_SCHEDULER = True     
        
    This parameter can be used to disable the Supporters scheduler.

- ORACLE_RUN = True
    
    This parameter can be used to disable the Oracle. The server still runs the schedulers.

- ORACLE_PORT = 5556

    Port in which the oracle listen for sign request.

- ORACLE_MONITOR_RUN = False

    This can be used to enable/disable the internal monitor. The monitor is a module that store information 
    in log files.

- ORACLE_MAIN_LOOP_TASK_INTERVAL = "120 secs"

    This is the delay in which the Oracle check for coin pairs in the OracleManager smart contract.
    The main loop maintains a list of coin pairs for which the price must be published. For each
    coin pair there are tasks to get the price from the exchanges and to publish to the blockchain. 

- ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL = "3 secs"

    Per coin pair loop scanning interval. Every ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL we check for the
    right conditions to publish a price, then we try to get the signature and send the transaction to
    the blockchain.

- ORACLE_BLOCKCHAIN_INFO_INTERVAL = "3 secs"

    Interval in which we collect information from the blockchain. Things like last publication block, current
    block number, etc.

- ORACLE_PRICE_FETCH_RATE = "5 secs"

    Interval in which we check exchanges price. All the exchanges are queried at the same time in parallel.

- ORACLE_PRICE_REJECT_DELTA_PCT = 50

    When an Oracle ask for a signature if the price difference percentage is grater than this value
    we reject the request by not signing.
    
- ORACLE_PRICE_DELTA_PCT = 0.05
    
    To decide when to publish the Oracle check for the price difference percentage between the currently
    published price in the blockchain and the last price from the exchanges. It the change is more than
    `ORACLE_PRICE_DELTA_PCT` the Oracle starts to count blocks. After `ORACLE_PRICE_PUBLISH_BLOCKS`
    the selected Oracle try to publish and after `ORACLE_ENTERING_FALLBACKS_AMOUNTS` list is used to 
    check how many fall back oracles try to publish.

- ORACLE_PRICE_PUBLISH_BLOCKS = 1

    The selected oracle publishes after `ORACLE_PRICE_PUBLISH_BLOCKS` blocks after a price change.

- ORACLE_ENTERING_FALLBACKS_AMOUNTS = b'\x02\x04\x06\x08\n'

    See ORACLE_PRICE_DELTA_PCT explanation bellow.

- ORACLE_GATHER_SIGNATURE_TIMEOUT = "60 secs"

    Timeout used when requesting signatures fom other oracles.

- ORACLE_COIN_PAIR_FILTER = [ "BTCUSD", "RIFUSD" ]

    This can be used to limit the coin pairs that the Oracle monitors. The missing coin pairs are ignored
    even if the Oracle is subscribed to them. **An empty value `[]`) means: to monitor all coin pairs**.
  
- ORACLE_PRICE_RECEIVE_MAX_AGE=<float>   
  Received price max age in exchange cache before we consider it a No-Price. 
  It is expected to be expressed in seconds. For details check 
  [PRICE_HANDLING.md](../PRICE_HANDLING.md).
  
- ORACLE_PRICE_PUBLISH_MAX_DIFF=<float>
- ORACLE_PRICE_VALIDATE_MAX_DIF=<float>
  
    Max time difference between the time a price is searched for and the 
    values returned from the price-queue. One value is used when generating a 
    new price, and the other is used when generating a price to be used to 
    validate third party oracles price proposal. For details check 
    [PRICE_HANDLING.md](../PRICE_HANDLING.md).


#### Exchanges to use by coinpair and their ponderation

The exchange list to use is configured in `exchange.json` file. the format is:

```json
{ 
  "coinpair1": [
      exchange_info-one-for-coinpair1,
      exchange_info-two-for-coinpair1, and so on..
  ]
}
```
containing as many _coinpairs_ and as many exchanges per _coinpair_ as 
required.

Here _exchange_info_ is like this:

```json
{"name": "bitstamp", "ponderation": "0.22", "min_volume": 0.0, "max_delay": 0}
```

(here name must be one of the exchanges defined in sourcecode. The 
ponderation is how it is weighted among the other exchanges when used. Keep 
in mind the ponderation is automatically normalized. Price is given as a 
string value to interpreted with all the decimals it is expressed).


#### Server configuration: parameters for development 

Besides the minimal set of variables previously mentioned, the following parameters are also needed for development:

- SCRIPT_ORACLE_OWNER_ADDR="0x3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9"
- SCRIPT_ORACLE_OWNER_PRIVATE_KEY="0xe485d098507f54e7733a205420dfddbe58db035fa577fc294ebd14db90767a52"
- SCRIPT_REWARD_BAG_ADDR="0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1"
- SCRIPT_REWARD_BAG_PRIVATE_KEY="4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"

The following are optional:

- DEBUG = False

    Turn on debug logging.

- UVICOIN_DEBUG = False
    
    Turn on web server debug logging. Log requests, etc.
    
- LOG_LEVEL = "info"

    Default log level.
    
    
- DEBUG_ENDPOINTS = False

    Add a swagger interface for the endpoints.

- PROXY_HEADERS = False
    
    Populate remote address info.

- RELOAD = False
    
    Reload the server automatically on a source code change.
    
- ON_ERROR_PRINT_STACK_TRACE = False

    Print the stack trace of the errors.


       
#### Server configuration: Full example
```
# Ganache cli
# NODE_URL="http://localhost:8545"
# CHAIN_ID=1

# RSK testnet
NODE_URL="https://public-node.testnet.rsk.co:443"
CHAIN_ID=31

# RSK regtest
#NODE_URL = "http://localhost:4444"
#CHAIN_ID=33 (NEEDED IF THE SERVER DOESN'T SUPPORT GET_CHAIN_ID RPC CALL)
#DEVELOP_NETWORK_ID=33 (OPTIONAL)

# RSK testnet CoinFabrik
# NODE_URL = "http://rsknodes:4446"
# CHAIN_ID=31 (NEEDED IF THE SERVER DOESN'T SUPPORT GET_CHAIN_ID RPC CALL)
# DEVELOP_NETWORK_ID=31 (OPTIONAL)

# RSK testnet
# NODE_URL = "https://public-node.testnet.rsk.co:443"
# CHAIN_ID=31 (NEEDED IF THE SERVER DOESN'T SUPPORT GET_CHAIN_ID RPC CALL)
# DEVELOP_NETWORK_ID=31 (OPTIONAL)

# The server expect to find in this folder the *.json files with the abi an addresses of contracts
# CONTRACT_FOLDER = "../build/contracts"

# Timeout used when connection to the blockchain node
# WEB3_TIMEOUT = "30 secs"

############################################### SCHEDULER

# Delay in which the scheduler checks for round change conditions
# SCHEDULER_POOL_DELAY = "10 secs"
# Delay in which the scheduler checks for round change after a round was closed
# SCHEDULER_ROUND_DELAY = "1 days"
# Run the oracle round scheduler?
# SCHEDULER_RUN_ORACLE_SCHEDULER = True
# Run the supporters round scheduler?
# SCHEDULER_RUN_SUPPORTERS_SCHEDULER = True


############################################### ORACLE
# Run the oracle server (sign api and publisher).
ORACLE_RUN = True

# Port in which the oracle listen for sign request
ORACLE_PORT = 5556

# Flag that indicates if the monitor (a module that store information in logfiles) must be run
ORACLE_MONITOR_RUN = False

# Flag that indicates if we must filter requests to /sign by ip.
ORACLE_RUN_IP_FILTER = True

# Oracle-only parameters.
# Account used to publish prices
ORACLE_ADDR="0x..."
ORACLE_PRIVATE_KEY="0x..."

# Main Oracle loop scanning interval, in which we get the coinpair list
ORACLE_MAIN_LOOP_TASK_INTERVAL = "120 secs"

# Per coin pair loop scanning interval, in which we try to publish
ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL = "3 secs"

# This loop collect a lot of information needed for validation (like last pub block) from the block chain
ORACLE_BLOCKCHAIN_INFO_INTERVAL = "3 secs"

# Exchange price- etch rate in seconds, all the exchanges are queried at the same time.
ORACLE_PRICE_FETCH_RATE = "5 secs"

# If the price delta percentage is grater than this we reject by not signing
ORACLE_PRICE_REJECT_DELTA_PCT = 50

# Try to publish if the price has changed more than this percentage  
ORACLE_PRICE_DELTA_PCT = 0.05

# Selected oracle publishes after ORACLE_PRICE_PUBLISH_BLOCKS  blocks of a price change.
ORACLE_PRICE_PUBLISH_BLOCKS = 1

#
ORACLE_ENTERING_FALLBACKS_AMOUNTS=

# Timeout used when requesting signatures fom other oracles
ORACLE_GATHER_SIGNATURE_TIMEOUT = "60 secs"

# If configured (json array of strings) only publish for those coinpairs in the list
ORACLE_COIN_PAIR_FILTER =[ "BTCUSD", "RIFUSD" ]



############################################### ONLY FOR DEVELOPMENT

# Turn on debug?
# DEBUG = False
# UVICOIN_DEBUG = False
# LOG_LEVEL = "info"
# Add some development endpoints
# DEBUG_ENDPOINTS = False
# Populate remote address info.
# PROXY_HEADERS = False
# Reload on source code change, used for development
# RELOAD = False
# Print stack trace of errors, used for development
# ON_ERROR_PRINT_STACK_TRACE = False
```

## Running a Local Environment

### Requirements:

You need to have locally installed: python3.7 & python3.7-dev

### Steps:

On your local copy of the repository create a Python virtual environment:

```
cd servers
pip3 install virtualenv
virtualenv -p /usr/bin/python3.7 venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

Now you'll need to configure your local environment:

```
cp dotenv_example .env
```

Edit the `.env` file to have:

```
# Contracts ABI folder location
CONTRACT_ROOT_FOLDER=../../OMoC-SC-Shared/

# Ganache cli
NODE_URL="http://localhost:8545"
CHAIN_ID=1

# Oracle-only parameters.
# Account used to publish prices. Should have ETH to pay gas costs.
SCRIPT_ORACLE_OWNER_ADDR="0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1"
SCRIPT_ORACLE_OWNER_PRIVATE_KEY="0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"

# Account used to manage tokens. Should have MOC to use for oracles stake.
SCRIPT_REWARD_BAG_ADDR="0xFFcf8FDEE72ac11b5c542428B35EEF5769C409f0"
SCRIPT_REWARD_BAG_PRIVATE_KEY="0x6cbed15c793ce57650b9877cf6fa156fbef513c4e6134f022a85b1ffdd59b2a1"

# Used by Oracle to publish prices. Should have ETH to pay gas costs.
# Associated ORACLE_PUBLIC_KEY 0x22d491Bde2303f2f43325b2108D26f1eAbA1e32b
ORACLE_PRIVATE_KEY="0x6370fd033278c143179d81c5526140625662b8daa446c22ee2d73db3707e620c"

# Contract registry address. Check OMoC-SC-Shared/.openzeppelin/dev-12341234.json
# Is the address within "proxies" -> "@moc/shared/Registry" -> "address"
REGISTRY_ADDR="0xA94B7f0465E98609391C623d0560C5720a3f2D33"
```

Transfer Tokens to the SCRIPT_REWARD_BAG_ADDR address:

```
npx truffle exec scripts/changeMinToken.js 0xFFcf8FDEE72ac11b5c542428B35EEF5769C409f0 2000
```

And now you can run the oracle nodes locally:

```
scripts/run.sh netsim
```

# Running multiple Oracle price feeders in a single machine (test environment configuration)

## Configuration files and scripts

### delfos/address.sh

In this file you'll need to configure the multiple oracle node address (public key), private key and port.

To get/generate an address + private key for each oracle within the machine you can use the following script:

```
# pip3 install ethereum

from ethereum import utils
from datetime import datetime
import os, requests

words =""
while len(words.split()) < 2:
	print("Enter 2 or more words separated by spaces.")
	print("We will use them as part of the seed used for generate a random privateKey")
	words = input()

now = datetime.now()
randomFromWeb = requests.get('https://www.random.org/integers/?num=1&min=1&max=4096&col=1&base=10&format=plain&rnd=new').text
seed_str =  (randomFromWeb + str(os.urandom(4096)) + now.strftime("%d/%m/%Y %H:%M:%S") + words)
privKey_Raw = utils.sha3(seed_str)
address = utils.checksum_encode(utils.privtoaddr(privKey_Raw))
privateKey = utils.encode_hex(privKey_Raw)

print("Address: " + address)
print("PrivateKey: " + privateKey)

```

### delfos/oracle.sh

This file simply takes as input the data you entered on address.sh, so nothing to do here. PM2 will use it to launch and configure each instance.

### Contracts ABIs

You'll need to fetch the latest version of the contracts ABIs, so the oracle server can communicate with the SCs:

```
wget http://oracles.coinfabrik.com/abis/latest_beyond.tgz
mv contracts contracts_v0.7.0
mkdir contracts
cd contracts
tar -zxvf ../latest_beyond.tgz
cd ..
rm latest_beyond.tgz
```

### dotEnv file

You'll need to create a ".env" with the basic configuration the N oracles you run will share:

```
# rsk testnet
NODE_URL="http://moc-rsk-node-testnet.moneyonchain.com:4454"
CHAIN_ID=31
DEBUG=True
ON_ERROR_PRINT_STACK_TRACE=True
CONTRACT_ROOT_FOLDER=/home/ubuntu/contracts
REGISTRY_ADDR="0x4791b9769DC1b82019904aa1cb45BDF1107888e4"
```

You can get the REGISTRY_ADDR from the info tab on the OMoC WebApp application.

### PM2 configuration

We have an example configuration for PM2 at servers/ecosystem.config.js which will run N copies of the oracles. Key configurations are:

```
    name: "Oracle" ,
    script: './delfos/oracle.sh',
    instances: 3, // How many copies to run
    instance_var: "InstanceID",
    autorestart: true,
    namespace: "Delfos",
```

A full copy, description and explanation on how to use this file can be found at https://pm2.keymetrics.io/docs/usage/application-declaration/

Then simply run:

```
cd ~/OMoC-Node/servers/
pm2 restart ecosystem.config.js
```

And make sure configuration is running correctly by doing:

```
netstat -tulpn | grep LISTEN
```

You can always check job status by doing:

```
pm2 monit
```

We strongly suggest to add:

```
pm2 logrotate
```

To keep disk usage at a reasonable size. The oracle logs in this configuration will be extremely verbose.

### Signing ports

On the delfos/address.sh you have configured the ports for each server you are running. It is important to open this ports (iptables, aws security groups, DigitalOcean firewall, etc...) so the different servers can reach each other in order to sign and get price consensus.
