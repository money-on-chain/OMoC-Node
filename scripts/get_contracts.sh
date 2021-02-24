#!/bin/bash 

set -e 

git clone https://github.com/money-on-chain/py_Moneyonchain.git
cd py_Moneyonchain/moneyonchain/abi_omoc/
if [ -d ~/OMoC-Node/contracts/build/contracts ]; then
    cp *.json ~/OMoC-Node/contracts/build/contracts/
else 
    mkdir -p ~/OMoC-Node/contracts/build/contracts
    cp *.json ~/OMoC-Node/contracts/build/contracts/
fi 
cd 
rm -rf py_Moneyonchain

