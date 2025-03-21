import logging

from common.bg_task_executor import BgTaskExecutor
from common.services.blockchain import is_error, BlockchainStateLoop
from oracle.src import oracle_settings
from oracle.src.oracle_configuration import OracleConfiguration

logger = logging.getLogger(__name__)


class SchedulerSupportersLoop(BgTaskExecutor):

    def __init__(self, conf: OracleConfiguration, supporters_service,bs_loop: BlockchainStateLoop):
        self.conf = conf
        self.supporters_service = supporters_service
        self.bs_loop = bs_loop
        super().__init__(name="SchedulerSupportersLoop", main=self.run)

    async def run(self):
        #logger.info("SchedulerSupportersLoop start")
        is_ready_to_distribute = await self.supporters_service.is_ready_to_distribute()
        if is_error(is_ready_to_distribute):
            #logger.error("SchedulerSupportersLoop error getting is_ready_to_distribute %r" % (is_ready_to_distribute,))
            return self.conf.SCHEDULER_POOL_DELAY

        if not is_ready_to_distribute:
            #logger.info("SchedulerSupportersLoop not ready to distribute, wait...")
            return self.conf.SCHEDULER_POOL_DELAY

        receipt = await self.supporters_service.distribute(account=oracle_settings.get_supporters_scheduler_account(),
                                                           wait=True,
                                                           last_gas_price=await self.bs_loop.gas_calc.get_current())
        if is_error(receipt):
            #logger.error("SchedulerSupportersLoop error in distribute tx %r" % (receipt,))
            return self.conf.SCHEDULER_POOL_DELAY

        #logger.info("SchedulerSupportersLoop round switched %r" % receipt.hash)
        return self.conf.SCHEDULER_ROUND_DELAY
