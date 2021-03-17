### Usage 

* Build: 
    * docker build -t omoc-node-img -f Docker/Dockerfile .

* Run: 
    * Set oracle configuration: 
        python3 scripts/setAddress.py [-e env file]
    * This will generate a file with the following configuration 
        ```
            CHAIN_ID=31

            NODE_URL=https://public-node.testnet.rsk.co

            REGISTRY_ADDR=0x_registry_addr

            ORACLE_ADDR=0x_oracle_addr

            ORACLE_PRIVATE_KEY=ox_oracle_private_key

            ORACLE_COIN_PAIR_FILTER=["COINPAIR1","COINPAIR2","COINPAIRN"]

            ORACLE_PORT=oracle_port
        ```
    
    * docker run --restart always --name omoc --publish 5556:5556 --env-file=./env_docker omoc-node-img


* docker run -it --restart always --name omoc-node --publish 5004:5004 --env-file=./Docker/.env_file omoc-node-img /bin/bash
* docker run --restart always --name omoc-node --publish 5004:5004 --env-file=./Docker/.env_file omoc-node-img 
docker run --restart always --name omoc-node --publish 5556:5556 --env-file=./Docker/.env_file omoc-node-img 