import logging
from typing import List

from hexbytes import HexBytes

from common.helpers import hb_to_bytes, dt_now_at_utc
from common.services.blockchain import BlockChainAddress, BlockchainAccount, is_error, BlockChainContract
from common.services.oracle_dao import OracleRoundInfo, RoundInfo

from common import settings

logger = logging.getLogger(__name__)


class CoinPairService:
    def __init__(self, contract: BlockChainContract):
        self.last_pub_at = None
        self._contract = contract

    @property
    def addr(self):
        return self._contract.addr

    async def coin_pair_price_call(self, method, *args, account: BlockchainAccount = None, **kw):
        return await self._contract.bc_call(method, *args, account=account, **kw)

    async def coin_pair_price_execute(self, method, *args, account: BlockchainAccount = None, wait=False,
                                      last_gas_price=None, gas: int = None, **kw):
        return await self._contract.bc_execute(method, *args, account=account, wait=wait,
                                               last_gas_price=last_gas_price, gas=gas, **kw)

    async def get_valid_price_period_in_blocks(self):
        return await self.coin_pair_price_call("getValidPricePeriodInBlocks")

    async def get_max_oracles_per_rounds(self):
        return await self.coin_pair_price_call("maxOraclesPerRound")

    async def can_remove_oracle(self, addr: BlockChainAddress):
        return await self.coin_pair_price_call("canRemoveOracle", addr)

    async def get_price(self):
        return await self.coin_pair_price_call("getPrice",
                                               account="0x" + "0" * 39 + "1")

    async def get_available_reward_fees(self):
        return await self.coin_pair_price_call("getAvailableRewardFees")

    async def publish_price(self,
                            version,
                            coin_pair,
                            price,
                            oracle_addr,
                            blocknumber,
                            signatures: List[HexBytes],
                            account: BlockchainAccount = None,
                            wait=False, last_gas_price=None):
        v, r, s = [], [], []
        for signature in signatures:
            v.append(int.from_bytes(hb_to_bytes(signature[64:]), "little"))
            r.append(hb_to_bytes(signature[:32]))
            s.append(hb_to_bytes(signature[32:64]))
        logger.debug(f"OCS-----> {last_gas_price}")
        ret = await self.coin_pair_price_execute("publishPrice", version,
                                                  coin_pair.longer(), price, oracle_addr,
                                                  blocknumber, v, r, s, account=account, wait=wait,
                                                 last_gas_price=last_gas_price)
        self.last_pub_at = dt_now_at_utc()
        return ret

    async def get_coin_pair(self) -> str:
        return await self.coin_pair_price_call("coinPair")

    async def get_token_addr(self) -> str:
        return await self.coin_pair_price_call("getToken")

    async def get_last_pub_block(self) -> int:
        return await self.coin_pair_price_call("getLastPublicationBlock")

    async def get_round_info(self) -> RoundInfo:
        bc_data = await self.coin_pair_price_call("getRoundInfo")
        if is_error(bc_data):
            return bc_data
        return RoundInfo(*bc_data)

    async def switch_round(self, account: BlockchainAccount = None, wait=False):
        gas = settings.COIN_PAIR_SW_ROUND_GAS_LIMIT
        return await self.coin_pair_price_execute("switchRound", account=account, wait=wait, gas=gas)

    async def get_oracle_round_info(self, address: BlockChainAddress) -> OracleRoundInfo:
        bc_data = await self.coin_pair_price_call("getOracleRoundInfo", address)
        round_info_data = await self.get_round_info()
        if is_error(bc_data):
            return bc_data
        return OracleRoundInfo(*bc_data, round_info_data.round)
