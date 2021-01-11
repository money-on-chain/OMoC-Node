#!/bin/bash 

STARTORACLE=false
STARTBACKEND=false

function isOracleStarting {
    echo 'You are ready to start your oracle, do you want to start it now? (y/n)) ' 
    read answerOracle
    if [ "$answerOracle" = "y" ]; then
        STARTORACLE=true
    fi
}

function startOracle {
    isOracleStarting
    if [ "$STARTORACLE" = "true" ]; then
        pm2 start --name oracle servers/run_oracle.sh
    fi
}

echo "---- Starting oracle set up -----"
python3 scripts/setAddress.py
startOracle
echo "Finish oracle set up"