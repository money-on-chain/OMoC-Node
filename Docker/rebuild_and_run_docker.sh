#!/usr/bin/env bash
# rebuild_and_run_docker_instance.sh

IMG_TAG="latest"
IMG_BASE="moneyonchain/omoc_node"
NAME="omoc-node"
ENVFILE="env_oracle"
ALLOW_MULTIPLE_INSTANCES=0
LOGPARAMS="--log-driver json-file --log-opt max-size=50M --log-opt max-file=15 --log-opt compress=true"
DEFAULT_PORT=5556

# Load environment variables
if [ -f "$ENVFILE" ] ; then
  source "$ENVFILE"
else
  echo "Couldn't find the env file ($ENVFILE)"
  exit 1
fi

# Determine the port to use
PORT="${ORACLE_PORT}"
if [ -z "$PORT" ]; then
  PORT="${DEFAULT_PORT}"
fi

# Docker run parameters
PARAMS="--restart always -p ${PORT}:${PORT} ${LOGPARAMS}"

# Allow overriding only the tag via the first command line argument
if [ -n "$1" ]; then
  IMG_TAG="$1"
fi

# Full image name
IMG="${IMG_BASE}:${IMG_TAG}"

term () {
  fold -w70 | awk '{print "  > "$0}'
}

docker_run () {
  echo
  echo "$1" ...
  shift
  {
    echo ~$ docker "$@"
    echo
    docker "$@" 2>&1
  } | term
}

docker_run "Pull the docker image" pull "$IMG"
docker_run "Show docker instances" ps

if [[ $ALLOW_MULTIPLE_INSTANCES -eq 1 ]]; then
  CID="$NAME"
else
  IMG_NO_TAG=$(echo "$IMG" | awk -F ':' '{print $1}')
  CID=$(docker ps | grep "$IMG_NO_TAG" | awk '{print $1}')
fi

if [ -z "$CID" ] ; then
  CID="$NAME"
fi

docker_run "Stop $CID docker instance" stop "$CID"
docker_run "Remove $CID docker instance" rm "$CID"
docker_run "Run/Create/Start $NAME docker instance" run -d $PARAMS --name "$NAME" --env-file="$ENVFILE" "$IMG"

sleep 3

docker_run "Show docker instances" ps
docker_run "Show some $NAME docker instance log" logs -n 10 -t $NAME

echo
echo Done!.
echo "Run 'docker logs -n 1 -t -f $NAME' to see more log."
echo
