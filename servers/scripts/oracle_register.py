from common import helpers
from common.services.blockchain import is_error
from scripts import script_settings


async def main():
    oracle_account = script_settings.SCRIPT_ORACLE_ACCOUNT
    oracle_addr = str(oracle_account.addr)
    print("ORACLE ADDR", oracle_addr)
    print("ORACLE OWNER ADDR", script_settings.SCRIPT_ORACLE_OWNER_ACCOUNT.addr)
    conf, oracle_service, oracle_manager_service, moc_token_service, staking_machine_service, staking_machine_addr = await script_settings.configure_oracle()

    balance = await script_settings.blockchain.get_balance(script_settings.SCRIPT_ORACLE_OWNER_ACCOUNT.addr)
    print("Oracle owner coinbase balance ", balance)
    if balance < script_settings.NEEDED_GAS:
        print("Oralce owner need at least %r but has %r" % (script_settings.NEEDED_GAS, balance))
        return

    moc_balance = await moc_token_service.balance_of(script_settings.SCRIPT_ORACLE_OWNER_ACCOUNT.addr)
    print("Oracle owner moc balance ", moc_balance)
    if moc_balance < script_settings.INITIAL_STAKE * 2:
        tx = await moc_token_service.transfer(script_settings.SCRIPT_ORACLE_OWNER_ACCOUNT.addr,
                                              script_settings.INITIAL_STAKE * 2,
                                              account=script_settings.SCRIPT_REWARD_BAG_ACCOUNT,
                                              wait=True)
        if is_error(tx):
            print("ERROR IN APPROVE", tx)
            return

    # move some rsks to my account
    balance = await script_settings.blockchain.get_balance(oracle_addr)
    print("price fetcher coinbase balance", balance)
    if balance < script_settings.NEEDED_GAS:
        tx = await script_settings.blockchain.bc_transfer(oracle_addr,
                                                          script_settings.NEEDED_GAS,
                                                          account=script_settings.SCRIPT_ORACLE_OWNER_ACCOUNT,
                                                          wait=True)
        print("rbtc transfer", tx)

    # register oracle
    registered = await oracle_manager_service.get_oracle_registration_info(script_settings.SCRIPT_ORACLE_OWNER_ACCOUNT.addr)
    if is_error(registered):
        tx = await staking_machine_service.register_oracle(script_settings.SCRIPT_ORACLE_OWNER_ACCOUNT,
                                                           oracle_addr,
                                                           "http://localhost:5556",
                                                           account=script_settings.SCRIPT_ORACLE_OWNER_ACCOUNT,
                                                           wait=True)
        print("register oracle is ok to fail", tx)

    registered = await oracle_manager_service.get_oracle_registration_info(script_settings.SCRIPT_ORACLE_OWNER_ACCOUNT.addr)
    print("registered", registered)
    if registered.owner:
        print("ORACLE ALREADY APPROVED, WE ARE DONE")
        return


if __name__ == '__main__':
    helpers.run_main(main)
