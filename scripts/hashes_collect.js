const helpers = require('./helpers');
const config = require('./CONFIG');

async function principal(conf) {
    const {web3, coinPairPrice, oracleManager} = conf;
    const ARGS = helpers.getScriptArgs(__filename);
    const DEPTH_IN_BLOCKS = isNaN(ARGS[0]) ? 70 : parseInt(ARGS[0]);
    console.log("DEPTH_IN_BLOCKS", DEPTH_IN_BLOCKS);
    const toBlk = parseInt(await web3.eth.getBlockNumber());
    const fromBlk = toBlk - DEPTH_IN_BLOCKS;
    console.log("RUN FROM", fromBlk, "to", toBlk);
    const blocks = [];
    // Take in chunks of 100 blocks
    const CHUNK_SIZE = 100;
    for (let i = fromBlk; i < toBlk; i += CHUNK_SIZE) {
        console.log("GET FROM", i, "to", i + CHUNK_SIZE);
        const promises = []
        for (let j = 0; i + j < toBlk && j < CHUNK_SIZE; j++) {
            promises.push(web3.eth.getBlock(i + j, true));
        }
        blocks.push(...await Promise.all(promises));
    }
    // To be used to run select_next_test2.js
    const fs = require("fs")
    fs.writeFileSync('hashes.json', JSON.stringify(blocks.map(x => x.hash)));
}

config.run(principal);
