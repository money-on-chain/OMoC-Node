/**
 * Helper script to keep moc-flow running
 *
 */
const Web3 = require('web3');
const HDWalletProvider = require("truffle-hdwallet-provider-privkey");
require('dotenv').config()

const BUFFER_ABI = [
    {
        "inputs": [],
        "name": "isLiquidable",
        "outputs": [
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
        "name": "liquidate",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getNumOutputs",
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
        "inputs": [
            {
                "internalType": "uint256",
                "name": "i",
                "type": "uint256"
            }
        ],
        "name": "isFlushable",
        "outputs": [
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
        "inputs": [
            {
                "internalType": "uint256",
                "name": "i",
                "type": "uint256"
            }
        ],
        "name": "flush",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
];

const DRIP_ABI = [
    {
        "inputs": [],
        "name": "isDripable",
        "outputs": [
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
        "name": "drop",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
];

async function check_and_call(contract, tx_params, check_method, call_method, args = []) {
    const is_ready = await contract.methods[check_method](...args).call();
    if (is_ready) {
        console.log("Calling", call_method + "(" + args.join(", ") + ")", "on", contract._address);
        await contract.methods[call_method](...args).send(tx_params);
    }
}

async function drip_run(web3, drip_addr, tx_params) {
    console.log("Drip addr", drip_addr);
    const contract = new web3.eth.Contract(DRIP_ABI, drip_addr);
    try {
        await check_and_call(contract, tx_params,
            "isDripable", "drop");
    } catch (err) {
        console.error("Error running drip on addr", drip_addr, err);
    }
}

async function buffer_run(web3, buf_addr, tx_params) {
    console.log("Buffer addr", buf_addr);
    const contract = new web3.eth.Contract(BUFFER_ABI, buf_addr);
    try {
        await check_and_call(contract, tx_params,
            "isLiquidable", "liquidate");
        const num_outputs = await contract.methods["getNumOutputs"]().call();
        // We assume num_outputs < MAX_SAFE_INTEGER
        for (let i = 0; i < num_outputs; i++) {
            await check_and_call(contract, tx_params,
                "isFlushable", "flush", [i]);
        }
    } catch
        (err) {
        console.error("Error running buffer on addr", buf_addr, err);
    }
}

async function main() {
    if (!process.env.PRIVATE_KEY
        || !process.env.RSK_NODE_URL
        || !process.env.MOC_FLOW_DRIPPERS
        || !process.env.MOC_FLOW_BUFFERS) {
        throw new Error("We the following env variables: PRIVATE_KEY, RSK_NODE_URL, MOC_FLOW_DRIPPERS and MOC_FLOW_BUFFERS");
    }
    const source_wallet = new HDWalletProvider([process.env.PRIVATE_KEY], process.env.RSK_NODE_URL);
    const drippers = JSON.parse(process.env.MOC_FLOW_DRIPPERS);
    if (!Array.isArray(drippers)) {
        throw new Error("We the following env variable: MOC_FLOW_DRIPPERS must contains a json array with addresses");
    }
    const buffers = JSON.parse(process.env.MOC_FLOW_BUFFERS);
    if (!Array.isArray(buffers)) {
        throw new Error("We the following env variable: MOC_FLOW_BUFFERS must contains a json array with addresses");
    }
    if (drippers.length === 0 && buffers.length === 0) {
        throw new Error("We need some drips or buffers to call");
    }

    try {
        const web3 = new Web3(source_wallet.engine)
        const accounts = await web3.eth.getAccounts();
        const source_account = accounts[0];
        for (const drip of drippers) {
            const drip_addr = Web3.utils.toChecksumAddress(drip);
            await drip_run(web3, drip_addr, {
                from: source_account,
                gas: 100 * 1000,
                gasPrice: 59240000
            });
        }
        for (const buf of buffers) {
            const buf_addr = Web3.utils.toChecksumAddress(buf);
            await buffer_run(web3, buf_addr, {
                from: source_account,
                gas: 100 * 1000,
                gasPrice: 59240000
            });
        }
    } finally {
        console.log("Shutting down web3...")
        source_wallet.engine.stop();
    }
}

main().catch(err => {
    console.error(err);
    process.exit(1)
});