from common import helpers

from common.services.blockchain import is_error
from scripts import script_settings


async def main():
    conf, oracle_service, oracle_manager_service, moc_token_service, staking_machine_service, staking_machine_addr = await script_settings.configure_oracle()

    print('--------------------------------------------------------------------------------------------------')
    print("Min Coin Pair subscription stake", await oracle_manager_service.get_min_coin_pair_subscription_stake())
    for cp in script_settings.USE_COIN_PAIR:
        print('--------------------------------------------------------------------------------------------------')
        print('=========== COIN PAIR:', cp)
        cps = await oracle_service.get_coin_pair_service(cp)
        print("Lock period timestamp", await cps.get_lock_period_timestamp())
        print("Max oracles per round", await cps.get_max_oracles_per_rounds())
        print("PRICE", await  cps.get_price())
        print("Available rewards", await cps.get_available_reward_fees())

        selected = await cps.get_selected_oracles_info()
        print("SELECTED ORACLES")
        for o in selected:
            print("\t", o.addr)

        oracles = await oracle_service.get_all_oracles_info()
        if is_error(oracles):
            print(' ERROR', oracles)
            return
        print("ALL ORACLES")
        for o in oracles:
            print('\t', o)
            print('\t\tname', oracles[o].internetName, '\tbalance in mocs',
                  await moc_token_service.balance_of(oracles[o].owner))
            print('\t\tstake', oracles[o].stake, '\towner', oracles[o].owner)
            round_info = await cps.get_oracle_round_info(o)
            print("\t\tselectedInCurrentRound", round_info.selectedInCurrentRound,
                  "\tpoints", round_info.points)
            print("\t\tIS SUBSCRIBED", await oracle_manager_service.is_subscribed(cp, o))
            print("\t\tCAN BE REMOVED", await oracle_manager_service.can_remove(o))


if __name__ == '__main__':
    helpers.run_main(main)
