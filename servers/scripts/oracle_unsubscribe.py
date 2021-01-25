from common import helpers
from scripts import script_settings


async def main():
    oracle_account = script_settings.SCRIPT_ORACLE_ACCOUNT
    oracle_addr = str(oracle_account.addr)
    owner_account = script_settings.SCRIPT_ORACLE_OWNER_ACCOUNT
    owner_addr = str(owner_account.addr)
    print("ORACLE ADDR", oracle_addr)
    print("ORACLE OWNER ADDR", owner_addr)

    conf, oracle_service, oracle_manager_service, moc_token_service, staking_machine_service, staking_machine_addr = await script_settings.configure_oracle()

    registered = await staking_machine_service.is_oracle_registered(owner_addr)
    if not registered:
        print("ORACLE NOT REGISTERED")
        return

    for cp in script_settings.USE_COIN_PAIR:
        is_subscribed = await staking_machine_service.is_subscribed(owner_addr,
                                                                    cp)
        print(cp, " IS SUBSCRIBED: ", is_subscribed)
        if is_subscribed:
            tx = await staking_machine_service.unsubscribe_from_coin_pair(cp,
                                                                          account=owner_account,
                                                                          wait=True)

            print("unsubscribe from coinpar", cp, " result ", tx)


if __name__ == '__main__':
    helpers.run_main(main)
