/*
This script was used during a demo and it is meant to be used with ganache, it
    adds earnings to the supporters smart contract, mine blocks each second and rotates
    the rounds when needed.
    Example:  ```NETWORK=ganache node supporters_pay.js```

 */

const Web3 = require('web3');
const helpers = require('./helpers');
const config = require('./CONFIG');



async function principal(conf) {
    const {web3, coinPairPrice, oracleManager} = conf;

    const cprMethods = oracleManager.contract.methods;
    const coinCant = await cprMethods.getCoinPairCount().call();
    for (let i = 0; i < coinCant; i++) {
        const coinPair = await cprMethods.getCoinPairAtIndex(i).call();
        const addr = await cprMethods.getContractAddress(coinPair).call();

        console.log("-".repeat(20), helpers.coinPairStr(coinPair) + " -> " + addr);
        coinPairPrice.contract.options.address = addr;
        const contract = coinPairPrice.contract;
        const lpbm = contract.methods.lastPublicationBlock
            ? contract.methods.lastPublicationBlock
            : contract.methods.getLastPublicationBlock;

        const lastPubBlock = await lpbm().call();
        const blk = await web3.eth.getBlock(lastPubBlock);
        const blockHash = blk.hash;
        const roundInfo = await contract.methods.getRoundInfo().call();
        const selectedOracles = roundInfo.selectedOracles;
        const oracles = []
        for (const addr of selectedOracles) {
            const oinfo = await cprMethods.getOracleRegistrationInfo(addr).call();
            oracles.push({addr, stake: oinfo.stake});
        }
        console.log("Assuming that selected oracles doesn't change!!!!")
        console.log("block hash", blockHash);
        console.log("selected oracles", oracles);
        console.log("select order", helpers.select_next(blockHash, oracles));
    }
}

config.run(principal);
