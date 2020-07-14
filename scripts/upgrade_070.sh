#!/bin/bash

# AMI upgrade from v0.6.0 to v0.7.0
#	run as user ubuntu

cd OMoC-Node
wget http://oracles.coinfabrik.com/abis/latest.tgz
mv contracts contracts_v0.6.0
mkdir contracts
cd contracts
tar -zxvf ../latest.tgz
cd ..
rm latest.tgz

git pull
# We update the monitor python environment
. ./venv/bin/activate
pip install -r monitor/backend/requirements.txt
deactivate
# We update the oracle server python environment
cd servers
. ./venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..

# Add contract folder location at the end of ".env" file
server_env="./servers/.env"
echo "" >> ${server_env}
echo "# Contracts ABI folder location" >> ${server_env}
echo "CONTRACT_ROOT_FOLDER=../contracts/" >> ${server_env}

# Update server to run from RSK public node
search="NODE_URL" ; replace="#NODE_URL" ; sed -i "s/${search}/${replace}/g" ${server_env}
echo "" >> ${server_env}
echo "# RSK testnet node" >> ${server_env}
echo "NODE_URL=\"https://public-node.testnet.rsk.co:443\"" >> ${server_env}

# Remove log folder for backend
backend_env="/home/ubuntu/OMoC-Node/monitor/backend/.env"
search="ALERT_LOG_FILENAME" ; replace="#ALERT_LOG_FILENAME" ; sed -i "s/${search}/${replace}/g" ${backend_env}
#echo "" >> ${backend_env}
#echo "# Log file reporting" >> ${backend_env}
#echo "ALERT_LOG_FILENAME=/var/log/supervisor/monitor.log" >> ${backend_env}
#-- Another option is to do as follow (but requires sudo): --
#sudo touch /var/log/supervisor/monitor.log
#sudo chown ubuntu:ubuntu /var/log/supervisor/monitor.log
#-- Fixed on the AMI, not included in the upgrade
