#!/bin/bash

# AMI upgrade from v0.6.0 to v0.7.0
#	run as user ubuntu

cd OMoC-Node
wget http://oracles.coinfabrik.com/abis/latest.tgz
rm -Rf contracts
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
