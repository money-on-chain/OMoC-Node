#!/usr/bin/env bash
# rebuild_docker_instance.sh

IMG="moneyonchain/omoc_node:latest"
NAME="omoc-node"
ENVFILE="env_oracle"
LOGPARAMS="--log-driver json-file --log-opt max-size=50M --log-opt max-file=15 --log-opt compress=true"
PARAMS="--restart always -p 5556:5556 $LOGPARAMS"

if [ ! -f "$ENVFILE" ] ; then
  echo "Couldn't find the env file ($ENVFILE)"
  exit 1
fi

term () {
  fold -w70 | awk '{print "  > "$0}'
}

docker_run () {
  echo
  echo $1 ...
  shift
  {
    echo ~$ docker $@
    echo
    docker $@ 2>&1
  } | term
}

docker_run "Pull the docker image" pull $IMG
docker_run "Show docker instances" ps

IMG_NO_TAG=$(echo "$IMG" | awk -F ':' '{print $1}')
CID=$(docker ps | grep $IMG_NO_TAG | awk '{print $1}')

if [ -z "$CID" ] ; then
  CID="$NAME"
fi

docker_run "Stop $CID docker instance" stop $CID
docker_run "Remove $CID docker instance" rm $CID
docker_run "Run/Create/Start $NAME docker instance" run -d $PARAMS --name $NAME --env-file="$ENVFILE" $IMG

sleep 3

docker_run "Show docker instances" ps
docker_run "Show some $NAME docker instance log" logs -n 10 -t $NAME

echo
echo Done!.
echo "Run 'docker logs -n 1 -t -f $NAME' to see more log."
echo
