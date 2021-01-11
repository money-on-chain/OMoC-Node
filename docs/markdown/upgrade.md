#Upgrading from release 0.7.0 to 1.0.0

Running the following commands you will upgrade your server.

##### Clarification: 

In case you only need to update logs files, please go to the fourth step and at the end of the fifth step, just restart services.

1. Stop services:

    `supervisorctl stop backend ; supervisorctl stop oracle`
    
2. Update code to latest version:

    `cd ~/OMoC-Node/ ; git pull`

3. Run the configuration/upgrade script:

    `. scripts/upgrade_100.sh`

4. Update logrotate configuration: 

	`rm -r /etc/logrotate.d/supervisor.conf `
	
    `nano /etc/logrotate.d/supervisor.conf `
	
	* Paste the following configuration file: 

	![LogRotateConf](./images/logrotate.png)


5. Modify supervisor configuration:

    `cd /etc/supervisor/conf.d/`

	* Both in oracle.conf and in backend.conf add the following lines:

	![SupervisorLogs](./images/supervisor.png)

6. Start services:

    `supervisorctl start backend ; supervisorctl start oracle`

7. Check if oracle and backend service's are running:

    `supervisorctl status`

8. We also changed the contracts, so you'll need to subscribe into a new DAPP:

    Visit the [new DAPP version](https://moc-test-alpha.moneyonchain.com/) (at the same URL) and [register your Oracle](./step04.html) (as you did before).
