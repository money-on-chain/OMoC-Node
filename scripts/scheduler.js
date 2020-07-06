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
        throw new Error("We the following env variables: PRIVATE_KEY and RSK_NODE_URL");
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

async function scheduler_main(tasks) {
    const scheduler = require('node-schedule');
    const provider = get_provider();
    const web3 = new Web3(provider);
    const accounts = await web3.eth.getAccounts();
    const source_account = accounts[0];

    const queue = [];
    let processing = false;

    function process_queue() {
        if (processing || queue.length == 0) {
            return;
        }
        processing = true;
        const task = queue.pop();
        task()
            .catch(console.error)
            .then(() => {
                processing = false;
                process_queue();
            });
    }

    for (const name in tasks) {
        const task = tasks[name]
        scheduler.scheduleJob(task["spec"], () => {
            queue.push(async () => {
                console.log("calling", name)
                await task["async_func"](web3, source_account);
                console.log("calling", name, "done")
            })
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
            async_func: async (web3, source_account) => {
                await web3.eth.sendTransaction({
                    to: "0xC69FBF17f088235085fa0D29E229D7C7b2C209f8",
                    value: Web3.utils.toWei("1", "gwei"),
                    from: source_account
                });
            }
        }
    }
    scheduler_main(TASKS).catch(err => {
        console.error(err);
        process.exit(1)
    });
}
