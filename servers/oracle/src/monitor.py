import logging

from common.bg_task_executor import BgTaskExecutor
from common.services.blockchain import get_last_block, is_error
from common.services.coin_pair_price_service import CoinPairPriceService
from oracle.src import oracle_service
from oracle.src.select_next import select_next


class MonitorLoopByCoinPair:

    def __init__(self, logger, cps: CoinPairPriceService):
        self._logger = logger
        self._cps = cps
        self._pre_pubblock_nr = None

    async def run(self):
        # published-block
        pubblock_nr = await self._cps.get_last_pub_block()
        if self._pre_pubblock_nr == pubblock_nr:
            return 5
        self._pre_pubblock_nr = pubblock_nr

        price = await self._cps.get_price()
        pubblock_hash = await self._cps.get_last_pub_block_hash(pubblock_nr)
        oracles = await self._cps.get_selected_oracles_info()
        if is_error(oracles):
            self._logger.error("Error getting oracles %r" % (oracles,))
            return 5
        self._logger.info("block %r published price: %r " % (pubblock_nr, price))
        sorted_oracles = select_next(pubblock_hash, oracles)
        for idx, oracle_addr in enumerate(sorted_oracles):
            self._logger.debug(" turn: %d  oracle: %s " % (idx, oracle_addr))
        self._logger.debug("---------")
        return 5


class MonitorTask(BgTaskExecutor):

    def __init__(self):
        super().__init__(self.monitor_loop)
        self.logger = logging.getLogger("published_price")
        self.prev_block = self.pre_pubblock_nr = None
        self.cpMap = {}

    async def monitor_loop(self):
        # blockchain-block
        block = await get_last_block()
        if is_error(block):
            self.logger.error("Error getting last block %r" % (block,))
            return 5
        if self.prev_block == block:
            return 5
        self.prev_block = block
        pairs = await oracle_service.get_all_coin_pair_service()
        if is_error(pairs):
            self.logger.error("Can't retrieve coinpairs")
            return 5
        for cps in pairs:
            cp_key = str(cps.coin_pair)
            if not self.cpMap.get(cp_key):
                self.logger.info("%r : Adding New coinpair" % cps.coin_pair)
                self.cpMap[cp_key] = MonitorLoopByCoinPair(self.logger, cps)
            await self.cpMap[cp_key].run()
        return 5