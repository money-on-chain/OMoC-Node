#!/usr/bin/env bash
# Show the public URL of the oracle service.

set -Eeuo pipefail

trap 'STATUS=$?; echo "Error: script failed at line $LINENO (exit code: $STATUS)" >&2; exit "$STATUS"' ERR

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ENVFILE="$SCRIPT_DIR/env_oracle"

if [ ! -f "$ENVFILE" ] ; then
  echo "Couldn't find the env file ($ENVFILE)"
  exit 1
fi

if ! source "$ENVFILE"; then
  echo "Error: couldn't load the env file ($ENVFILE)" >&2
  exit 1
fi

if [ -z "${ORACLE_PORT:-}" ]; then
  echo "Error: ORACLE_PORT is missing or empty in $ENVFILE" >&2
  exit 1
fi

echo "Envfile: $ENVFILE"
echo "Oracle Port (ORACLE_PORT): $ORACLE_PORT"

# Obtain the public IP address reported by an external service.
if ! PUBLIC_IP=$(curl --silent --show-error --fail --max-time 10 \
    https://ifconfig.me/ip); then
  echo "Error: couldn't obtain the public IP address" >&2
  exit 1
fi

PUBLIC_IP=${PUBLIC_IP//$'\r'/}
PUBLIC_IP=${PUBLIC_IP//$'\n'/}

if [ -z "$PUBLIC_IP" ]; then
  echo "Error: the public IP service returned an empty response" >&2
  exit 1
fi

# IPv6 addresses must be enclosed in brackets when used in a URL.
if [[ "$PUBLIC_IP" == *:* ]]; then
  PUBLIC_URL="http://[$PUBLIC_IP]:$ORACLE_PORT"
else
  PUBLIC_URL="http://$PUBLIC_IP:$ORACLE_PORT"
fi

echo "Public oracle URL: $PUBLIC_URL"
