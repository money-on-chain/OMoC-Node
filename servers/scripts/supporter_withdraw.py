from common import helpers
from common.services.blockchain import is_error
from common.services.moc_token_service import MocTokenService
from common.services.supporters_service import SupportersService
from scripts.script_settings import SCHEDULER_ACCOUNT

REWARDS_ACCOUNT = SCHEDULER_ACCOUNT

supporters_service = SupportersService()
moc_token_service = MocTokenService()


# Take from scheduler addr into reward bag addr
async def main():
    print("AVAILABLE MOCS BEFORE: ", await moc_token_service.balance_of(SCHEDULER_ACCOUNT.addr))
    print("STAKE BEFORE: ", await supporters_service.detailed_balance_of(SCHEDULER_ACCOUNT.addr))

    tx = await supporters_service.withdraw(account=REWARDS_ACCOUNT, wait=True)
    if is_error(tx):
        print("ERROR IN WITHDRAW", tx)
        return

    print("AVAILABLE MOCS AFTER: ", await moc_token_service.balance_of(SCHEDULER_ACCOUNT.addr))
    print("STAKE AFTER: ", await supporters_service.detailed_balance_of(SCHEDULER_ACCOUNT.addr))


if __name__ == '__main__':
    helpers.run_main(main)
