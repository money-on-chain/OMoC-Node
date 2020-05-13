from common import helpers
from common.services.blockchain import is_error
from common.services.moc_token_service import MocTokenService
from common.services.supporters_service import SupportersService
from scripts import script_settings

supporters_service = SupportersService()
moc_token_service = MocTokenService()


# Take from scheduler addr into reward bag addr
async def main():
    print("STAKE BEFORE: ",
          await supporters_service.detailed_balance_of(script_settings.SCRIPT_REWARD_BAG_ACCOUNT.addr))

    tx = await supporters_service.stop(account=script_settings.SCRIPT_REWARD_BAG_ACCOUNT, wait=True)
    if is_error(tx):
        print("ERROR IN APPROVE", tx)
        return

    print("STAKE AFTER: ", await supporters_service.detailed_balance_of(script_settings.SCRIPT_REWARD_BAG_ACCOUNT.addr))


if __name__ == '__main__':
    helpers.run_main(main)
