from common import helpers
from scripts import script_settings


async def main():
    oracle_account = script_settings.SCRIPT_ORACLE_ACCOUNT
    oracle_addr = str(oracle_account.addr)
    owner_addr = script_settings.SCRIPT_ORACLE_OWNER_ACCOUNT.addr
    print("ORACLE ADDR", oracle_addr)
    print("ORACLE OWNER ADDR", owner_addr)

    conf, oracle_service, oracle_manager_service, moc_token_service, staking_machine_service, staking_machine_addr = await script_settings.configure_oracle()

    for cp in script_settings.USE_COIN_PAIR:
        balance = await script_settings.blockchain.get_balance(owner_addr)
        print(cp, " Oracle owner coinbase balance ", balance)
        if balance < script_settings.NEEDED_GAS:
            print(cp, " Oralce owner need at least %r but has %r" % (script_settings.NEEDED_GAS, balance))
            return

        # register oracle
        is_subscribed = await staking_machine_service.is_subscribed(owner_addr, cp)
        if is_subscribed:
            print(cp, " ORACLE IS SUBSCRIBED, CANT REMOVE")
            return

        cps = await oracle_service.get_coin_pair_service(cp)
        registered = await cps.get_oracle_round_info(owner_addr)
        print(cp, " registered info", registered)

        round_info = await cps.get_round_info()
        print(cp, " round info", round_info)
        round_number = round_info.round

        num_idle_rounds = await cps.get_num_idle_rounds()
        if round_number - registered.selectedInCurrentRound < num_idle_rounds:
            print("must be idle for", num_idle_rounds, 'rounds and was only', round_number - registered.selectedInRound)
            return

        tx = await staking_machine_service.remove_oracle(account=script_settings.SCRIPT_ORACLE_OWNER_ACCOUNT,
                                                        wait=True)
        print("remove oracle", tx)


if __name__ == '__main__':
    helpers.run_main(main)
