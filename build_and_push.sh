aws ecr get-login-password --region us-west-1 | docker login --username AWS --password-stdin 551471957915.dkr.ecr.us-west-1.amazonaws.com
docker build -t omoc_node -f Docker/Dockerfile .
docker tag omoc_node:latest 551471957915.dkr.ecr.us-west-1.amazonaws.com/omoc_node:latest
docker push 551471957915.dkr.ecr.us-west-1.amazonaws.com/omoc_node:latest