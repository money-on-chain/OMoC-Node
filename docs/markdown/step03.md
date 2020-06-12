#Setup your machine and run the service

We will setup your machine to run the Oracle and Backend services.
The Oracle service will inform the smart contracts about the current prices of the coinPairs (BTCUSD, RIFBTC).
The Backend service will send emails with the content of the logs from Oracle service to an specific email account from a SMTP email account.

The following commands will set up your machine and start the services.


1. Go to the OMoC folder an update your repo.

	`cd OMoC-Node` </br>
	`git pull`
	
2. Configure the data of oracles and SMTP email following the instructions in the script:

	`python3 scripts/setAddress.py`

3. Enable supervisor as a service when starting the machine:

	`sudo systemctl enable supervisor.service`
4. Start supervisor:

	`sudo supervisord`
5. Check if oracle and backend service's are running:

	`supervisorctl status`
	
6. Get RBTC in RSK_testnet 

	Visit [https://faucet.rsk.co/](https://faucet.rsk.co/) and complete the form to get Ethers for your Oracle's address.

Now you can register your oracle and interact with the smartcontract using the Dapp. To do that go to the [next step](./step04.html)



