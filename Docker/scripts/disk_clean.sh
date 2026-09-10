#!/usr/bin/env bash
# disk_clean.sh
# Clean up disk space by removing unnecessary packages, logs, and Docker logs.

PREV_MB=$(df -m / | awk 'NR==2{print $4}')

# Clean .deb packages that are no longer required
echo
echo "Get rid of .deb packages that are no longer required..."
echo
sudo apt-get -y autoremove
apt-get -y autoclean
sudo apt-get -y clean

# Log clean
echo
echo "Logrotate clean..."
echo
find /var/log -type f -name '*.[0-99].gz' -exec rm {} +


# Docker log clean
echo
echo "Docker's log clean..."
echo
truncate -s 0 /var/lib/docker/containers/**/*-json.log

# Summary
MB=$(df -m / | awk 'NR==2{print $4}')
DELTA_MB=$((PREV_MB-MB))
echo
echo "Summary"
echo "======="
echo
echo "Save $DELTA_MB MB"
echo
df -H /
echo
