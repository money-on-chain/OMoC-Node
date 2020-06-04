#Dapp Guide

##Introduction

The intention of this document is to guide the user on how to interact with the dapp. For this reason, we assume that the reader has a knowledge of how the decentralized oracle system and its supporters work in general.


## Prerequisites
1. A complete understanding of the Oracle-Supporter interaction Setup and run your Oracle on a server.
2. Know the RSK address (0x...) and internet address of your Oracle (http://<IP>:5556).
3. Install Metamask in your browser.

###1) Login and Setup
####1.A) Add RSK-Test to Metamask and select that network.

Go to Network's menu, select Custom RPC and config the network with the following values and save:


![dapp](./images/GUIA03-01.png) 
![dapp](./images/GUIA03-02.png)


Network name: RSKTestnet

New RPC URL: https://public-node.testnet.rsk.co

ChainId: 31

####1.B) Get RBTC in RSK_testnet 
Visit [https://faucet.rsk.co/](https://faucet.rsk.co/) and complete the form to get Ethers.
####1.C) Enter the [dapp](http://oracles.testnet.moneyonchain.com)  and connect your metamask account. 

![dapp](./images/GUIA03-03.png)
   

###2) Registration (Mint->Allow->Register)
To register your Oracle, you will need to allow the contract to use your MoCTokens. To do that, go to the Oracle tab and subtab Registration, and mint MoC Token (will be assigned to your account). After that allow part or the total of your MoCToken to the contract. For the last step, register your Oracle using the Oracle address, the network address and stake the total or part of what you allow, in the allow step.

![dapp](./images/GUIA03-05.png)
![dapp](./images/GUIA03-06.png)

###3) Edit your Oracle's configuration
At the end of the Oracle Tab you will see all of the Oracles and you will be allowed to edit or delete only your Oracles.

![dapp](./images/GUIA03-07.png)
![dapp](./images/GUIA03-08.png)

If you chose to edit your oracle, you can change the internet Address, the Stake and/or the subscription to the coin-pairs.
For this example we will add subscription to BTCUSD
![dapp](./images/GUIA03-09.png)







