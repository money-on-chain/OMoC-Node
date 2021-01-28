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
        cd /omoc-node/servers
        touch .env
        cp dotenv_example .env
    fi
}

function main {
        echo "---- Starting oracle -----"
        isFirstTime
            if [ "$FIRSTTIME" = "true" ]; then
                echo "----- Starting oracle initial set up -----"
                cd /omoc-node
                python3 scripts/setAddress.py
             fi
        cd /omoc-node/servers
        pm2-runtime --name oracle run_oracle.sh
}

main