#!/usr/bin/env bash

TAG=""
LOCAL_NAME="omoc_node"
PUSH_NAME="omoc_node"
IS_BETA=0
NAMESPACES=(moneyonchain ghcr.io/money-on-chain)

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
: "${LOCAL_NAME:=omoc_node}"
: "${PUSH_NAME:=omoc_node}"

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
docker build -t $LOCAL_NAME:$TAG -f Docker/Dockerfile .
if [ "$IS_BETA" -ne 1 ]; then
    docker tag $LOCAL_NAME:$TAG $LOCAL_NAME:latest
fi
IMG_ID=$(docker images --format '{{.ID}}' $LOCAL_NAME:$TAG)
IMG_SIZE=$(docker images --format '{{.Size}}' $LOCAL_NAME:$TAG)

# Tags
docker tag $LOCAL_NAME:$TAG $PUSH_NAME:$TAG
if [ "$IS_BETA" -ne 1 ]; then
    docker tag $LOCAL_NAME:$TAG $PUSH_NAME:latest
fi
for NAMESPACE in "${NAMESPACES[@]}"; do
    docker tag $LOCAL_NAME:$TAG $NAMESPACE/$PUSH_NAME:$TAG
    if [ "$IS_BETA" -ne 1 ]; then
        docker tag $LOCAL_NAME:$TAG $NAMESPACE/$PUSH_NAME:latest
    else
        docker tag $LOCAL_NAME:$TAG $NAMESPACE/$PUSH_NAME:beta
    fi
done

# Show local images
echo ""
echo "Local images ($IMG_ID: $IMG_SIZE):"
docker images --format '---> {{.Repository}}:{{.Tag}}|{{.ID}}' | grep $IMG_ID  | cut -d'|' -f1

# Push
echo ""
echo "To upload the image you must run:"
for NAMESPACE in "${NAMESPACES[@]}"; do
    echo "~$ docker push $NAMESPACE/$PUSH_NAME:$TAG"
    if [ "$IS_BETA" -ne 1 ]; then
        echo "~$ docker push $NAMESPACE/$PUSH_NAME:latest"
    else
        echo "~$ docker push $NAMESPACE/$PUSH_NAME:beta"
    fi
done

# END.
echo ""
