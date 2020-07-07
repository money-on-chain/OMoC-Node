const fs = require('fs');
const helpers = require('./helpers');


async function main() {
    const {oracles, selected} = JSON.parse(fs.readFileSync('../servers/select_next_data.json'));
    for (const hash in selected) {
        console.log("check", hash);
        const to_check = selected[hash];
        const s = helpers.select_next(hash, oracles);
        if (s.length !== to_check.length) {
            console.log("Lengths don't match");
            process.exit();
        }
        if (!s.every((val, i) => val === to_check[i])) {
            console.log("Arrays don't match");
            process.exit();
        }
    }
    console.log("DONE");
}

main().catch(console.error);