#Setup your machine and run the service

We will setup your machine to run the Oracle service.
The Oracle service will inform the smart contracts about the current prices of the coinPairs (BTCUSD, RIFBTC).

The following commands will set up your machine and start the services.


1. Go to the OMoC folder an update your repo.

	`cd OMoC-Node` </br>
	`git pull`

2. We encourage you to run a RSK node. Despite of public nodes of rsk could be used, they are not going to work as expected. Follow the RSK node installation documentation and provide the URL of your node in the next step. Docs: https://developers.rsk.co/rsk/node/install/.

3. Configure the oracle data following the instructions in the script:

	`python3 scripts/setAddress.py`

4. Enable supervisor as a service when starting the machine:

	`sudo systemctl enable supervisor.service`
5. Start supervisor:

	`sudo supervisord`
6. Check if the oracle service is running:

	`supervisorctl status`
	
7. Get RBTC in RSK_testnet. If you already have stake in the system, you can skip this step.

	Visit [https://faucet.rsk.co/](https://faucet.rsk.co/) and complete the form to get Ethers for your Oracle's address.

Now you can register your oracle and interact with the smart contract using the Dapp. To do that go to the [next step](./step04.html)




