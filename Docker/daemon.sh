#!/bin/bash
echo "Starting oracle daemon"
docker run docker run --restart always --name omoc-node -v ./monitor:/monitor 
echo "Oracle has started and will be running when you turn off your computer"

