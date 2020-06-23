/**
 * Helper script to pay rewards in testnet
 *
 */
const Web3 = require('web3');
const HDWalletProvider = require("truffle-hdwallet-provider-privkey");

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

async function pay(token, from, destination_addr, amount) {
    const params = {
        from,
        gas: 100 * 1000,
        // gasPrice: 59240000,
        // chainID: 31,
    };
    await token.methods.mint(from, amount).send(params)
    await token.methods.transfer(destination_addr, amount).send(params)
}

async function main() {
    if (!process.env.PRIVATE_KEY
        || !process.env.RSK_NODE_URL
        || !process.env.ORACLE_MANAGER_ADDRESS
        || !process.env.PAY_AMOUNT) {
        throw new Error("We the following env variables: PRIVATE_KEY, RSK_NODE_URL, PAY_AMOUNT and ORACLE_MANAGER_ADDRESS");
    }
    const unit = !process.env.PAY_UNIT ? "gwei" : process.env.PAY_UNIT;
    const amount = Web3.utils.toWei(process.env.PAY_AMOUNT, unit)
    const source_wallet = new HDWalletProvider([process.env.PRIVATE_KEY], process.env.RSK_NODE_URL);
    const oracle_manager_addr = Web3.utils.toChecksumAddress(process.env.ORACLE_MANAGER_ADDRESS);
    try {
        const web3 = new Web3(source_wallet.engine)
        const accounts = await web3.eth.getAccounts();
        const source_account = accounts[0];

        const oracle_manager = new web3.eth.Contract(ORACLE_MANAGER_ABI, oracle_manager_addr);
        const token_address = await oracle_manager.methods.token().call();
        console.log("Token addr", token_address);
        const token = new web3.eth.Contract(TOKEN_ABI, token_address);

        const supporters_addr = await oracle_manager.methods.supportersContract().call();
        console.log("Paying", amount, unit, "to supporters", supporters_addr, "from", source_account);
        await pay(token, source_account, supporters_addr, amount);

        const coin_pair_count = await oracle_manager.methods.getCoinPairCount().call();
        console.log("Coin pair count", coin_pair_count);
        for (let i = 0; i < coin_pair_count; i++) {
            const coin_pair = await oracle_manager.methods.getCoinPairAtIndex(i).call();
            const coin_pair_addr = await oracle_manager.methods.getContractAddress(coin_pair).call();
            console.log("Paying", amount, unit, "to coinpair", Web3.utils.toAscii(coin_pair),
                "addr", coin_pair_addr, "from", source_account);
            await pay(token, source_account, coin_pair_addr, amount);
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