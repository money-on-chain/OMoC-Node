#!/usr/bin/env bash
# update.sh

ENVFILE="env_oracle"
URL=https://raw.githubusercontent.com/money-on-chain/OMoC-Node/master/Docker/rebuild_and_run_docker.sh
FILENAME="rebuild_and_run_docker.sh"

if [ ! -f "$ENVFILE" ] ; then
  echo "Couldn't find the env file ($ENVFILE)"
  exit 1
fi

curl -o "$FILENAME" "$URL" 
chmod +x "$FILENAME"
bash "$FILENAME"
