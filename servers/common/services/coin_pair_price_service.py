import logging
from typing import List, Union

from hexbytes import HexBytes

from common.helpers import hb_to_bytes, dt_now_at_utc
from common.services.blockchain import BlockChainAddress, BlockchainAccount, is_error, BlockChainContract
from common.services.coin_pair_service_types import CoinPairServiceType
from common.services.oracle_dao import OracleRoundInfo, RoundInfo

from common import settings
from oracle.src.oracle_publish_message import PublishPriceParams, PublishTaskParams

logger = logging.getLogger(__name__)

class BaseCoinPairService:
    def __init__(self, contract: BlockChainContract):
        self.last_pub_at = None
        self._contract = contract

    @property
    def addr(self):
        return self._contract.addr
    
    async def coin_pair_call(self, method, *args, account: BlockchainAccount = None, **kw):
        return await self._contract.bc_call(method, *args, account=account, **kw)

    async def coin_pair_execute(self, method, *args, account: BlockchainAccount = None, wait=False,
                                      last_gas_price=None, gas: int = None, **kw):
        return await self._contract.bc_execute(method, *args, account=account, wait=wait,
                                               last_gas_price=last_gas_price, gas=gas, **kw)

    async def get_valid_price_period_in_blocks(self):
        return await self.coin_pair_call("getValidPricePeriodInBlocks")

    async def get_max_oracles_per_rounds(self):
        return await self.coin_pair_call("maxOraclesPerRound")

    async def can_remove_oracle(self, addr: BlockChainAddress):
        return await self.coin_pair_call("canRemoveOracle", addr)

    async def get_available_reward_fees(self):
        return await self.coin_pair_call("getAvailableRewardFees")

    async def get_coin_pair(self) -> str:
        return await self.coin_pair_call("coinPair")

    async def get_token_addr(self) -> str:
        return await self.coin_pair_call("getToken")

    async def get_last_pub_block(self) -> int:
        return await self.coin_pair_call("getLastPublicationBlock")

    async def get_round_info(self) -> RoundInfo:
        bc_data = await self.coin_pair_call("getRoundInfo")
        if is_error(bc_data):
            return bc_data
        return RoundInfo(*bc_data)

    async def switch_round(self, account: BlockchainAccount = None, wait=False,
                           last_gas_price=None):
        gas = settings.COIN_PAIR_SW_ROUND_GAS_LIMIT        
        return await self.coin_pair_execute(
            "switchRound", account=account, wait=wait, gas=gas, last_gas_price=last_gas_price)

    async def get_oracle_round_info(self, address: BlockChainAddress) -> OracleRoundInfo:
        bc_data = await self.coin_pair_call("getOracleRoundInfo", address)
        round_info_data = await self.get_round_info()
        if is_error(bc_data):
            return bc_data
        return OracleRoundInfo(*bc_data, round_info_data.round)


    async def _publish(self, params: Union[PublishPriceParams, PublishTaskParams], v: List[int], r: List[bytes], s: List[bytes], account: BlockchainAccount = None, wait=False, last_gas_price=None):
        raise NotImplementedError("Subclasses must implement the _publish method.")

    async def publish(self,
                            params: Union[PublishPriceParams, PublishTaskParams],
                            signatures: List[HexBytes],
                            account: BlockchainAccount = None,
                            wait=False, last_gas_price=None):
        v, r, s = [], [], []
        for signature in signatures:
            v.append(int.from_bytes(hb_to_bytes(signature[64:]), "little"))
            r.append(hb_to_bytes(signature[:32]))
            s.append(hb_to_bytes(signature[32:64]))
        logger.debug(f"OCS-----> {last_gas_price}")
        ret = await self._publish(params, v, r, s, account=account, wait=wait,
                                                 last_gas_price=last_gas_price)
        self.last_pub_at = dt_now_at_utc()
        return ret

class CoinPairService(BaseCoinPairService):
    def __init__(self, contract: BlockChainContract):
        super().__init__(contract)

    def get_service_type(self):
        return CoinPairServiceType.COIN_PAIR
    
    async def get_price(self):
        return await self.coin_pair_call("getPrice",
                                               account="0x" + "0" * 39 + "1")
    
    async def log_data(self):
        price = await self.get_price()
        return "price: %r " % price

    async def _publish(self, params: PublishPriceParams, v: List[int], r: List[bytes], s: List[bytes], account: BlockchainAccount = None, wait=False, last_gas_price=None):
        return await self.coin_pair_execute("publishPrice", params.version,
                                                  params.coin_pair.longer(), params.price, params.oracle_addr,
                                                  params.last_pub_block, v, r, s, account=account, wait=wait,
                                                 last_gas_price=last_gas_price)

class TasksRunnerService(BaseCoinPairService):
    def __init__(self, contract: BlockChainContract):
        super().__init__(contract)

    def get_service_type(self):
        return CoinPairServiceType.TASKS_RUNNER
    
    async def get_are_tasks_available(self) -> bool:
        ret = await self.coin_pair_call("areTasksAvailable")
        if is_error(ret):
            logger.warning("areTasksAvailable reverted, assuming false")
            return False
        return ret
    
    async def get_tasks_available(self):
        ret = await self.coin_pair_call("getTasksAvailable")
        if is_error(ret):
            logger.warning("getTasksAvailable reverted, assuming empty list")
            return []
        return ret

    async def get_tasks_available_as_flags(self):
        ret = await self.coin_pair_call("getTasksAvailableAsFlags")
        if is_error(ret):
            logger.warning("getTasksAvailableAsFlags reverted, assuming 0")
            return 0
        return ret
    
    async def log_data(self):
        tasks_available = await self.get_tasks_available()
        tasks_flags = await self.get_tasks_available_as_flags()
        return f"tasks available: {tasks_available!r} flags: {tasks_flags!r}"

    async def _publish(self, params: PublishTaskParams, v: List[int], r: List[bytes], s: List[bytes], account: BlockchainAccount = None, wait=False, last_gas_price=None):
        return await self.coin_pair_execute("runTasks", params.version,
                                                  params.coin_pair.longer(), params.tasks_flags, params.oracle_addr,
                                                  params.last_pub_block, v, r, s, account=account, wait=wait,
                                                 last_gas_price=last_gas_price)
