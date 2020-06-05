import logging
import typing

from common.services.blockchain import BlockChainAddress, BlockchainAccount, BlockChainContract, is_error

logger = logging.getLogger(__name__)

SupportersDetailedBalance = typing.NamedTuple("SupportersDetailedBalance",
                                              [("stopped", int),
                                               ("stopped_in_block", int),
                                               ])


class SupportersService:

    def __init__(self, contract: BlockChainContract):
        self._contract = contract

    async def supporters_call(self, method, *args, **kw):
        return await self._contract.bc_call(method, *args, **kw)

    async def supporters_execute(self, method, *args, account: BlockchainAccount = None, wait=False, **kw):
        return await self._contract.bc_execute(method, *args, account=account, wait=wait, **kw)

    async def get_token_addr(self):
        return await self.supporters_call("mocToken")

    async def is_ready_to_distribute(self) -> bool:
        return await self.supporters_call("isReadyToDistribute")

    async def distribute(self, account: BlockchainAccount = None, wait=False):
        return await self.supporters_execute("distribute", account=account, wait=wait)

    async def get_moc_balance_at(self, user: BlockChainAddress, addr: BlockChainAddress):
        return await self.supporters_call("getMOCBalanceAt", user, addr)

    async def get_token_balance_at(self, user: BlockChainAddress, addr: BlockChainAddress):
        return await self.supporters_call("getBalanceAt", user, addr)

    async def vesting_info_of(self, user: BlockChainAddress, addr: BlockChainAddress) -> SupportersDetailedBalance:
        data = await self.supporters_call("vestingInfoOf", user, addr)
        if is_error(data):
            return data
        return SupportersDetailedBalance(*data)

    async def get_total_tokens(self):
        return await self.supporters_call("getTokens")

    async def get_total_mocs(self):
        return await self.supporters_call("getAvailableMOC")

    async def get_earning_at(self, block):
        return await self.supporters_call("getEarningsAt", block)

    async def get_locked_at(self, block):
        return await self.supporters_call("getLockedAt", block)

    async def get_earnings_info(self, block):
        return await self.supporters_call("getEarningsInfo", block)
