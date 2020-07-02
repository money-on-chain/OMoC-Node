module.exports = {
    apps: [
        {
            name: "indexer",
            script: "./index_contract_calls.js",
            watch: false,
            autorestart: false,
            args: "PUT YOUR COIN PAIR PRICE ADDR HERE!!!",
            cron_restart: "0,30 * * * *",
            log_date_format: "YYYY-MM-DD HH:mm:ss Z",
            env: {
                NETWORK: 'rsknode_gobernanza'
            },
        },
        {
            name: "rewards",
            script: "./pay_rewards.js",
            watch: false,
            autorestart: false,
            cron_restart: "0 */2 * * *",
            log_date_format: "YYYY-MM-DD HH:mm:ss Z",
        },
        {
            name: "moc_flow",
            script: "./moc_flow.js",
            watch: false,
            autorestart: false,
            cron_restart: "*/3 * * * *",
            log_date_format: "YYYY-MM-DD HH:mm:ss Z",
        },
    ]
}
