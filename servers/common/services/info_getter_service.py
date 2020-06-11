import logging

from common.services.blockchain import BlockchainAccount, BlockChainContract
from common.services.coin_pair_price_service import CoinPairService
from common.services.oracle_manager_service import OracleManagerService

logger = logging.getLogger(__name__)


class InfoGetterService:

    def __init__(self, contract: BlockChainContract):
        self._contract = contract

    async def coin_pair_price_call(self, method, *args, account: BlockchainAccount = None, **kw):
        return await self._contract.bc_call(method, *args, account=account, **kw)

    async def coin_pair_price_execute(self, method, *args, account: BlockchainAccount = None, wait=False, **kw):
        return await self._contract.bc_execute(method, *args, account=account, wait=wait, **kw)

    async def get_oracle_server_info(self, oracle_manager: OracleManagerService, coin_pair_price: CoinPairService):
        return await self.coin_pair_price_call("getOracleServerInfo", oracle_manager.addr, coin_pair_price.addr)
