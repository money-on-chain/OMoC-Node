#!/usr/bin/env bash
# rebuild_docker_instance.sh

IMG="moneyonchain/omoc_node:latest"

echo
echo Pull the docker image ...
echo "docker pull $IMG"
docker pull $IMG

echo
echo Stop omoc-node docker instance...
echo "docker stop omoc-node"
docker stop omoc-node

echo
echo Remove omoc-node docker instance...
echo "docker rm omoc-node"
docker rm omoc-node

echo
echo Run omoc-node docker instance...
echo "docker run -d --restart always --log-driver json-file --log-opt max-size=50M --log-opt max-file=15 --log-opt compress=true -p 5556:5556 --name omoc-node --env-file=/home/ubuntu/env_oracle $IMG"
docker run -d --restart always --log-driver json-file --log-opt max-size=50M --log-opt max-file=15 --log-opt compress=true -p 5556:5556 --name omoc-node --env-file=/home/ubuntu/env_oracle $IMG

sleep 3

echo
echo Show docker instances...
echo "docker ps"
docker ps

echo
echo Show some omoc-node docker instance log...
echo "docker logs -n 10 -t omoc-node"
docker logs -n 10 -t omoc-node


echo
echo Done!.
echo "Run 'docker logs -n 1 -t -f omoc-node' to see more log."
