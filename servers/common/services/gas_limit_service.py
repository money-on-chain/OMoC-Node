from common.services.blockchain import BlockChainContract


class GasLimitService:

    def __init__(self, contract: BlockChainContract):
        self._contract = contract

    async def _call(self, method, *args, **kw):
        return await self._contract.bc_call(method, *args, **kw)

    async def value(self) -> int:
        return await self._call("maxGasPrice")
