/*
This script was used during a demo and it is meant to be used with ganache, it
    adds earnings to the supporters smart contract, mine blocks each second and rotates
    the rounds when needed.
    Example:  ```NETWORK=ganache node supporters_pay.js```

 */

const Web3 = require('web3');
const helpers = require('./helpers');
const config = require('./CONFIG');

function select_next(last_block_hash, oracle_info_list) {
    if (oracle_info_list.length == 0) {
        return [];
    }

    if (oracle_info_list.length > 32) {
        throw  new Error('Cant have more than 32 oracles, the hash is 32 bytes long');
    }

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
        stake_buckets.push(total_stake.subn(1))
    }
    // Select from L2 according to stake weight
    // rnd_stake = int(last_block_hash, 16) % total_stake
    // i've got hexbytes string in hash, so:
    const rnd_stake = last_block_hash_as_int.mod(total_stake);
    // stake_buckets is a growing array of numbers, search the first bigger than rnd_stake
    for (let idx = 0; ; idx++) {
        if (rnd_stake.lte(stake_buckets[idx])) {
            // reorder the l2 array starting with idx
            return l2.map((val, i) => l2[(idx + i) % l2.length]);
        }
    }
}

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
        console.log("select order", select_next(blockHash, oracles));
    }
}

config.run(principal);
