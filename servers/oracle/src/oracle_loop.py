import logging
import typing

from common.bg_task_executor import BgTaskExecutor
from common.services.blockchain import is_error, BlockchainStateLoop
from oracle.src import oracle_settings
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfoLoop, OracleBlockchainInfo
from oracle.src.oracle_coin_pair_loop import OracleCoinPairLoop
from oracle.src.oracle_coin_pair_service import OracleCoinPairService
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.oracle_publish_message import PublishPriceParams
from oracle.src.oracle_service import OracleService
from oracle.src.oracle_turn import OracleTurn
from oracle.src.price_feeder.price_feeder import PriceFeederLoop
from oracle.src.request_validation import RequestValidation
from oracle.src.scheduler_oracle_loop import SchedulerCoinPairLoop

logger = logging.getLogger(__name__)

OracleLoopTasks = typing.NamedTuple("OracleLoopTasks",
                                    [("coin_pair_service", OracleCoinPairService),
                                     ("tasks", typing.List[BgTaskExecutor]),
                                     ("coin_pair_loop", OracleCoinPairLoop),
                                     ("price_feeder_loop", PriceFeederLoop),
                                     ("blockchain_info_loop", OracleBlockchainInfoLoop),
                                     ("oracle_turn", OracleTurn)
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
            pf_loop = PriceFeederLoop(self.conf, cp_service.coin_pair)
            bl_loop = OracleBlockchainInfoLoop(self.conf, cp_service)
            cp_loop = OracleCoinPairLoop(self.conf, cp_service, pf_loop, bl_loop,
                                         self.bs_loop)
            tasks.extend([pf_loop, bl_loop, cp_loop])
            self.cpMap[cp_key] = OracleLoopTasks(cp_service, tasks,
                                                 cp_loop, pf_loop, bl_loop,
                                                 cp_loop._oracle_turn)  # OracleTurn(self.conf, cp_service.coin_pair))
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

    async def get_validation_data(self, params: PublishPriceParams) -> RequestValidation or None:
        tasks: OracleLoopTasks = self.cpMap.get(str(params.coin_pair))
        if not tasks or not tasks.price_feeder_loop \
                or not tasks.blockchain_info_loop or not tasks.oracle_turn:
            return

        exchange_price = await tasks.price_feeder_loop.get_last_price(params.price_ts_utc, False)
        blockchain_info: OracleBlockchainInfo = tasks.blockchain_info_loop.get()
        oracle_price_reject_delta_pct = self.conf.ORACLE_PRICE_REJECT_DELTA_PCT
        return RequestValidation(oracle_price_reject_delta_pct, params, tasks.oracle_turn, exchange_price,
                                 blockchain_info)

    async def get_full_blockchain_info(self) -> typing.Dict[str, OracleBlockchainInfo]:
        return {cp_key: task.blockchain_info_loop.get()
                for (cp_key, task) in self.cpMap.items()}
