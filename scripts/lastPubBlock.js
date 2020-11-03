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

async function historyForCoinPair(web3, abi, contract, selected_oracles) {
    const ret = {};
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
    const {txs, blocks} = await helpers.getHistory(web3, startBlockNumber, currentBlock,
        tx => tx.to && tx.to.toLowerCase() === contract.options.address.toLowerCase());
    const block_map = blocks.reduce((acc, val) => {
        acc[val.number] = val.hash;
        return acc;
    }, {});
    const pr = (x, st, el) => (x.status ? colors.green(st) : colors.red(el || st));
    // instantiate
    const table = new Table({
        head: ["blocknumber", "timestamp", "message last pub block", "from", "price", "status", "blockHash", "Selected"]
    });
    let prev = new BigNumber(endBlockNumber.toString());
    for (const x of txs) {
        const args = fnDecoder.decodeFn(x.input);
        const d = new Date(x.timestamp * 1000).toISOString();
        if (args.signature === "switchRound()") {
            table.push([
                pr(x, x.blockNumber),
                pr(x, d),
                pr(x, "SWITCH ROUND"),
                pr(x, x.from),
                "SWITCH ROUND",
                pr(x, "SUCCESS", "FAILED"),
                "",
                ""
            ]);
        } else if (args.signature === "publishPrice(uint256,bytes32,uint256,address,uint256,uint8[],bytes32[],bytes32[])") {
            if (!block_map[args._blockNumber.toString()]) {
                const blk = await web3.eth.getBlock(args._blockNumber, false);
                block_map[blk.number] = blk.hash;
            }
            const block_hash = block_map[args._blockNumber.toString()];
            const selected = helpers.select_next(block_hash, selected_oracles)
            const printable_selected = selected.map(x => x.substr(0, 4) + "..." + x.substr(-3)).toString()
            ret[block_hash] = selected[0];
            table.push([
                pr(x, x.blockNumber),
                pr(x, d),
                pr(x, args._blockNumber.toString(10) + " - " + prev.sub(args._blockNumber).toString(10)),
                pr(x, x.from),
                web3.utils.fromWei(args._price.toString()),
                pr(x, "SUCCESS", "FAILED"),
                block_hash.substr(0, 6) + "...",
                (selected[0] === x.from ? printable_selected :
                    (x.status ? colors.blue(printable_selected) : colors.red(printable_selected))),
            ]);
            if (x.status) prev = args._blockNumber;
        } else {
            console.log("Invalid signature", args.signature);
        }
    }
    console.log("" + table);
    return ret;
}

async function get_oracle_info_list(info_cache, oracle_manager_methods, coin_pair_price_methods) {
    const roundInfo = await coin_pair_price_methods.getRoundInfo().call();
    const selected_oracles = roundInfo.selectedOracles;
    const oracle_info_list = [];
    for (const s of selected_oracles) {
        if (!info_cache[s]) {
            const info = await oracle_manager_methods.getOracleRegistrationInfo(s).call();
            info_cache[s] = {stake: info.stake, addr: s}
        }
        oracle_info_list.push(info_cache[s]);
    }
    return oracle_info_list;
}

async function principal(conf) {
    const {web3, coinPairPrice, oracleManager} = conf;
    const oracle_manager_methods = oracleManager.contract.methods;
    const coinCant = await oracle_manager_methods.getCoinPairCount().call();
    const info_cache = {};
    for (let i = 0; i < coinCant; i++) {
        const coinPair = await oracle_manager_methods.getCoinPairAtIndex(i).call();
        const addr = await oracle_manager_methods.getContractAddress(coinPair).call();
        console.log("-".repeat(20), colors.green(helpers.coinPairStr(coinPair) + " -> " + addr));
        coinPairPrice.contract.options.address = addr;
        const oracle_info_list = await get_oracle_info_list(info_cache,
            oracle_manager_methods,
            coinPairPrice.contract.methods);
        console.log("SELECTED ORACLES", oracle_info_list);
        // TODO: Instead of searching block for every coinpair, search for all of them at once
        const r = await historyForCoinPair(web3, coinPairPrice.abi, coinPairPrice.contract, oracle_info_list);
        console.log("SELECTION ORDER", r);
        const selected_addresses = oracle_info_list.map(x => x.addr);
        console.log("STATS", Object.values(r)
            .reduce((acc, val) => {
                const idx = selected_addresses.indexOf(val);
                if (!acc[idx]) acc[idx] = 0;
                acc[idx]++;
                return acc;
            }, {}));
    }
}

config.run(principal);
