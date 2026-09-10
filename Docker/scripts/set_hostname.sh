#!/usr/bin/env bash
# set_hostname.sh
# Set the hostname of the machine.

set -Eeuo pipefail

trap 'STATUS=$?; echo "Error: script failed at line $LINENO (exit code: $STATUS)" >&2; exit "$STATUS"' ERR

# Debe ejecutarse como root
if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root."
    exit 1
fi

NEW_HOSTNAME="${1:-omoc-node}"

echo "Changing hostname to: ${NEW_HOSTNAME}"

# Change the hostname immediately and persistently.
sudo hostnamectl set-hostname "${NEW_HOSTNAME}"

# Update /etc/hosts so the local hostname resolves correctly.
if grep -qE '^127\.0\.1\.1' /etc/hosts; then
    sudo sed -i -E \
        "s/^127\.0\.1\.1[[:space:]].*/127.0.1.1 ${NEW_HOSTNAME}/" \
        /etc/hosts
else
    echo "127.0.1.1 ${NEW_HOSTNAME}" | sudo tee -a /etc/hosts >/dev/null
fi

# On EC2, cloud-init may overwrite the hostname on the next boot.
# Prevent cloud-init from changing the configured hostname.
sudo mkdir -p /etc/cloud/cloud.cfg.d
echo "preserve_hostname: true" | \
    sudo tee /etc/cloud/cloud.cfg.d/99-preserve-hostname.cfg >/dev/null

echo "Hostname successfully changed to: ${NEW_HOSTNAME}"
echo "Please relogin for all changes to take effect."
