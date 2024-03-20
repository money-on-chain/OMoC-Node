import logging

from common.bg_task_executor import BgTaskExecutor
from common.services.blockchain import is_error, BlockchainStateLoop
from oracle.src import oracle_settings
from oracle.src.oracle_coin_pair_service import OracleCoinPairService
from oracle.src.oracle_configuration import OracleConfiguration

logger = logging.getLogger(__name__)


class SchedulerCoinPairLoop(BgTaskExecutor):
    def __init__(self, conf: OracleConfiguration, cps: OracleCoinPairService,
                 bs_loop: BlockchainStateLoop):
        self.bs_loop = bs_loop
        self._conf = conf
        self._cps = cps
        self._coin_pair = cps.coin_pair
        super().__init__(name="SchedulerCoinPairLoop", main=self.run)

    async def run(self):
        self.log("start")

        round_info = await self._cps.get_round_info()
        if is_error(round_info):
            self.error("error get_round_info error %r" % (round_info,))
            return self._conf.SCHEDULER_POOL_DELAY
        self.log("Round %r" % (round_info,))

        block_timestamp = await self._cps.get_last_block_timestamp()
        if not self._is_right_block(round_info, block_timestamp):
            return self._conf.SCHEDULER_POOL_DELAY

        receipt = await self._cps.switch_round(
            account=oracle_settings.get_oracle_scheduler_account(),
            wait=True,
            last_gas_price=self.bs_loop.gas_calc.get_current())
        
        if is_error(receipt):
            self.error("error in switch_round tx %r" % (receipt,))
            return self._conf.SCHEDULER_POOL_DELAY

        self.log("round switched %r" % (receipt.hash,))
        return self._conf.SCHEDULER_ROUND_DELAY

    def _is_right_block(self, round_info, block_timestamp):
        if is_error(block_timestamp):
            self.error("error get_last_block error %r" % (block_timestamp,))
            return False
        if round_info.lockPeriodTimestamp > block_timestamp:
            self.log("The round is running, wait %r < %r " %
                     (block_timestamp, round_info.lockPeriodTimestamp))
            return False
        self.log("Current block %r" % (block_timestamp,))
        return True

    def log(self, msg):
        logger.info("SchedulerCoinPairLoop : %r : %s" % (self._coin_pair, msg))

    def error(self, msg):
        logger.error("SchedulerCoinPairLoop : %r : %s" % (self._coin_pair, msg))
