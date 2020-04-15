import asyncio
import logging
import typing

from common.bg_task_executor import BgTaskExecutor
from common.services import blockchain
from common.services.blockchain import is_error
from common.services.coin_pair_price_service import CoinPairPriceService
from common.services.oracle_dao import CoinPair, OracleRoundInfo
from oracle.src import oracle_settings

logger = logging.getLogger(__name__)

OracleBlockchainInfo = typing.NamedTuple("OracleBlockchainInfo",
                                         [("coin_pair", CoinPair),
                                          ('selected_oracles', typing.List[OracleRoundInfo]),
                                          ('blockchain_price', int),
                                          ('block_num', int),
                                          ('last_pub_block', int),
                                          ('last_pub_block_hash', str),
                                          ])


class OracleBlockchainInfoLoop(BgTaskExecutor):
    def __init__(self, cps: CoinPairPriceService):
        self._cps = cps
        self._coin_pair = cps.coin_pair
        self._blockchain_info: OracleBlockchainInfo = None
        super().__init__(self.task_loop)

    async def task_loop(self):
        data = await self._get_blocking()
        if data:
            self._blockchain_info = data
        return oracle_settings.ORACLE_BLOCKCHAIN_INFO_INTERVAL

    def get(self) -> OracleBlockchainInfo:
        return self._blockchain_info

    async def _get_blocking(self) -> OracleBlockchainInfo:
        async def _get_last_pub_data():
            lpb = await self._cps.get_last_pub_block()
            lpbh = await self._cps.get_last_pub_block_hash(lpb)
            return lpb, lpbh

        cors = [self._cps.get_selected_oracles_info(),
                self._cps.get_price(),
                blockchain.get_last_block(),
                _get_last_pub_data()]
        ret = await asyncio.gather(*cors, return_exceptions=True)
        if any(is_error(elem) for elem in ret):
            logger.warning("Error getting blockchain info %r" % (ret,))
            return None
        (selected_oracles, blockchain_price, block_num, (last_pub_block, last_pub_block_hash)) = ret
        return OracleBlockchainInfo(self._coin_pair, selected_oracles,
                                    blockchain_price, block_num, last_pub_block, last_pub_block_hash)