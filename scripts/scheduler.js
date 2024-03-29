/**
 * Helper to run paying scripts from one account
 *
 */
const Web3 = require('web3');
const helpers = require('./helpers');
const HDWalletProvider = require("truffle-hdwallet-provider-privkey");
require('dotenv').config()

function get_provider() {
    if (!process.env.PRIVATE_KEY || !process.env.RSK_NODE_URL) {
        throw new Error("We need the following env variables: PRIVATE_KEY and RSK_NODE_URL");
    }
    return new HDWalletProvider([process.env.PRIVATE_KEY], process.env.RSK_NODE_URL);
}

// Helper function to run the script directly from command line
function run_main(main_func) {
    async function run_with_web3(main_func) {
        const provider = get_provider();
        try {
            const web3 = new Web3(provider);
            const accounts = await web3.eth.getAccounts();
            const source_account = accounts[0];
            await main_func(web3, source_account);
        } finally {
            console.log("Shutting down web3...")
            provider.engine.stop();
        }
    }

    run_with_web3(main_func).catch(err => {
        console.error(err);
        process.exit(1)
    });
}

module.exports.run_main = run_main;

async function transfer_main(web3, source_account) {
    if (!process.env.TRANSFER_DESTINATIONS) {
        console.log("Skipping transfers");
    }
    const destinations = JSON.parse(process.env.TRANSFER_DESTINATIONS);
    if (!Array.isArray(destinations)) {
        throw new Error("We need the following env variable: TRANSFER_DESTINATIONS must contains " +
            "a json array with addresses");
    }
    const unit = !process.env.TRANSFER_UNIT ? "gwei" : process.env.TRANSFER_UNIT;
    let amounts = destinations.map(x => 1);
    if (process.env.TRANSFER_AMOUNTS) {
        const a = JSON.parse(process.env.TRANSFER_AMOUNTS);
        if (!Array.isArray(a) || a.length != destinations.length) {
            throw new Error("We need the following env variable: TRANSFER_AMOUNTS must contains a " +
                "json array of the same size as TRANSFER_DESTINATIONS");
        }
        amounts = a;
    }
    let gas = 4200000;
    if (process.env.TRANSFER_GAS && !isNaN(parseInt(process.env.TRANSFER_GAS))) {
        gas = parseInt(process.env.TRANSFER_GAS);
    }
    for (let i = 0; i < destinations.length; i++) {
        const d = destinations[i];
        const amount = Web3.utils.toBN(Web3.utils.toWei(amounts[i].toString(), unit));
        const dest = Web3.utils.toChecksumAddress(d);
        console.log("Transfer rbtc from", source_account, "to", dest, "amount", amount.toString());
        await web3.eth.sendTransaction({
            gas,
            to: dest,
            value: amount,
            from: source_account
        });
    }
}


async function scheduler_main(tasks) {
    const scheduler = require('node-schedule');
    const provider = get_provider();
    const web3 = new Web3(provider);
    console.log("USING transactionBlockTimeout", web3.eth.transactionBlockTimeout);
    web3.eth.transactionPollingTimeout = 1500;
    console.log("USING transactionPollingTimeout", web3.eth.transactionPollingTimeout);

    const accounts = await web3.eth.getAccounts();
    const source_account = accounts[0];

    const queue = [];
    let processing = false;

    function process_queue() {
        if (processing || queue.length == 0) {
            return;
        }
        processing = true;
        const {task, name} = queue.pop();
        console.log("calling", name)
        const func = task["async_func"];
        func(web3, source_account)
            .catch((err) => console.error("ERROR IN TASK", name, err))
            .then(() => {
                console.log("calling", name, "done")
                processing = false;
                process_queue();
            });
    }

    for (const name in tasks) {
        const task = tasks[name]
        scheduler.scheduleJob(task["spec"], () => {
            queue.push({task, name})
            process_queue()
        });
    }
}


if (require.main === module) {
    const scheduler_pay_rewards = require("./scheduler_pay_rewards");
    const scheduler_moc_flow = require("./scheduler_moc_flow");

    const TASKS = {
        "pay_rewards_main": {
            spec: "0 */2 * * *",
            async_func: scheduler_pay_rewards.pay_rewards_main
        },
        "moc_flow_main": {
            spec: '*/3 * * * *',
            async_func: scheduler_moc_flow.moc_flow_main
        },
        "transfer": {
            spec: '*/10 * * * *',
            async_func: transfer_main
        }
    }
    scheduler_main(TASKS).catch(err => {
        console.error(err);
        process.exit(1)
    });
}
