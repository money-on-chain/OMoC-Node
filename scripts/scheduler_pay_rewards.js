/**
 * Helper script to pay rewards in testnet
 *
 */
const Web3 = require('web3');
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

const SUPPORTERS_ABI = [
    {
        "inputs": [],
        "name": "getAvailableMOC",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
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
    }
];

async function collect_coin_pair_info(to_pay, oracle_manager, oracles_amount) {
    const coin_pair_count = await oracle_manager.methods.getCoinPairCount().call();
    console.log("\tCoin pair count", coin_pair_count);
    for (let i = 0; i < coin_pair_count; i++) {
        const coin_pair = await oracle_manager.methods.getCoinPairAtIndex(i).call();
        const coin_pair_addr = await oracle_manager.methods.getContractAddress(coin_pair).call();
        console.log("\tWill pay", oracles_amount.toString(), "weis to coinpair", Web3.utils.toAscii(coin_pair), "addr", coin_pair_addr);
        to_pay[coin_pair_addr] = oracles_amount;
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
    const current_balance = Web3.utils.toBN(await token.methods.balanceOf(source_account).call());
    if (current_balance.lt(needed)) {
        console.log("NOT ENOUGH BALANCE IN SOURCE ACCOUNT", source_account
            , "HAVE", current_balance.toString()
            , "NEEDS", needed.toString()
        )
    }
    // await token.methods.mint(source_account, needed).send(tx_params)
    for (let addr of Object.keys(to_pay)) {
        console.log("Paying", to_pay[addr].toString(),
            "weis from", current_balance.toString(), "balance of", source_account,
            "to", addr, "using token", token_addr);
        await token.methods.transfer(addr, to_pay[addr]).send(tx_params)
    }
}

async function pay_rewards_main(web3, source_account) {
    if (!process.env.ORACLE_MANAGER_ADDRESSES
        || !process.env.SUPPORTERS_FACTOR) {
        throw new Error("We need the following env variables: SUPPORTERS_FACTOR and ORACLE_MANAGER_ADDRESSES");
    }
    const unit = !process.env.PAY_UNIT ? "gwei" : process.env.PAY_UNIT;
    const supporters_factor = Web3.utils.toBN(Web3.utils.toWei(process.env.SUPPORTERS_FACTOR, unit));
    const oracle_manager_addresses = JSON.parse(process.env.ORACLE_MANAGER_ADDRESSES);
    if (!Array.isArray(oracle_manager_addresses)) {
        throw new Error("We need the following env variable: ORACLE_MANAGER_ADDRESSES must contains a json array with addresses");
    }

    const payments = {};
    for (const addr of oracle_manager_addresses) {
        const oracle_manager_addr = Web3.utils.toChecksumAddress(addr);
        console.log("Oracle manager addr", oracle_manager_addr);
        const oracle_manager = new web3.eth.Contract(ORACLE_MANAGER_ABI, oracle_manager_addr);
        const token_address = await oracle_manager.methods.token().call();
        console.log("\tToken addr", token_address);

        const supporters_addr = await oracle_manager.methods.supportersContract().call();
        console.log("\tSupporters addr", token_address);
        const supporters = new web3.eth.Contract(SUPPORTERS_ABI, supporters_addr);
        const available_moc = await supporters.methods.getAvailableMOC().call();
        const supporters_amount = Web3.utils.toBN(available_moc)
            .mul(supporters_factor)
            .div(Web3.utils.toBN(10 ** 18));
        console.log("\tWill pay", supporters_amount.toString(), "weis to supporters", supporters_addr);

        const payments_per_token = {};
        payments_per_token[supporters_addr] = supporters_amount;
        payments[token_address] = await collect_coin_pair_info(payments_per_token,
            oracle_manager, supporters_amount);
    }
    for (const token_addr of Object.keys(payments)) {
        const token = new web3.eth.Contract(TOKEN_ABI, token_addr);
        await pay_with_token(token_addr, token, source_account, payments[token_addr]);
    }
}

module.exports.pay_rewards_main = pay_rewards_main;

if (require.main === module) {
    const scheduler = require("./scheduler");
    scheduler.run_main(pay_rewards_main);
}
