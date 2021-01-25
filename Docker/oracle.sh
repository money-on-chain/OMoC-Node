#!/bin/bash 

STARTORACLE=false
FIRSTTIME=false

function isFirstTime {
    cd ./monitor/backend
    hasOracleEnv=$(find ./ -name ".env" | wc -l)
    if [ $hasOracleEnv -ne 1 ]; then
        FIRSTTIME=true
        touch .env
        cp dotenv_example .env
    fi
}

function isOracleStarting {
    echo 'You are ready to start your oracle, do you want to start it now? (y/n)) ' 
    read answerOracle
    if [ "$answerOracle" = "y" ]; then
        STARTORACLE=true
    fi
}

function runOracle {
    isOracleStarting
    if [ "$STARTORACLE" = "true" ]; then
        cd ./servers 
        pm2-runtime --name oracle run_oracle.sh
    fi
}

function main {
        echo "---- Starting oracle -----"
        isFirstTime
            if [ "$FIRSTTIME" = "true" ]; then
                echo "----- Starting oracle initial set up -----"
                cd ~/omoc-node
                python3 scripts/setAddress.py
             fi
        runOracle
}

main