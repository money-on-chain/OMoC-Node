#TroubleShooting

Some things that can go wrong when setting up your MoC Oracle


1. Connection to the RSK node:

Looking into your `/var/log/supervisor/oracle-stderr---supervisor-*.log` log file you might find something like:

```
WARNING:  Error getting param from blockchain 'ORACLE_MANAGER_ADDR' -> BCError(state='error', hash=None, error="HTTPConnectionPool(host='moc-rsk-node-testnet.moneyonchain.com', port=4454): Max retries exceeded with url: / (Caused by ConnectTimeoutError(<urllib3.connection.HTTPConnection object at 0x7fa94b26a610>, 'Connection to moc-rsk-node-testnet.moneyonchain.com timed out. (connect timeout=30)'))")
ERROR:    Oracle loop Error getting coin pairs BCError(state='error', hash=None, error="HTTPConnectionPool(host='moc-rsk-node-testnet.moneyonchain.com', port=4454): Max retries exceeded with url: / (Caused by ConnectTimeoutError(<urllib3.connection.HTTPConnection object at 0x7fa94b1a0410>, 'Connection to moc-rsk-node-testnet.moneyonchain.com timed out. (connect timeout=30)'))")
ERROR:    SchedulerSupportersLoop error getting is_ready_to_distribute BCError(state='error', hash=None, error="HTTPConnectionPool(host='moc-rsk-node-testnet.moneyonchain.com', port=4454): Max retries exceeded with url: / (Caused by ConnectTimeoutError(<urllib3.connection.HTTPConnection object at 0x7fa94b259e10>, 'Connection to moc-rsk-node-testnet.moneyonchain.com timed out. (connect timeout=30)'))")
```

Which means your Oracle can not read the contract registry. To check if you have connectivity you can run:

```
NODO="<RSK-NODE-URL>:<PORT>" ; curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_blockNumber", "params": {},  "id":123}' $NODO | jq .result | tr -d '"' | awk '{print "printf \"%d\\n\" "$0}' | sh
```

If your server can access the node you'll get in return the block number. If you don't get a reply it means the node is unreachable from the machine.

It is important to flag you'll need the jq (Json CLI parser) to run above command. Alternatively you can run:

```
NODO="https://public-node.testnet.rsk.co:443" ; curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_blockNumber", "params": {},  "id":123}' $NODO
```

And will get the JSON reply which is in HEX and harder to read. Plus in this example we've used the RSK public node.

2. Server port (ie. 5556) not open:

You should be able to reach the oracle from the internet in the designated port. So if you do:

```
curl http://<YOUR-IP>:5556
```

It will reply some error, but it should at least reply. It usually goes something like:

```
"The request was not made by a selected oracle."
```

And might continue with your local IP. This means the port is open and reachable which is needed for the Oracle to work.
