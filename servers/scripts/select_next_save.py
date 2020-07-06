import json
import secrets
from random import randint

from common import helpers
from common.services.oracle_dao import FullOracleRoundInfo
# Take from scheduler addr into reward bag addr
from oracle.src.select_next import select_next_addresses


async def main():
    num_oracles = 32
    num_rounds = 12000
    owner = '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826'

    oracle_infos = []
    total_stake = 0
    for i in range(0, num_oracles):
        stake = randint(0, 1000) + 10000
        total_stake += stake
        oi = FullOracleRoundInfo(secrets.token_hex(nbytes=20), 'SOME_NAME_' + str(i), stake,
                                 owner, 0, False, 0)
        oracle_infos.append(oi)

    # TODO: Move this into the server (we must not trust the block chain order).
    oracle_infos.sort(key=lambda x: x.stake, reverse=True)
    selected = {}
    for i in range(num_rounds):
        last_block_hash = secrets.token_hex(nbytes=32)
        selected[last_block_hash] = select_next_addresses(last_block_hash, oracle_infos)

    with open('select_next_data.json', 'w') as outfile:
        json.dump({
            "oracles": [{"addr": x.addr, "stake": x.stake} for x in oracle_infos],
            "selected": selected
        }, outfile)


if __name__ == '__main__':
    helpers.run_main(main)
