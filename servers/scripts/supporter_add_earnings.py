from common import helpers
from scripts import script_settings


# Take from scheduler addr into reward bag addr
async def main():
    conf, moc_token_service = await script_settings.configure_supporter()

    available_mocs = await moc_token_service.balance_of(script_settings.SCRIPT_REWARD_BAG_ACCOUNT.addr)
    print("AVAILABLE MOCS: ", available_mocs)
    if available_mocs < script_settings.REWARDS:
        raise Exception("WE MUST MINT BY GOBERNANZA, check contacts/scripts/mint_tokens.js!!!")

    tx = await moc_token_service.transfer(conf.SUPPORTERS_VESTED_ADDR,
                                          script_settings.REWARDS,
                                          account=script_settings.SCRIPT_REWARD_BAG_ACCOUNT,
                                          wait=True)
    print("token transfer", tx)


if __name__ == '__main__':
    helpers.run_main(main)
