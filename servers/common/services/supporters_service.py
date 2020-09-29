import logging
import typing

from common.services.blockchain import BlockchainAccount, BlockChainContract

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

    async def get_total_tokens(self):
        return await self.supporters_call("totalToken")

    async def get_total_mocs(self):
        return await self.supporters_call("totalMoc")

    async def get_priod(self):
        return await self.supporters_call("period")
