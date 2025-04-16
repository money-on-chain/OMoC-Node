# Usage 

## 1 - Build:

```bash
docker build -t omoc_node -f Docker/Dockerfile .
```

## 2 - Run

### 2.1 - Set oracle configuration:

```bash
$ python3 scripts/setAddress.py [-e env file]
```
        
This will generate a file with the following configuration 
        
```bash
CHAIN_ID=31
NODE_URL=https://public-node.testnet.rsk.co
REGISTRY_ADDR=0x...
ORACLE_ADDR=0x...
ORACLE_PRIVATE_KEY=0x...
ORACLE_COIN_PAIR_FILTER=["COINPAIR1","COINPAIR2", "COINPAIRN"]
ORACLE_PORT=5004
```

### 2.2 - Run docker instance (some examples)

```
$ sudo docker run -d \
--name some_omoc_node \
--publish 5004:5004 \
--env-file=./env_file \
omoc_node
```

Or locally and interactively

```
$ sudo docker run --rm \
--name some_omoc_node \
--publish 5004:5004 \
--env-file=./env_file \
-it omoc_node
```