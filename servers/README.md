## Scheduler implementation

- [Scheduler implementation](#scheduler-implementation)
  * [Requirements](#requirements)
  * [Instalation guide](#instalation-guide)

*** 

### Requirements 

- First, run the following command to install dependencies and requirements:

```
sudo apt-get install python3 python-dev python3-dev \
     build-essential libssl-dev libffi-dev \
     libxml2-dev libxslt1-dev zlib1g-dev \
     python3.7-dev \
     python-pip
```

### Instalation guide
- Create a python virtualenv: 

      virtualenv -p /usr/bin/python3.7 venv

- Run:
    -  source venv/bin/activate
- Then:
    - pip install -r requirements.txt
- Rename the dotenv_example:
    - mv dotenv_example .env
- Make a build directory inside the contracts folder: 
    - mkdir ../contracts/build
- Make a contracts directory inside the build folder: 
    - mkdir ../contracts/build/contracts
- Copy the contracts located in: **Add where the contracts are suposed to be**.
- For the next step you need an address and rsk funds in order to deploy the oracle: 
    - Open .env: 
        - Locate the commented line saying # rsk testnet and make sure the lines below match the following  text:
        
        **NODE_URL = "http://10.0.0.73:4444"**
        **NETWORK_ID=31**
        **CHAIN_ID=31**
    - Now locate the commented line saying  *# oracle-only parameters*. Complete the following fields: 
    **ORACLE_ADDR="Your address"**
    **ORACLE_PRIVATE_KEY="Your private key"**
    - Finally, uncomment the following lines: 
```
# Main Oracle loop scanning interval, in which we get the coinpair list
ORACLE_MAIN_LOOP_TASK_INTERVAL = "120 secs"

# Per coin pair loop scanning interval, in which we try to publish
ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL = "3 secs"

# This loop collect a lot of information needed for validation (like last pub block) from the blockchain
ORACLE_BLOCKCHAIN_INFO_INTERVAL = "3 secs"

# Exchange price- etch rate in seconds, all the exchanges are queried at the same time.
ORACLE_PRICE_FETCH_RATE = "5 secs"

# If the price delta percentage is grater than this we reject by not signing
ORACLE_PRICE_REJECT_DELTA_PCT = 50

# If the price delta percentage has changed and more than ORACLE_PRICE_FALLBACK_BLOCKS pass we act as fallbacks.
ORACLE_PRICE_FALLBACK_DELTA_PCT = 0.05

# Selected oracle publishes after ORACLE_PRICE_PUBLISH_BLOCKS blocks of a price change.
ORACLE_PRICE_PUBLISH_BLOCKS = 1

# Fallback oracle try to publish ORACLE_PRICE_FALLBACK_BLOCKS blocks after price change.
ORACLE_PRICE_FALLBACK_BLOCKS = 3

# Timeout used when requesting signatures fom other oracles
ORACLE_GATHER_SIGNATURE_TIMEOUT = "2 secs"

# This is used to limit the difference in participation between selected oracles, the maximum stake used
# is the minimum multiplied by this factor (even if some oracle has more stake participating)
ORACLE_STAKE_LIMIT_MULTIPLICATOR = 2
```

- Start the oracle: 
    - To run in detached mode: 
        - tmux
        - ./run_oracle.sh
        - ctrl+b then d
    - Or you could just simple type ./run_oracle.sh 