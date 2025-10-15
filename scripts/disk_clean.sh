# apt clean
echo
echo "Get rid of .deb packages that are no longer required..."
echo
sudo apt-get -y autoremove
apt-get -y autoclean
sudo apt-get -y clean

# log clean
echo
echo "Logrotate clean..."
echo
find /var/log -type f -name '*.[0-99].gz' -exec rm {} +

# docker log clean
echo
echo "Docker's log clean..."
echo
truncate -s 0 /var/lib/docker/containers/**/*-json.log

# docker image prune
echo
echo "Docker's images clean..."
echo
docker image prune -a -f

# Summary
MB=$(df -m / | awk 'NR==2{print $4}')
DELTA_MB=$((PREV_MB-MB))
echo
echo "Summary"
echo "======="
echo
echo "Start with $PREV_MB MB"
echo "End with $MB MB"
echo "Save $DELTA_MB MB"
echo
df -H /
echo

