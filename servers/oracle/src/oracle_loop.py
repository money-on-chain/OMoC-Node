import logging
import typing

from common.bg_task_executor import BgTaskExecutor
from common.services.blockchain import is_error, BlockchainStateLoop
from oracle.src import oracle_settings
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfoLoop, OracleBlockchainInfo
from oracle.src.oracle_coin_pair_loop import OracleCoinPairLoop
from oracle.src.oracle_coin_pair_service import OracleCoinPairService
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.oracle_publish_message import PublishPriceParams, PublishTaskParams
from oracle.src.oracle_service import OracleService
from oracle.src.oracle_turn import PriceOracleTurn, TasksOracleTurn
from oracle.src.price_feeder.price_feeder import PriceFeederLoop
from oracle.src.request_validation import PriceRequestValidation, TaskRequestValidation
from oracle.src.scheduler_oracle_loop import SchedulerCoinPairLoop
from oracle.src.coin_pair_runner import CoinPairRunner
from oracle.src.tasks_runner import TasksRunner
from typing import Union

logger = logging.getLogger(__name__)

OracleLoopTasks = typing.NamedTuple("OracleLoopTasks",
                                    [("coin_pair_service", OracleCoinPairService),
                                     ("tasks", typing.List[BgTaskExecutor]),
                                     ("coin_pair_loop", OracleCoinPairLoop),
                                     ("runner", Union[CoinPairRunner, TasksRunner]),
                                     ("blockchain_info_loop", OracleBlockchainInfoLoop),
                                     ("oracle_turn", Union[PriceOracleTurn, TasksOracleTurn])
                                     ])


class OracleLoop(BgTaskExecutor):

    def __init__(self, conf: OracleConfiguration, oracle_service: OracleService,
                 bs_loop: BlockchainStateLoop):
        self.bs_loop = bs_loop
        self.conf = conf
        self.oracle_addr = oracle_settings.get_oracle_account().addr
        self.oracle_service = oracle_service
        self.cpMap: typing.Dict[str, OracleLoopTasks] = {}
        super().__init__(name="OracleLoop", main=self.run)

    def stop_bg_task(self):
        for cp_key in self.cpMap:
            self.delete_coin_pair(cp_key)
        super().stop_bg_task()

    def delete_coin_pair(self, cp_key):
        logger.info("Oracle loop Deleted coin pair %r stop it" % cp_key)
        old = self.cpMap.pop(cp_key)
        for x in old.tasks:
            x.stop_bg_task()

    def add_coin_pair(self, cp_service):
        cp_key = str(cp_service.coin_pair)
        logger.info("Oracle loop Adding New coin pair %r" % cp_key)
        tasks = []
        if oracle_settings.ORACLE_RUN:
            bl_loop = OracleBlockchainInfoLoop(self.conf, cp_service)
            if cp_service.coin_pair_type == cp_service.CoinPairServiceType.COIN_PAIR:
                pf_loop = PriceFeederLoop(self.conf, cp_service.coin_pair)
                runner = CoinPairRunner(self.conf, pf_loop, cp_service, bl_loop)
                tasks.extend([pf_loop])
            if cp_service.coin_pair_type == cp_service.CoinPairServiceType.TASKS_RUNNER:
                runner = TasksRunner(self.conf, cp_service, bl_loop)
            cp_loop = OracleCoinPairLoop(self.conf, runner, self.bs_loop)
            tasks.extend([bl_loop, cp_loop])
            self.cpMap[cp_key] = OracleLoopTasks(cp_service, tasks,
                                                 cp_loop, runner, bl_loop,
                                                 runner.oracle_turn)
        if oracle_settings.SCHEDULER_RUN_ORACLE_SCHEDULER:
            tasks.append(SchedulerCoinPairLoop(self.conf, cp_service, self.bs_loop))
        for x in tasks:
            x.start_bg_task()

    async def run(self):
        #logger.info("Oracle loop start")
        owner = await self.oracle_service.get_oracle_owner(self.oracle_addr)
        cp_serv1 = await self.oracle_service.get_subscribed_coin_pair_services(self.oracle_addr)
        cp_serv2 = await self.oracle_service.get_subscribed_coin_pair_services(owner)

        if is_error(cp_serv1) and is_error(cp_serv2):
            logger.error("Oracle loop Error getting coin pairs %r / %r" %
                         (cp_serv1, cp_serv2))
            return self.conf.ORACLE_MAIN_LOOP_TASK_INTERVAL

        cp_services = {str(x.coin_pair): x for x in cp_serv1+cp_serv2}
        coin_pair_keys = list(cp_services.keys())
        # logger.info("Oracle loop Got coin pair list %r" % (coin_pair_keys,))
        deleted_coin_pairs = [x for x in self.cpMap if x not in coin_pair_keys]
        for cp_key in deleted_coin_pairs:
            self.delete_coin_pair(cp_key)

        added_services = [x for k, x in cp_services.items() if not
                          (k in self.cpMap)]
        for cp_service in added_services:
            self.add_coin_pair(cp_service)

        # logger.info("Oracle loop done")
        return self.conf.ORACLE_MAIN_LOOP_TASK_INTERVAL

    async def get_validation_data(self, params: Union[PublishPriceParams, PublishTaskParams]) -> Union[PriceRequestValidation, TaskRequestValidation, None]:
        tasks: OracleLoopTasks = self.cpMap.get(str(params.coin_pair))
        if not tasks or not tasks.runner:
            return

        return await tasks.runner.create_validator(params)

    async def get_full_blockchain_info(self) -> typing.Dict[str, OracleBlockchainInfo]:
        return {cp_key: task.blockchain_info_loop.get()
                for (cp_key, task) in self.cpMap.items()}
