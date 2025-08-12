#!/usr/bin/env python3
import os
import subprocess
from datetime import datetime, timedelta

LOCAL_LOG_DIR = "./"
os.makedirs(LOCAL_LOG_DIR, exist_ok=True)

def fetch_local_logs(minutes=3600):
    now = datetime.utcnow()
    since_time_dt = now - timedelta(minutes=int(minutes))
    timestamp_str = now.strftime('%Y-%m-%d_%Hh%Mm')
    since_time = since_time_dt.isoformat() + "Z"

    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True, text=True
    )
    container_names = result.stdout.strip().splitlines()

    if not container_names:
        print("⚠️  No running containers found locally")
        return

    for container in container_names:
        log_prefix = f"{timestamp_str}_local_{container}"
        stdout_path = os.path.join(LOCAL_LOG_DIR, log_prefix + ".out.log")
        stderr_path = os.path.join(LOCAL_LOG_DIR, log_prefix + ".err.log")

        print(f"Fetching logs for container '{container}' since the last {minutes} minutes")

        try:
            cmd = [
                "docker", "logs",
                f"--since={since_time}",
                "--timestamps",
                container
            ]
            log_result = subprocess.run(cmd, capture_output=True, text=True)

            with open(stdout_path, 'w') as f_out:
                f_out.write(log_result.stdout)

            with open(stderr_path, 'w') as f_err:
                f_err.write(log_result.stderr)

            print(f"✅ Stdout saved to {stdout_path}")
            print(f"✅ Stderr saved to {stderr_path}")
        except Exception as e:
            print(f"❌ Error retrieving logs from container '{container}': {e}")

if __name__ == "__main__":
    fetch_local_logs(minutes=3600)