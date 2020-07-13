#Upgrading from release 0.6.0 to 0.7.0

Running the following commands you will upgrade your server.


1. Stop services:

	`supervisorctl stop backend ; supervisorctl stop oracle`
	
2. Update code to latest version:

	`cd ~/OMoC-Node/ ; git pull`

3. Run the configuration/upgrade script:

	`. scripts/upgrade_070.sh`

4. Start services:

	`supervisorctl start backend ; supervisorctl start oracle`

5. Check if oracle and backend service's are running:

	`supervisorctl status`

6. We also changed the contracts, so you'll need to subscribe into a new DAPP:

	Visit the [new DAPP version](https://oracles.testnet.moneyonchain.com/) (at the same URL) and [register your Oracle](./step04.html) (as you did before).
