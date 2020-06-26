/*
This script queries the OracleManager for all the CoinPairPrice addresses then
    the block chain is searched for call to those contracts and transaction details are shown.
    Example: ```NETWORK=ganche node lastPubBlock.js number_of_block_to_search_for```

 */
const helpers = require('./helpers');
const txDecoder = require('ethereum-tx-decoder');
const colors = require('colors/safe');
const BigNumber = require('bignumber.js');
const Table = require('cli-table');
const config = require('./CONFIG');
const ARGS = helpers.getScriptArgs(__filename);
const DEPTH_IN_BLOCKS = isNaN(ARGS[0]) ? 70 : parseInt(ARGS[0]);
console.log("DEPTH_IN_BLOCKS", DEPTH_IN_BLOCKS);

async function historyForCoinPair(web3, abi, contract) {
    const fnDecoder = new txDecoder.FunctionDecoder(abi);
    const lpbm = contract.methods.lastPublicationBlock
        ? contract.methods.lastPublicationBlock
        : contract.methods.getLastPublicationBlock;

    const lastPubBlock = parseInt(await lpbm().call());
    const currentBlock = parseInt(await web3.eth.getBlockNumber());
    const startBlockNumber = Math.max(0, lastPubBlock - DEPTH_IN_BLOCKS);
    const endBlockNumber = Math.min(currentBlock, lastPubBlock + DEPTH_IN_BLOCKS);
    console.log("-".repeat(10), colors.green("current block " + currentBlock
        + " last pub block " + lastPubBlock
        + " search txs from " + startBlockNumber + " to " + endBlockNumber
    ));
    const txs = await helpers.getHistory(web3, startBlockNumber, currentBlock,
        tx => tx.to && tx.to.toLowerCase() == contract.options.address.toLowerCase());
    const pr = (x, st, el) => (x.status ? colors.green(st) : colors.red(el || st));
    // instantiate
    const table = new Table({
        head: ["timestamp", "blocknumber", "message last pub block", "from", "price", "status"]
    });
    let prev = new BigNumber(endBlockNumber.toString());
    txs.forEach(x => {
        const args = fnDecoder.decodeFn(x.input);
        const d = new Date(x.timestamp * 1000).toISOString();
        if (args.signature == "switchRound()") {
            table.push([
                pr(x, d),
                pr(x, x.blockNumber),
                pr(x, "SWITCH ROUND"),
                pr(x, x.from),
                "SWITCH ROUND",
                pr(x, "SUCCESS", "FAILED"),
            ]);
        } else if (args.signature == "publishPrice(uint256,bytes32,uint256,address,uint256,uint8[],bytes32[],bytes32[])") {
            table.push([
                pr(x, d),
                pr(x, x.blockNumber),
                pr(x, args.blockNumber.toString(10) + " - " + prev.sub(args.blockNumber).toString(10)),
                pr(x, x.from),
                web3.utils.fromWei(args.price.toString()),
                pr(x, "SUCCESS", "FAILED"),
            ]);
            if (x.status) prev = args.blockNumber;
        } else {
            console.log("Invalid signature", args.signature);
        }
    });
    console.log("" + table);
}

async function principal(conf) {
    const {web3, coinPairPrice, oracleManager} = conf;
    const cprMethods = oracleManager.contract.methods;
    const coinCant = await cprMethods.getCoinPairCount().call();
    for (let i = 0; i < coinCant; i++) {
        const coinPair = await cprMethods.getCoinPairAtIndex(i).call();
        const addr = await cprMethods.getContractAddress(coinPair).call();
        console.log("-".repeat(20), colors.green(helpers.coinPairStr(coinPair) + " -> " + addr));
        coinPairPrice.contract.options.address = addr;
        await historyForCoinPair(web3, coinPairPrice.abi, coinPairPrice.contract);
    }
}

config.run(principal);
