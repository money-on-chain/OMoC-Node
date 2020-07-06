// CONFIGURATION!!!!
const RSK_NODE_URL = "https://public-node.testnet.rsk.co";
const ORACLE_MANAGER_ADDRESS = "0xACb142091e345c50D2c9aD94f849Ca98DfC0eD6B";
const CONFIRMATIONS = 10;
const SEARCH_DEPTH = 100;
const FROM_ADDRS = [
    "0xF6A2fe11415cEEC12B59D9BC8d37AAF9DDA60B32",
    "0x8b7EEF66c1BB20f550b79E4891CcC6a06F7f4F6d",
    "0xff49426EE621FCF9928FfDBd163fBC13fA36f465",
    "0xd761CC1ceB991631d431F6dDE54F07828f2E61d2",
    "0x3ef6eFadE0C6F1AC81779F5f66142462b64D2285",
    "0xBc6D08Ecd1F17c5f7aE16c92CEB8d9B5f6bcbC54",
];

// CoinPairPrice Addr
const TO_ADDR = "0x71C199A8476059b3e4cb1aC8189D5E5d15c46689";
// CONFIGURATION END
/**
 *
 */
const Web3 = require('web3');
const log = console.log;
const error = console.error;
const catch_error = () => {
};

async function get_txs(web3, confirmations, search_depth) {
    const currBlk = Web3.utils.toBN(await web3.eth.getBlockNumber());
    const toBlk = currBlk.sub(Web3.utils.toBN(confirmations));
    log(toBlk.toString(), toBlk.subn(search_depth).toString());
    const from_addrs = FROM_ADDRS.map(x => x.toLowerCase());
    const eth = web3.eth;
    const promises = []
    for (let i = toBlk.subn(search_depth); toBlk.gt(i); i = i.addn(1)) {
        promises.push(eth.getBlock(i, true));
    }
    const blocks = await Promise.all(promises);
    const f_blocks = blocks.filter(b => b != null && b.transactions != null)
        .map(b => b.transactions.map(x => ({...x, timestamp: b.timestamp})));
    const tx_filter = tx => (tx.from
        && from_addrs.includes(tx.from.toLowerCase())
        && tx.to.toLowerCase() === TO_ADDR.toLowerCase());
    const txs = [].concat.apply([], f_blocks).filter(tx_filter);
    const txMap = txs.reduce((acc, tx) => {
        acc[tx.hash] = tx;
        return acc;
    }, {});
    const receipts = await Promise.all(txs.map(x => eth.getTransactionReceipt(x.hash)));
    receipts.sort((a, b) => (b.blockNumber - a.blockNumber));
    return receipts.map(r => ({...r, ...txMap[r.transactionHash]}));
}

const publish_signature = Web3.utils.sha3("publishPrice(uint256,bytes32,uint256,address,uint256,uint8[],bytes32[],bytes32[])").substring(0, 10);
const switch_round_signature = Web3.utils.sha3("switchRound()").substring(0, 10);

async function main() {
    const web3 = new Web3(new Web3.providers.HttpProvider(RSK_NODE_URL));
    // Success transactions
    const txs = (await get_txs(web3, CONFIRMATIONS, SEARCH_DEPTH)).filter(x => x.status);
    const publications = txs
        .filter(x => x.input.startsWith(publish_signature))
        .map(x => ({from: x.from, timestamp: x.timestamp}));
    const switch_round = txs
        .filter(x => x.input.startsWith(switch_round_signature))
        .map(x => ({from: x.from, timestamp: x.timestamp}));
    log(switch_round);
    const metrics1 = publications.map(x => ({
        MetricName: 'Publication_' + x.from,
        Timestamp: x.timestamp,
        Value: "1"
    }));
    return {
        Namespace: 'MOC/ORACLE-PUBLICATION',
        MetricData: metrics1,
    };
}

main().catch(err => console.error(err.message)).then(console.log);