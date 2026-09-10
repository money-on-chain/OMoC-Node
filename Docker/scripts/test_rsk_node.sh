#!/usr/bin/env bash
# test_rsk_node.sh
# Test the RSK node by checking the current block number and measuring connection latency.

set -Eeuo pipefail

trap 'STATUS=$?; echo "Error: script failed at line $LINENO (exit code: $STATUS)" >&2; exit "$STATUS"' ERR

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ENVFILE="$SCRIPT_DIR/env_oracle"

if [ ! -f "$ENVFILE" ] ; then
  echo "Couldn't find the env file ($ENVFILE)"
  exit 1
fi

source "$ENVFILE"

if [ -z "${NODE_URL:-}" ]; then
  echo "Error: NODE_URL is missing or empty in $ENVFILE" >&2
  exit 1
fi

echo "Envfile: $ENVFILE"
echo "Network URL node (NODE_URL): $NODE_URL"

# Request the current block number from the node.
if ! RPC_RESPONSE=$(curl --silent --show-error --fail -X POST \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":{},"id":123}' \
    "$NODE_URL"); then
  echo "Error: couldn't obtain the block number from $NODE_URL" >&2
  exit 1
fi

if [ -z "$RPC_RESPONSE" ]; then
  echo "Error: received an empty response from $NODE_URL" >&2
  exit 1
fi

# Extract the hexadecimal block number from the JSON response.
BLOCK_NUMBER_HEX=$(echo "$RPC_RESPONSE" | jq -r '.result')

# Convert the hexadecimal value to decimal.
BLOCK_NUMBER=$(printf "%d" "$BLOCK_NUMBER_HEX")

echo "Block number: $BLOCK_NUMBER"

# Measure TCP connection latency and get the remote IP.
CONNECTION_INFO=$(curl -o /dev/null -s -w '%{remote_ip} %{time_connect}' "$NODE_URL")
REMOTE_IP=$(echo "$CONNECTION_INFO" | awk '{print $1}')
CONNECT_TIME=$(echo "$CONNECTION_INFO" | awk '{print $2}')
CONNECT_TIME_MS=$(awk -v t="$CONNECT_TIME" 'BEGIN {printf "%.2f", t * 1000}')

echo "Remote IP: $REMOTE_IP"
echo "Connection latency: ${CONNECT_TIME_MS} ms"
