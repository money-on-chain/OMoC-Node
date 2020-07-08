const fs = require('fs');
const path = require('path');
const Web3 = require('web3');


async function printSingle(msg, contract, name) {
    try {
        const data = await contract.methods[name]().call();
        console.log(msg + name, data);
    } catch (e) {
        console.log(msg, "error getting", name, e.message)
    }
}

module.exports.printSingle = printSingle;

async function printProps(msg, data) {
    const props = data.abi.filter(x => (x["type"] == "function"
        && x["stateMutability"] == "view"
        && x["inputs"].length == 0
        && !x["payable"]
    ));
    if (msg.length > 0) console.log(msg);
    for (const p of props) {
        await printSingle("\t", data.contract, p["name"]);
    }

}

module.exports.printProps = printProps;

async function getAllOracles(oracle) {
    let addr = await oracle.methods.getRegisteredOracleHead().call();
    const ret = [];
    while (addr != "0x0000000000000000000000000000000000000000") {
        ret.push(addr);
        addr = await oracle.methods.getRegisteredOracleNext(addr).call();
    }
    return ret;
}

module.exports.getAllOracles = getAllOracles;


function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

module.exports.sleep = sleep;

function getContractData(jsonPath, contracts) {
    return Object.keys(contracts).reduce((acc, x) => {
        const data = JSON.parse(fs.readFileSync(path.join(jsonPath, contracts[x])));
        acc[x] = {data, abi: data.abi};
        return acc;
    }, {})
}

module.exports.getContractData = getContractData;

function getContracts(web3, contractData, addresses) {
    return Object.keys(addresses).reduce((acc, x) => {
        acc[x] = {
            addr: addresses[x],
            abi: contractData[x].abi,
            data: contractData[x],
            contract: new web3.eth.Contract(contractData[x].abi, addresses[x]),
        }
        return acc;
    }, {});
}

module.exports.getContracts = getContracts;

function coinPairStr(hex) {
    let str = "";
    for (let n = 0; n < hex.length; n += 2) {
        const ch = hex.substr(n, 2);
        if (ch == "0x" || ch == "00") {
            continue;
        }
        str += String.fromCharCode(parseInt(ch, 16));
    }
    return str;
}

module.exports.coinPairStr = coinPairStr;

function getScriptArgs(filename) {
    const scriptName = path.basename(filename);
    const script_in_args = process.argv.map(x => x.indexOf(scriptName) > 0);
    const idx = script_in_args.indexOf(true);
    if (idx < 0) {
        console.error("INVALID ARGS", script_in_args);
        process.exit();
    }
    return process.argv.splice(idx + 1);
}

module.exports.getScriptArgs = getScriptArgs;


async function getHistory(web3, fromBlk, toBlk, tx_filter) {
    const eth = web3.eth;
    const blocks = [];
    // Take in chunks of 100 blocks
    const CHUNK_SIZE = 100;
    for (let i = fromBlk; i < toBlk; i += CHUNK_SIZE) {
        const promises = []
        for (let j = 0; i + j < toBlk && j < CHUNK_SIZE; j++) {
            promises.push(eth.getBlock(i + j, true));
        }
        blocks.push(...await Promise.all(promises));
    }
    const f_blocks = blocks.filter(b => b != null && b.transactions != null)
        .map(b => b.transactions.map(x => ({...x, timestamp: b.timestamp})));
    const txs = [].concat.apply([], f_blocks).filter(tx_filter);
    const txMap = txs.reduce((acc, tx) => {
        acc[tx.hash] = tx;
        return acc;
    }, {});
    const receipts = await Promise.all(txs.map(x => eth.getTransactionReceipt(x.hash)));
    receipts.sort((a, b) => (b.blockNumber - a.blockNumber));
    return {txs: receipts.map(r => ({...r, ...txMap[r.transactionHash]})), blocks};
}

module.exports.getHistory = getHistory;

function select_next(last_block_hash, oracle_info_list) {
    if (oracle_info_list.length == 0) {
        return [];
    }

    if (oracle_info_list.length > 32) {
        throw  new Error('Cant have more than 32 oracles, the hash is 32 bytes long');
    }
    oracle_info_list.sort((a, b) => Web3.utils.toBN(b.stake).cmp(Web3.utils.toBN(a.stake)));
    const l1 = oracle_info_list.slice()
    let total_stake = Web3.utils.toBN(0);
    const l2 = []
    const stake_buckets = []
    const lbh_with_x = last_block_hash.startsWith("0x") ?
        last_block_hash :
        "0x" + last_block_hash
    const hb = Web3.utils.hexToBytes(lbh_with_x);
    const last_block_hash_as_int = Web3.utils.toBN(lbh_with_x);
    for (let idx = 0; idx < oracle_info_list.length; idx++) {
        // Take an element in a random place of l1 and push it to l2
        const sel_index = hb[idx] % l1.length
        const oracle_item = l1[sel_index];
        l1.splice(sel_index, 1)
        l2.push(oracle_item.addr)

        const stake = Web3.utils.toBN(oracle_item["stake"]);
        total_stake = total_stake.add(stake);
        stake_buckets.push(total_stake)
    }
    // Select from L2 according to stake weight
    // rnd_stake = int(last_block_hash, 16) % total_stake
    // i've got hexbytes string in hash, so:
    // const rnd_stake = last_block_hash_as_int.mod(total_stake);

    //const rnd_stake = last_block_hash_as_int.mod(total_stake);
    const max_int = Web3.utils.toBN('0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF');
    const hb_int = last_block_hash_as_int.xor(last_block_hash_as_int.shrn(16)).and(max_int)
    // bn don't support decimals => scale it up.
    const scale = Web3.utils.toBN("1" + "0".repeat(30));
    const rnd_stake = total_stake.mul(hb_int).mul(scale).div(max_int);
    // stake_buckets is a growing array of numbers, search the first bigger than rnd_stake
    for (let idx = 0; ; idx++) {
        if (idx === l2.length - 1 || rnd_stake.lte(stake_buckets[idx].mul(scale))) {
            // reorder the l2 array starting with idx
            return l2.map((val, i) => l2[(idx + i) % l2.length]);
        }
    }
}

module.exports.select_next = select_next;
