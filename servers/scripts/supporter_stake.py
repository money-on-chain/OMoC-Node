from common import helpers
from common.services import moc_service, supporters_service
from common.services.blockchain import is_error
from scripts.script_settings import SCHEDULER_ACCOUNT, INITIAL_STAKE

REWARDS_ACCOUNT = SCHEDULER_ACCOUNT


# Take from scheduler addr into reward bag addr
async def main():
    available_mocs = await moc_service.balance_of(SCHEDULER_ACCOUNT.addr)
    print("AVAILABLE MOCS: ", available_mocs)
    if available_mocs < INITIAL_STAKE:
        tx = await moc_service.mint(SCHEDULER_ACCOUNT.addr, INITIAL_STAKE,
                                    account=SCHEDULER_ACCOUNT,
                                    wait=True)
        if is_error(tx):
            print("ERROR IN APPROVE", tx)
            return

    print("STAKE BEFORE: ", await supporters_service.detailed_balance_of(SCHEDULER_ACCOUNT.addr))

    token_approved = await moc_service.allowance(SCHEDULER_ACCOUNT.addr, supporters_service.SUPPORTERS_ADDR)
    print("tokenApproved", token_approved)
    if token_approved < INITIAL_STAKE:
        tx = await moc_service.approve(supporters_service.SUPPORTERS_ADDR,
                                       INITIAL_STAKE,
                                       account=SCHEDULER_ACCOUNT,
                                       wait=True)
        print("token approve", tx)

    tx = await supporters_service.add_stake(INITIAL_STAKE,
                                            account=REWARDS_ACCOUNT,
                                            wait=True)
    if is_error(tx):
        print("ERROR IN APPROVE", tx)
        return
    print("STAKE AFTER: ", await supporters_service.detailed_balance_of(SCHEDULER_ACCOUNT.addr))


if __name__ == '__main__':
    helpers.run_main(main)