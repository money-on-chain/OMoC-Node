/**
 * Helper script to keep moc-flow running
 *
 */
const Web3 = require('web3');
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
        await ((contract.methods[call_method](...args)).send(tx_params));
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

async function moc_flow_main(web3, source_account) {
    if (!process.env.MOC_FLOW_DRIPPERS
        || !process.env.MOC_FLOW_BUFFERS) {
        throw new Error("We need the following env variables: MOC_FLOW_DRIPPERS and MOC_FLOW_BUFFERS");
    }
    const drippers = JSON.parse(process.env.MOC_FLOW_DRIPPERS);
    if (!Array.isArray(drippers)) {
        throw new Error("We need the following env variable: MOC_FLOW_DRIPPERS must contains a json array with addresses");
    }
    const buffers = JSON.parse(process.env.MOC_FLOW_BUFFERS);
    if (!Array.isArray(buffers)) {
        throw new Error("We need the following env variable: MOC_FLOW_BUFFERS must contains a json array with addresses");
    }
    if (drippers.length === 0 && buffers.length === 0) {
        throw new Error("We need some drips or buffers to call");
    }

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
}

module.exports.moc_flow_main = moc_flow_main;

if (require.main === module) {
    const scheduler = require("./scheduler");
    scheduler.run_main(moc_flow_main);
}
