// CONFIGURATION!!!!
const RSK_NODE_URL = "https://public-node.testnet.rsk.co";
const ORACLE_MANAGER_ADDRESS = "0xACb142091e345c50D2c9aD94f849Ca98DfC0eD6B";
const ACCOUNT_BALANCE_CHECK_ADDRESSES = [
    "0xF6A2fe11415cEEC12B59D9BC8d37AAF9DDA60B32",
    "0x8b7EEF66c1BB20f550b79E4891CcC6a06F7f4F6d",
    "0xff49426EE621FCF9928FfDBd163fBC13fA36f465",
    "0xd761CC1ceB991631d431F6dDE54F07828f2E61d2"
];
// CONFIGURATION END


/**
 *
 */
const Web3 = require('web3');
const ADDRESS_ONE = "0x0000000000000000000000000000000000000001";
const log = console.log;
const error = console.error;
const catch_error = () => {
};
const ORACLE_MANAGER_ABI = [
    {
        "name": "getCoinPairCount",
        "inputs": [],
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
        "constant": true
    },
    {
        "name": "getCoinPairAtIndex",
        "inputs": [{"internalType": "uint256", "name": "i", "type": "uint256"}],
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function",
        "constant": true
    },
    {
        "name": "getContractAddress",
        "inputs": [{"internalType": "bytes32", "name": "coinpair", "type": "bytes32"}],
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
        "constant": true
    }
];

const COIN_PAIR_PRICE_ABI = [
    {
        "inputs": [],
        "name": "validPricePeriodInBlocks",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "peek",
        "outputs": [
            {
                "internalType": "bytes32",
                "name": "",
                "type": "bytes32"
            },
            {
                "internalType": "bool",
                "name": "",
                "type": "bool"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "lastPublicationBlock",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getRoundInfo",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "round",
                "type": "uint256"
            },
            {
                "internalType": "uint256",
                "name": "startBlock",
                "type": "uint256"
            },
            {
                "internalType": "uint256",
                "name": "lockPeriodEndBlock",
                "type": "uint256"
            },
            {
                "internalType": "uint256",
                "name": "totalPoints",
                "type": "uint256"
            },
            {
                "internalType": "address[]",
                "name": "selectedOracles",
                "type": "address[]"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    }
];

async function get_coin_pair_data(web3, coin_pair, coin_pair_price) {
    const promises = [
        web3.eth.getBlockNumber().catch(catch_error),
        coin_pair_price.methods.validPricePeriodInBlocks().call().catch(catch_error),
        coin_pair_price.methods.lastPublicationBlock().call().catch(catch_error),
        coin_pair_price.methods.peek().call({from: ADDRESS_ONE}).catch(catch_error),
        coin_pair_price.methods.getRoundInfo().call().catch(catch_error),
    ];
    // TODO: check what is better if sequential or parallel.
    const [cb, valid_price_period_in_blocks,
        last_publication_block, price_data, round_data] = await Promise.all(promises);
    let block_to_expire;
    if (cb && valid_price_period_in_blocks && last_publication_block) {
        const period = Web3.utils.toBN(valid_price_period_in_blocks);
        const current_block = Web3.utils.toBN(cb)
        block_to_expire = Web3.utils.toBN(last_publication_block).add(period).sub(current_block);
    }
    return {
        coin_pair,
        block_to_expire,
        price: Web3.utils.toBN(price_data[0]),
        points: Web3.utils.toBN(round_data.totalPoints)
    };
}

async function get_balances(web3) {
    // TODO: check what is better if sequential or parallel.
    return (await Promise
        .all(ACCOUNT_BALANCE_CHECK_ADDRESSES
            .map(addr =>
                web3.eth.getBalance(addr)
                    .catch(error)
                    .then(x => Web3.utils.toBN(x))
            )
        ))
        .reduce((acc, val, idx) => {
            acc[ACCOUNT_BALANCE_CHECK_ADDRESSES[idx]] = val;
            return acc;
        }, {});
}

async function get_data(web3) {
    const oracle_manager = new web3.eth.Contract(ORACLE_MANAGER_ABI, ORACLE_MANAGER_ADDRESS);
    const coin_pair_count = await oracle_manager.methods.getCoinPairCount().call();
    const ret = [];
    for (let i = 0; i < coin_pair_count; i++) {
        const coin_pair = await oracle_manager.methods.getCoinPairAtIndex(i).call();
        const coin_pair_addr = await oracle_manager.methods.getContractAddress(coin_pair).call();
        const coin_pair_price = new web3.eth.Contract(COIN_PAIR_PRICE_ABI, coin_pair_addr);
        ret.push(await get_coin_pair_data(web3, Web3.utils.toUtf8(coin_pair), coin_pair_price))
    }
    return ret;
}

async function main() {
    const web3 = new Web3(new Web3.providers.HttpProvider(RSK_NODE_URL));
    // TODO: check what is better if sequential or parallel.
    const balances = await get_balances(web3);
    const data = await get_data(web3);
    const metrics1 = Object.keys(balances).map(account_addr => ({
        MetricName: 'Balance',
        Value: balances[account_addr].toString(),
        Dimensions: [
            {Name: 'Account', Value: account_addr},
            {Name: 'Oracle', Value: ORACLE_MANAGER_ADDRESS},
        ]
    }));
    const metrics2 = [].concat.apply([], data.map(x => ([
        {
            MetricName: 'BlockToPriceExpire',
            Value: x.block_to_expire.toString(),
            Dimensions: [
                {Name: 'CoinPair', Value: x.coin_pair},
                {Name: 'Oracle', Value: ORACLE_MANAGER_ADDRESS},
            ]
        },
        {
            MetricName: 'Price',
            Value: x.price.toString(),
            Dimensions: [
                {Name: 'CoinPair', Value: x.coin_pair},
                {Name: 'Oracle', Value: ORACLE_MANAGER_ADDRESS},
            ]
        },
        {
            MetricName: 'TotalPoints',
            Value: x.points.toString(),
            Dimensions: [
                {Name: 'CoinPair', Value: x.coin_pair},
                {Name: 'Oracle', Value: ORACLE_MANAGER_ADDRESS},
            ]
        }])));
    return {
        Namespace: 'MOC/ORACLE-NODE',
        MetricData: [...metrics1, ...metrics2],
    };
}


main().catch(err => console.error(err.message)).then(console.log);

