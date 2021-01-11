#!/bin/bash

# AMI upgrade from v0.7.0 to v1.0.0
#	run as user ubuntu

wget http://oracles.coinfabrik.com/abis/latest_beyond.tgz
mv contracts contracts_v0.7.0
mkdir contracts
cd contracts
tar -zxvf ../latest_beyond.tgz
cd ..
rm latest_beyond.tgz

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

# Add registry address
echo "" >> ${server_env}
echo "# Registry Address" >> ${server_env}
echo "REGISTRY_ADDR=\"0xf078375a3dD89dDF4D9dA460352199C6769b5f10\"" >> ${server_env}
