# `$ disk_clean.sh`

A script tool to clean an Ubuntu Linux instance intended to run via Docker an oMoC Node.

## Example of use

Must be run as root

```shell
root@server:~# curl https://raw.githubusercontent.com/money-on-chain/OMoC-Node/scripts/disk_clean.sh | bash
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   613  100   613    0     0   3111      0 --:--:-- --:--:-- --:--:--  3095

Get rid of .deb packages that are no longer required...

Reading package lists... Done
Building dependency tree       
Reading state information... Done
The following packages will be REMOVED:
  linux-aws-5.4-headers-5.4.0-1096 linux-aws-5.4-headers-5.4.0-1097 linux-aws-5.4-headers-5.4.0-1099 linux-aws-5.4-headers-5.4.0-1100
0 upgraded, 0 newly installed, 4 to remove and 71 not upgraded.
After this operation, 291 MB disk space will be freed.
(Reading database ... 219919 files and directories currently installed.)
Removing linux-aws-5.4-headers-5.4.0-1096 (5.4.0-1096.104~18.04.1) ...
Removing linux-aws-5.4-headers-5.4.0-1097 (5.4.0-1097.105~18.04.1) ...
Removing linux-aws-5.4-headers-5.4.0-1099 (5.4.0-1099.107~18.04.1) ...
Removing linux-aws-5.4-headers-5.4.0-1100 (5.4.0-1100.108~18.04.1) ...
Reading package lists... Done
Building dependency tree       
Reading state information... Done

Logrotate clean...


Docker's log clean...


Summary
=======

Save -547 MB

Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p1  8.3G  5.5G  2.9G  66% /

root@server:~#
```

