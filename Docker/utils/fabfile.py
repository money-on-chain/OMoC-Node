import os, sys
from datetime import datetime, timedelta
from fabric import task, Connection
from invoke import Exit
from tabulate import tabulate



# Directory to save logs locally (on the machine where 'fab' is run)
LOCAL_LOG_DIR = "./"
os.makedirs(LOCAL_LOG_DIR, exist_ok=True)


def get_hostname(c: Connection):
    """Retrieve the hostname of the remote connection."""    
    if not getattr(c, "host", None):
        raise Exit(
            "You must specify a host. e.g.: fab -H server1,server2 <task-name>",
            code=1
        )    
    try:
        result = c.run('hostname', hide=True)
        hostname =  result.stdout.strip()
    except Exception as e:
        hostname = None
    return f"{hostname} ({c.host})" if hostname else c.host


def run_sudo(command, c: Connection, sudo_user="ubuntu", hide=False):
    cmd = f"sudo -u {sudo_user} {command}"
    if hide==False:
        print(f"$ {cmd}")
    return c.run(cmd, hide=hide)


def get_used_mb(c: Connection, sudo_user="ubuntu"):
    result = run_sudo("df -m /", c, sudo_user="ubuntu", hide=True)
    return int([l for l in result.stdout.split('\n') if l.strip()][-1].split()[2])


@task(help={
    'minutes': "Number of minutes in the past from which to retrieve logs (default: 60)",
    'sudo_user': "Username to use with sudo commands on the remote host (default: ubuntu)"
})
def fetch_logs(c, minutes=60, sudo_user="ubuntu"):
    """
    Retrieve Docker logs from all running containers on a remote host from the last `minutes` interval and save them locally.
    """

    hostname = get_hostname(c)
    now = datetime.utcnow()
    since_time_dt = now - timedelta(minutes=int(minutes))
    timestamp_str = now.strftime('%Y-%m-%d_%Hh%Mm')
    since_time = since_time_dt.isoformat() + "Z"

    try:        
        result = c.run(f"sudo -u {sudo_user} docker ps --format '{{{{.Names}}}}'", hide=True)
        container_names = result.stdout.strip().splitlines()

        if not container_names:
            print(f"⚠️  No running containers found on {hostname} ({c.host})")
            return

        for container in container_names:
            log_prefix = f"{timestamp_str}_{hostname.split()[0]}_{container}"
            stdout_path = os.path.join(LOCAL_LOG_DIR, log_prefix + ".out.log")
            stderr_path = os.path.join(LOCAL_LOG_DIR, log_prefix + ".err.log")

            print(f"Fetching logs from {hostname} for container '{container}' since the last {minutes} minutes")

            try:
                command = f'sudo -u {sudo_user} docker logs --since="{since_time}" --timestamps {container}'
                log_result = c.run(command, hide=True)

                with open(stdout_path, 'w') as f_out:
                    f_out.write(log_result.stdout)

                with open(stderr_path, 'w') as f_err:
                    f_err.write(log_result.stderr)

                print(f"✅ Stdout saved to {stdout_path}")
                print(f"✅ Stderr saved to {stderr_path}")
            except Exception as e:
                print(f"❌ Error retrieving logs from container '{container}' on {hostname}: {e}")

    except Exception as e:
        print(f"❌ Error retrieving container list from {hostname}: {e}")


@task(help={
    'sudo_user': "Username to use with sudo commands on the remote host (default: ubuntu)"
})
def container_status(c, sudo_user="ubuntu"):
    """Show the status of all Docker containers on the remote host."""
    hostname = get_hostname(c)
    try:
        print(f"\n📦 Listing Docker containers on {hostname}\n")
        result = c.run(
            f"sudo -u {sudo_user} docker ps -a --format 'table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Image}}}}'",
            hide=False
        )
    except Exception as e:
        print(f"❌ Error retrieving container status on {hostname}: {e}")


@task(help={
    'sudo_user': "Username to use with sudo commands on the remote host (default: ubuntu)",
    'grep_opts': "Additional grep options to customize filtering (default: passes all, excludes sensitive lines)"
})
def show_env_oracle(c, sudo_user="ubuntu", grep_opts=""):
    """Display the contents of the env_oracle file in the user's home directory, excluding lines with 'private' or 'key'."""
    hostname = get_hostname(c)
    try:
        print(f"\n🔍 Showing contents of env_oracle for {hostname} (excluding private/key lines)\n")
        base_command = f"grep -v -iE 'private|key' /home/{sudo_user}/env_oracle"
        if grep_opts:
            base_command = f"grep {grep_opts} /home/{sudo_user}/env_oracle | grep -v -iE 'private|key'"
        result = c.run(f"sudo -u {sudo_user} bash -c \"{base_command}\"", hide=False)
    except Exception as e:
        print(f"❌ Error displaying env_oracle on {hostname}: {e}")


@task(help={
    'sudo_user': "Username to use with sudo commands on the remote host (default: ubuntu)"
})
def container_stop(c, sudo_user="ubuntu"):
    """Stop all Docker containers on the remote host."""
    hostname = get_hostname(c)
    try:
        print(f"\n📦 Stop Docker containers on {hostname}\n")
        result = c.run(
            f"sudo -u {sudo_user} docker stop omoc-node",
            hide=False
        )
    except Exception as e:
        print(f"❌ Error stoping container on {hostname}: {e}")


@task(help={
    'sudo_user': "Username to use with sudo commands on the remote host (default: ubuntu)",
    'tag': "Docker image tag to pass to the rebuild script (default: latest)"
})
def run_rebuild_script(c, sudo_user="ubuntu", tag="latest"):
    """Execute rebuild_and_run_docker.sh from the ubuntu user's home directory."""
    hostname = get_hostname(c)
    try:
        print(f"\n🔧 Running rebuild_and_run_docker.sh as {hostname} using tag '{tag}'\n")
        command = (
            f"sudo -u {sudo_user} bash -c 'cd /home/{sudo_user} && ./rebuild_and_run_docker.sh {tag}'"
        )
        c.run(command, hide=False, pty=True)
    except Exception as e:
        print(f"❌ Error running rebuild_and_run_docker.sh on {c.host}: {e}")


@task(help={
    'sudo_user': "Username to use with sudo commands on the remote host (default: ubuntu)"
})
def disk_used(c, sudo_user="ubuntu"):
    """Show the disk used on the remote host."""
    hostname = get_hostname(c)
    kargs = {"c": c, "sudo_user": sudo_user}

    try:
        print(f"\n📦 Disk used on {hostname}\n")
        run_sudo("df -H /", **kargs)
        print()
    except Exception as e:
        print(f"❌ Error retrieving disk used on {hostname}: {e}")
        return


@task()
def disk_clean(c):
    """Clean disk on the remote host."""
    hostname = get_hostname(c)
    kargs = {"c": c, "sudo_user": "root"}

    try:
        first_used_mb = get_used_mb(**kargs)
        print(f"\n📦 Disk used on {hostname}\n")
        run_sudo("df -H /", **kargs, hide = False)
        print()
    except Exception as e:
        print(f"❌ Error retrieving disk used on {hostname}: {e}")
        return

    try:
        print(f"\n🧽 Get rid of .deb packages that are no longer required on {hostname}\n")
        run_sudo("apt-get -y autoremove", **kargs)
        run_sudo("apt-get -y autoclean", **kargs)
        run_sudo("apt-get -y clean", **kargs)
        print()
    except Exception as e:
        print(f"❌ Error on geting rid of .deb packages that are no longer required on {hostname}: {e}")

    try:
        print(f"\n🧽 Logrotate clean on {hostname}\n")
        run_sudo("find /var/log -type f -name '*.[0-99].gz' -print -exec rm {} +", **kargs)
        print()
    except Exception as e:
        print(f"❌ Error on Logrotate clean on {hostname}: {e}")

    try:
        print(f"\n🧽 Docker's log clean on {hostname}\n")
        run_sudo("find /var/lib/docker/containers/ -type f -name '*-json.log' -print -exec truncate -s 0 {} \;", **kargs)
        print()
    except Exception as e:
        print(f"❌ Error on Docker's log clean on {hostname}: {e}")

    try:
        print(f"\n🧽 Docker's images clean on {hostname}\n")
        run_sudo("docker image prune -a -f", **kargs)
        print()
    except Exception as e:
        print(f"❌ Error on Docker's images clean on {hostname}: {e}")

    try:
        last_used_mb = get_used_mb(**kargs)
        print(f"\n📦 Disk used on {hostname}\n")
        print(
            tabulate(
                [["Start with", first_used_mb, "MB"],
                 ["End with", last_used_mb, "MB"],
                 ["Save", first_used_mb - last_used_mb, "MB"]],
                 tablefmt="plain"))
        print()
        run_sudo("df -H /", **kargs)
        print()
    except Exception as e:
        print(f"❌ Error retrieving disk used on {hostname}: {e}")


if __name__ == "__main__":
    print("[!] This script is intended to be run using the 'fab' command, not directly.")
    print("To see the list of available tasks, run:")
    print("  fab -l")
    print("To get help on a specific task, run:")
    print("  fab --help <task-name>")
    sys.exit(1)
