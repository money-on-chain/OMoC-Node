#!/usr/bin/env bash

TAG=""
NAME="moneyonchain/omoc_node"
IS_BETA=0

# Exit immediately if a command exits with a non-zero status
set -e 

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Go one level up from the script's directory
TARGET_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$TARGET_DIR"

# Get version
PCODE="$(grep "VERSION" servers/common/settings.py | head -n 1 | cut -d '#' -f1); print(VERSION)"
VERSION=$(python -c "$PCODE")

# Assign VERSION to TAG only if TAG is empty or unset
: "${TAG:=$VERSION}"

# Default NAME if NAME is empty or unset
: "${NAME:=omoc_node}"

# Verify is beta
if [ "$IS_BETA" -eq 1 ]; then
    if ! echo "$TAG" | grep -iq "b"; then
        TAG="${TAG}-beta"
    fi
else
    if echo "$TAG" | grep -iq "b"; then
        IS_BETA=1
    fi
fi

# Build
docker build -t $NAME:$TAG -f Docker/Dockerfile .
if [ "$IS_BETA" -ne 1 ]; then
    docker tag $NAME:$TAG $NAME:latest
fi

# Push
echo ""
echo "To upload the image you must run:"
echo "docker push $NAME:$TAG"
if [ "$IS_BETA" -ne 1 ]; then
    echo "docker push $NAME:latest"
fi
echo ""





