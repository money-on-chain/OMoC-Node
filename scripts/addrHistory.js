/*
    This script list all the transactions in the last blocks from some address
    Example: ```NETWORK=ganche node addrHistory.js address number_of_block_to_search_for```

 */
const helpers = require('./helpers');
const colors = require('colors/safe');
const BigNumber = require('bignumber.js');
const Table = require('cli-table');
const config = require('./CONFIG');
const Web3 = require('web3');

const ARGS = helpers.getScriptArgs(__filename);
const ADDR = Web3.utils.toChecksumAddress(ARGS[0]);
const DEPTH_IN_BLOCKS = isNaN(ARGS[1]) ? 70 : parseInt(ARGS[1]);
console.log("DEPTH_IN_BLOCKS", DEPTH_IN_BLOCKS);


async function historyForAddr(web3, addr) {
    const currentBlock = parseInt(await web3.eth.getBlockNumber());
    const startBlockNumber = Math.max(0, currentBlock - DEPTH_IN_BLOCKS);
    console.log("-".repeat(10), colors.green("current block " + currentBlock
        + " search txs from " + startBlockNumber + " to " + currentBlock
    ));
    const {txs} = await helpers.getHistory(web3, startBlockNumber, currentBlock,
        tx => tx.from && tx.from.toLowerCase() == addr.toLowerCase());
    const pr = (x, st, el) => (x.status ? colors.green(st) : colors.red(el || st));
    // instantiate
    const table = new Table({
        head: ["timestamp", "blocknumber", "gas", "gasUsed", "deltaGas", "contractDeploy (blue) / to (green)", "hash", "nonce",]
    });
    txs.forEach(x => {
        const d = new Date(x.timestamp * 1000).toISOString();
        table.push([
            pr(x, d),
            pr(x, x.blockNumber),
            pr(x, x.gas),
            // pr(x, x.cumulativeGasUsed),
            pr(x, x.gasUsed),
            pr(x, Web3.utils.toBN(x.gas).sub(Web3.utils.toBN(x.gasUsed)).toString()),
            x.contractAddress ? colors.blue(x.contractAddress) : colors.green(x.to),
            pr(x, x.hash),
            pr(x, x.nonce),
        ]);
    });
    console.log("" + table);
}

async function principal(conf) {
    const {web3} = conf;
    await historyForAddr(web3, ADDR);
}

config.run(principal);
