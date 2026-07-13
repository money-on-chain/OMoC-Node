#!/bin/bash

CONF_FILE="/etc/supervisor/supervisord.conf"

if [ "$NOT_RUN_MPS_API_SERVER" != true ] ; then
    AUTOSTART="true"    
else
    AUTOSTART="false"
fi

cat > "$CONF_FILE" <<EOF

[supervisord]
nodaemon=true
environment=PATH="/opt/venv/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
user=root
logfile=/dev/stdout
logfile_maxbytes=0

[program:redis]
command=redis-server --save "" --appendonly no
autostart=$AUTOSTART
autorestart=$AUTOSTART
stdout_logfile=/dev/stdout
stderr_logfile=/dev/stderr
stdout_logfile_maxbytes=0
stderr_logfile_maxbytes=0
priority=10
startsecs=10

[program:moc_prices_source_api]
command=/app/moc_prices_source/.venv/bin/python /app/moc_prices_source/.venv/bin/moc_prices_source_api
autostart=$AUTOSTART
autorestart=$AUTOSTART
stdout_logfile=/dev/stdout
stderr_logfile=/dev/stderr
stdout_logfile_maxbytes=0
stderr_logfile_maxbytes=0
priority=20

[program:omoc]
directory=/app/omoc_node
environment=TZ="UTC",CONTRACT_ROOT_FOLDER="./"
command=/app/omoc_node/.venv/bin/python -m oracle.src.main
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stderr_logfile=/dev/stderr
stdout_logfile_maxbytes=0
stderr_logfile_maxbytes=0
priority=20

EOF

/usr/bin/supervisord -c "$CONF_FILE"
