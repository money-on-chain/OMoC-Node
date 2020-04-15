from common import helpers
from common.services.blockchain import is_error
from oracle.src import oracle_service
from scripts import script_settings
from scripts.script_settings import PRICE_FETCHER_OWNER_ACCOUNT


async def main():
    for cp in script_settings.USE_COIN_PAIR:
        cps = await oracle_service.get_oracle_service(cp)
        if is_error(cps):
            print("Error getting coin pair service for coin pair", cp, cps)
            continue

        print("get round info")
        round_info = await cps.get_round_info()
        if round_info.round != 0:
            print("Already started, round", round_info.round)
            return
        print(repr(round_info))

        print("start initial round")
        tx = await cps.switch_round(account=PRICE_FETCHER_OWNER_ACCOUNT, wait=True)
        print("start initial round", tx)


if __name__ == '__main__':
    helpers.run_main(main)