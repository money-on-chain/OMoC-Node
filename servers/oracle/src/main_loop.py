import logging
from typing import List

from common import settings
from common.bg_task_executor import BgTaskExecutor
from common.services.blockchain import BlockchainStateLoop
from common.services.contract_factory_service import ContractFactoryService
from oracle.src import oracle_settings, monitor
from oracle.src.ip_filter_loop import IpFilterLoop
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.oracle_loop import OracleLoop
from oracle.src.oracle_service import OracleService
from oracle.src.scheduler_supporters_loop import SchedulerSupportersLoop


logger = logging.getLogger(__name__)


class MainLoop(BgTaskExecutor):
    def __init__(self):
        self.cf = ContractFactoryService.get_contract_factory_service()
        self.conf = OracleConfiguration(self.cf)
        self.tasks: List[BgTaskExecutor] = []
        self.initialized = False
        self.oracle_loop: OracleLoop = None
        self.bs_loop: BlockchainStateLoop = None
        self.ip_filter_loop: IpFilterLoop = None
        super().__init__(name="MainLoop", main=self.run)

    async def web_server_startup(self):
        await self.conf.initialize()
        self.start_bg_task()

    async def scheduler_alone_startup(self):
        await self.conf.initialize()
        await self.start_bg_task()

    async def run(self):
        logger.debug("MainExecutor loop start")
        if not self.initialized:
            if self.conf.ORACLE_MANAGER_ADDR is None or self.conf.SUPPORTERS_ADDR is None:
                logger.warning("MainExecutor waiting to get configuration from blockchain")
                return self.conf.ORACLE_MAIN_EXECUTOR_TASK_INTERVAL
            self.initialized = True
            self._print_info()
            self._startup()

        await self.conf.update()
        # TODO: react to a change in addresses.
        logger.debug("MainExecutor loop done")
        return self.conf.ORACLE_CONFIGURATION_TASK_INTERVAL

    def _startup(self):
        oracle_service = OracleService(self.cf, self.conf.ORACLE_MANAGER_ADDR, self.conf.INFO_ADDR)
        self.bs_loop = BlockchainStateLoop(self.conf, self.cf, settings.GAS_LIMIT_ADDR)
        self.oracle_loop = OracleLoop(self.conf, oracle_service, self.bs_loop)
        self.tasks.append(self.oracle_loop)
        self.tasks.append(self.bs_loop)
        if oracle_settings.ORACLE_RUN_IP_FILTER:
            self.ip_filter_loop = IpFilterLoop(self.oracle_loop, self.conf)
            self.tasks.append(self.ip_filter_loop)
        if oracle_settings.ORACLE_MONITOR_RUN:
            monitor.log_setup()
            self.tasks.append(monitor.MonitorTask(self.cf.get_blockchain(), oracle_service))
        if oracle_settings.SCHEDULER_RUN_SUPPORTERS_SCHEDULER:
            supporters_service = self.cf.get_supporters(self.conf.SUPPORTERS_ADDR)
            self.tasks.append(SchedulerSupportersLoop(self.conf, supporters_service,self.bs_loop))
        for t in self.tasks:
            logger.debug(f'****** task {t}')
            t.start_bg_task()

    def _print_info(self):
        logger.info("=== Money-On-Chain Reference Oracle Starting up ===")
        logger.info("    Address: " + oracle_settings.get_oracle_account().addr)
        logger.info("    Loop main task interval: " + str(self.conf.ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL))
        logger.info("    Loop per-coin task interval: " + str(self.conf.ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL))
        logger.info("    Loop blockchain loop interval: " + str(self.conf.ORACLE_BLOCKCHAIN_INFO_INTERVAL))
        if settings.NODE_URL is not None:
            logger.info("    Node url %s" % str(settings.NODE_URL))
        if settings.DEBUG:
            logger.info("    DEBUG")
        if settings.MOC_NETWORK is not None:
            logger.info("    Using moneyonchain library to get abis and addresses")

    def shutdown(self):
        for t in self.tasks:
            t.stop_bg_task()
        self.stop_bg_task()

    async def get_validation_data(self, params):
        if self.oracle_loop is None:
            return None
        return await self.oracle_loop.get_validation_data(params)

    def is_valid_ip(self, ip):
        if self.ip_filter_loop is None:
            logger.warning("Trying to filter ip while filter isn't yet up..")
            return False
        return self.ip_filter_loop.is_valid_ip(ip)
