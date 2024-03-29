from common import helpers
from common.services.blockchain import is_error
from scripts import script_settings


# Take from scheduler addr into reward bag addr
async def main():
    conf, oracle_service, oracle_manager_service, moc_token_service, staking_machine_service, staking_machine_addr = await script_settings.configure_oracle()

    for cp in script_settings.USE_COIN_PAIR:
        cps = await oracle_service.get_coin_pair_service(cp)
        print(cp, " REWARDS BEFORE: ", await cps.get_available_reward_fees())

        balance = await moc_token_service.balance_of(script_settings.SCRIPT_REWARD_BAG_ACCOUNT.addr)
        print(cp, " REWARD ACCOUNT BALANCE: ", balance)
        if balance < script_settings.REWARDS:
            raise Exception("WE MUST MINT BY GOBERNANZA, check contacts/scripts/mint_tokens.js!!!")

        tx = await moc_token_service.transfer(cps.addr, script_settings.REWARDS,
                                              account=script_settings.SCRIPT_REWARD_BAG_ACCOUNT,
                                              wait=True)
        if is_error(tx):
            print("ERROR IN TRANSFER", tx)
            return
        print(cp, " REWARDS AFTER: ", await cps.get_available_reward_fees())


if __name__ == '__main__':
    helpers.run_main(main)
