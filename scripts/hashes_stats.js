// A collection of small different tests related to the hashes and the way that we choose the
// next selected oracle.

const fs = require('fs');
const helpers = require('./helpers');
const Web3 = require('web3');


const selected_oracles = [
    {
        stake: '35000000000000026796',
        addr: '0x3ef6eFadE0C6F1AC81779F5f66142462b64D2285'
    },
    {
        stake: '28000000000000021437',
        addr: '0x8b7EEF66c1BB20f550b79E4891CcC6a06F7f4F6d'
    },
    {
        stake: '25000000000000019140',
        addr: '0xBc6D08Ecd1F17c5f7aE16c92CEB8d9B5f6bcbC54'
    },
    {
        stake: '5000000000000003828',
        addr: '0xd761CC1ceB991631d431F6dDE54F07828f2E61d2'
    }
];

const data = {
    '0x3a798df87ba7d79ae68b16e51878f84afdbfb19a2488f46192c8d98e7cf97870': '0xBc6D08Ecd1F17c5f7aE16c92CEB8d9B5f6bcbC54',
    '0xb144997ade6093b9c57be6896f29a2f73cbbae5ad1f553f2e4be29787cf34a8f': '0x3ef6eFadE0C6F1AC81779F5f66142462b64D2285',
    '0x7c5d00c24bdddffbfb1763e454929f089ad456a0c22fb5802e31a884e2b7de1f': '0x8b7EEF66c1BB20f550b79E4891CcC6a06F7f4F6d',
    '0xe8b81615d587fa117110a60b21d8d090cd568f486d11d79ce38439e05c927a7d': '0x8b7EEF66c1BB20f550b79E4891CcC6a06F7f4F6d',
    '0x9f24afa1363d54941c60058da9c2c312aaf88ff785d88baf941980bf24619d69': '0xBc6D08Ecd1F17c5f7aE16c92CEB8d9B5f6bcbC54',
    '0x67b7dc9884cdc9b674caa645f78dd623b1c3711497837b4de98bf90420eecd82': '0x3ef6eFadE0C6F1AC81779F5f66142462b64D2285',
    '0x1c3d4e5bb994b1fce2b45d5875dc36cd66346ebf4d0592a77bd6ef05ae8636e1': '0x3ef6eFadE0C6F1AC81779F5f66142462b64D2285',
    '0xa9bbd47a11d90101bb81df5838527e48fb75a5313b5a55ed3d837e8f0db23f6a': '0x3ef6eFadE0C6F1AC81779F5f66142462b64D2285',
    '0x336fd5ba1e0de3d7a7bf0df8a0407c74cac26ddca095514f041073b92ca580e5': '0x3ef6eFadE0C6F1AC81779F5f66142462b64D2285',
    '0x9ba17161ae3da225d62b496b28d3ec0c5d52d01b7dd59deb3d6e349194320976': '0x8b7EEF66c1BB20f550b79E4891CcC6a06F7f4F6d',
    '0x7992b847d2b787a05f118737884226b42ae77d791c7ac6e1716da3ec267ccea1': '0x3ef6eFadE0C6F1AC81779F5f66142462b64D2285',
    '0xa9b9979f37c1a6d646b12e25ecc227b2f6301269ba97d020f0e5e39b3e8960c6': '0x3ef6eFadE0C6F1AC81779F5f66142462b64D2285',
    '0xcbdf47db144eff3f2ee0c58e3b4bfd27af23a1672b504be2118c9c5e1aa58198': '0x3ef6eFadE0C6F1AC81779F5f66142462b64D2285',
    '0x5c491af61219e9e104863e4164861395b253a1ef787b30101e90c2ef2500e825': '0x3ef6eFadE0C6F1AC81779F5f66142462b64D2285',
    '0xb0b63d69848392e58e341d59e2bb2a316ad001232e96e9a0f044fdfaa2fafb74': '0xBc6D08Ecd1F17c5f7aE16c92CEB8d9B5f6bcbC54',
    '0x56ffad790c04eacb55ddbbbcdfba13ae2fc6c4b6d46b0cb31e6c79a4d057e0ec': '0x3ef6eFadE0C6F1AC81779F5f66142462b64D2285',
    '0x66c96e98a8a469bfa92d42e873952623b57b91151717f9f16af94196500bdb09': '0x3ef6eFadE0C6F1AC81779F5f66142462b64D2285',
    '0x0563d4aa2d7fa68e7f8a8716280a40927b73746f86952129a6aec9e77ccbb48e': '0x8b7EEF66c1BB20f550b79E4891CcC6a06F7f4F6d',
    '0x602cada858f3862c55b891c4b824193e8be8c4e8fb5cdc2b9228ca5d938513f9': '0x3ef6eFadE0C6F1AC81779F5f66142462b64D2285',
    '0xb1be66d58086c29e5481a92ac1e75ba1cbc3383dabcce695be2f84332b079f38': '0x3ef6eFadE0C6F1AC81779F5f66142462b64D2285',
    '0x4a86b5b35b8a0d62a38e3028f9cb64df049dde5bf752b1d72233fbba6a8f1d33': '0xd761CC1ceB991631d431F6dDE54F07828f2E61d2',
    '0x1ab299ac05954f99de77fce2ce237e7b327a711f19315aa92237d96515f577c0': '0xBc6D08Ecd1F17c5f7aE16c92CEB8d9B5f6bcbC54',
    '0x0af7f6118ec1854fad94f8a7034717e51fd0674edc72e860cdbaf2e61184cf7d': '0xBc6D08Ecd1F17c5f7aE16c92CEB8d9B5f6bcbC54'
};

let hashes;
if (true) {
    // hashes = Object.keys(data);
    hashes = JSON.parse(fs.readFileSync('hashes.json'));
} else {
    const {oracles, selected} = JSON.parse(fs.readFileSync('../servers/select_next_data.json'));
    hashes = Object.keys(selected);
}
const stats = [];
const two = Web3.utils.toBN(2);
const max_int = Web3.utils.toBN('0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF');
let cant = 0;
let total = Web3.utils.toBN(0);
for (const hash of hashes) {
    console.log("check", hash);
    const hb = Web3.utils.toBN(hash)
    total = total.add(hb);
    // if (!(Number(hash.substring(0, 3)) & 0x8)) {
    if (hb.lt(max_int.div(two))) {
        cant++
    }
    const s = helpers.select_next(hash, selected_oracles);
    stats.push(s[0]);
}
const mean = total.divn(hashes.length);
console.log("MEAN", mean.toString(), "0x" + mean.toString(16));
console.log("HALF", max_int.div(two).toString(), "0x" + max_int.div(two).toString(16));

console.log("CANT LESS THAN HALF", cant / hashes.length, "FROM", hashes.length);
const stakes = selected_oracles.map(x => parseInt(x.stake));
console.log("STAKES", stakes)
const total_stakes = stakes.reduce((acc, val) => acc + val)
console.log("NEEDED", stakes.map(x => Math.round(hashes.length * x / total_stakes)))
const selected_addresses = selected_oracles.map(x => x.addr);
console.log("STATS", stats
    .reduce((acc, val) => {
        const idx = selected_addresses.indexOf(val);
        if (!acc[idx]) acc[idx] = 0;
        acc[idx]++;
        return acc;
    }, {}));
