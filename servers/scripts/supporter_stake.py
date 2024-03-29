from common import helpers
from common.services.blockchain import is_error
from scripts import script_settings


# Take from scheduler addr into reward bag addr
async def main():
    conf, supporters_service, moc_token_service = await script_settings.configure_supporter()
    available_mocs = await moc_token_service.balance_of(script_settings.SCRIPT_REWARD_BAG_ACCOUNT.addr)
    print("AVAILABLE MOCS: ", available_mocs)
    if available_mocs < script_settings.INITIAL_STAKE:
        raise Exception("WE MUST MINT BY GOBERNANZA, check contacts/scripts/mint_tokens.js!!!")

    print("STAKE BEFORE: ",
          await moc_token_service.balance_of(script_settings.SCRIPT_REWARD_BAG_ACCOUNT.addr))

    token_approved = await moc_token_service.allowance(script_settings.SCRIPT_REWARD_BAG_ACCOUNT.addr,
                                                       conf.SUPPORTERS_ADDR)
    print("tokenApproved", token_approved)
    if token_approved < script_settings.INITIAL_STAKE:
        tx = await moc_token_service.approve(conf.SUPPORTERS_ADDR,
                                             script_settings.INITIAL_STAKE,
                                             account=script_settings.SCRIPT_REWARD_BAG_ACCOUNT,
                                             wait=True)
        print("token approve", tx)

    tx = await moc_token_service.transfer(conf.SUPPORTERS_ADDR,
                                          script_settings.INITIAL_STAKE,
                                          account=script_settings.SCRIPT_REWARD_BAG_ACCOUNT,
                                          wait=True)

    if is_error(tx):
        print("ERROR IN APPROVE", tx)
        return
    print("STAKE AFTER: ", await moc_token_service.balance_of(script_settings.SCRIPT_REWARD_BAG_ACCOUNT.addr))


if __name__ == '__main__':
    helpers.run_main(main)
