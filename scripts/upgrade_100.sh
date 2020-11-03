#!/bin/bash

# AMI upgrade from v0.7.0 to v1.0.0
#	run as user ubuntu

wget http://oracles.coinfabrik.com/abis/latest.tgz
mv contracts contracts_v0.7.0
mkdir contracts
cd contracts
tar -zxvf ../latest.tgz
cd ..
rm latest.tgz

git pull
# We update the oracle server python environment
cd servers
. ./venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..

# Replace contract folder location in the ".env" file
server_env="./servers/.env"
search="CONTRACT_ROOT_FOLDER" ; replace="CONTRACT_ROOT_FOLDER=../contracts/" ; sed -i "/${search}/c ${replace}" ${server_env}

# Update server to run from RSK public node
search="NODE_URL" ; replace="NODE_URL=\"https://public-node.testnet.rsk.co:443\"" ; sed -i "/^[^#]*${search}.*/c ${replace}" ${server_env}
