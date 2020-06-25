/**
 * Helper script to pay rewards in testnet
 *
 */
const Web3 = require('web3');
const HDWalletProvider = require("truffle-hdwallet-provider-privkey");
require('dotenv').config()

const ORACLE_MANAGER_ABI =
    [
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
        },
        {
            "name": "token",
            "inputs": [],
            "outputs": [{"internalType": "contract IERC20", "name": "", "type": "address"}],
            "stateMutability": "view",
            "type": "function",
            "constant": true
        },
        {
            "name": "supportersContract",
            "inputs": [],
            "outputs": [
                {
                    "internalType": "contract SupportersWhitelisted",
                    "name": "",
                    "type": "address"
                }
            ],
            "stateMutability": "view",
            "type": "function",
            "constant": true
        },
    ];


const TOKEN_ABI = [
    {
        "name": "balanceOf",
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "name": "transfer",
        "inputs": [{"internalType": "address", "name": "recipient", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}],
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "name": "mint",
        "inputs": [{"internalType": "address", "name": "user", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}],
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
];

function addBN(some_obj, k, val) {
    if (!some_obj[k]) {
        some_obj[k] = Web3.utils.toBN(0);
    }
    some_obj[k].add(val);
}

async function collect_info(to_pay, oracle_manager, amount) {
    const supporters_addr = await oracle_manager.methods.supportersContract().call();
    console.log("\tWill pay", amount.toString(), "weis to supporters", supporters_addr);
    to_pay[supporters_addr] = amount;

    const coin_pair_count = await oracle_manager.methods.getCoinPairCount().call();
    console.log("\tCoin pair count", coin_pair_count);
    for (let i = 0; i < coin_pair_count; i++) {
        const coin_pair = await oracle_manager.methods.getCoinPairAtIndex(i).call();
        const coin_pair_addr = await oracle_manager.methods.getContractAddress(coin_pair).call();
        console.log("\tWill pay", amount.toString(), "weis to coinpair", Web3.utils.toAscii(coin_pair), "addr", coin_pair_addr);
        to_pay[coin_pair_addr] = amount;
    }
    return to_pay;
}

async function pay_with_token(token_addr, token, source_account, to_pay) {
    const tx_params = {
        from: source_account,
        gas: 100 * 1000,
        gasPrice: 59240000,
        // chainID: 31,
    };

    const needed = Object.keys(to_pay).reduce((acc, val) => acc.add(to_pay[val]), Web3.utils.toBN(0));
    console.log("Mint", needed.toString(), "token for", source_account, "in", token_addr);
    await token.methods.mint(source_account, needed).send(tx_params)
    for (let addr of Object.keys(to_pay)) {
        console.log("Paying", to_pay[addr].toString(), "weis from", source_account, "to", addr, "using token", token_addr);
        await token.methods.transfer(addr, to_pay[addr]).send(tx_params)
    }
}

async function main() {
    if (!process.env.PRIVATE_KEY
        || !process.env.RSK_NODE_URL
        || !process.env.ORACLE_MANAGER_ADDRESSES
        || !process.env.PAY_AMOUNT) {
        throw new Error("We the following env variables: PRIVATE_KEY, RSK_NODE_URL, PAY_AMOUNT and ORACLE_MANAGER_ADDRESSES");
    }
    const unit = !process.env.PAY_UNIT ? "gwei" : process.env.PAY_UNIT;
    const amount = Web3.utils.toWei(process.env.PAY_AMOUNT, unit)
    const source_wallet = new HDWalletProvider([process.env.PRIVATE_KEY], process.env.RSK_NODE_URL);
    const oracle_manager_addresses = JSON.parse(process.env.ORACLE_MANAGER_ADDRESSES);
    if (!Array.isArray(oracle_manager_addresses)) {
        throw new Error("We the following env variable: ORACLE_MANAGER_ADDRESSES must contains a json array with addresses");
    }
    try {
        const web3 = new Web3(source_wallet.engine)
        const accounts = await web3.eth.getAccounts();
        const source_account = accounts[0];

        const payments = {};
        for (const addr of oracle_manager_addresses) {
            const oracle_manager_addr = Web3.utils.toChecksumAddress(addr);
            console.log("Oracle manager addr", oracle_manager_addr);
            const oracle_manager = new web3.eth.Contract(ORACLE_MANAGER_ABI, oracle_manager_addr);
            const token_address = await oracle_manager.methods.token().call();
            console.log("\tToken addr", token_address);
            payments[token_address] = await collect_info(payments[token_address] || {}, oracle_manager, Web3.utils.toBN(amount));
        }
        for (const token_addr of Object.keys(payments)) {
            const token = new web3.eth.Contract(TOKEN_ABI, token_addr);
            await pay_with_token(token_addr, token, source_account, payments[token_addr]);
        }

    } finally {
        console.log("Shutting down web3...")
        source_wallet.engine.stop();
    }
}

main().catch(err => {
    console.error(err.message);
    process.exit(1)
});