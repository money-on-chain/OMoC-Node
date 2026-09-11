from common.helpers import MyCfgdLogger
from common.services.conditional_publish import DisabledConditionalPublishService
from common.services.oracle_dao import OracleBlockchainInfo
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfoLoop
from oracle.src.oracle_coin_pair_service import OracleCoinPairService
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.oracle_publish_message import PublishTaskParams
from oracle.src.oracle_turn import TasksOracleTurn
from oracle.src.request_validation import TaskRequestValidation


class TasksRunner(MyCfgdLogger):
    def __init__(
        self,
        conf: OracleConfiguration,
        cps: OracleCoinPairService,
        vi_loop: OracleBlockchainInfoLoop,
    ):
        super().__init__(None, str(cps.coin_pair))
        self._conf = conf
        self.cps = cps
        self.vi_loop = vi_loop
        self._last_block_when_available = 0
        self._tasks_flags = 0

        self.signal_service = DisabledConditionalPublishService.SyncCreate(
            self.cps._blockchain, str(self.cps.coin_pair), self.vi_loop
        )
        self.oracle_turn = TasksOracleTurn(self._conf, self.cps.coin_pair)

    async def is_oracle_turn(self, blockchain_info, oracle_addr):
        self._are_tasks_available = await self.cps.get_are_tasks_available()
        self._tasks_flags = await self.cps.get_tasks_available_as_flags()
        if not self._are_tasks_available:
            self._last_block_when_available = None
            return False, None, None
        if not self._last_block_when_available:
            self._last_block_when_available = blockchain_info.block_num

        self.info(await self.cps.log_data())
        result = self.oracle_turn.is_oracle_turn(
            blockchain_info,
            oracle_addr,
            extra_args={
                "are_tasks_available": self._are_tasks_available,
                "last_block_when_available": self._last_block_when_available,
            },
        )
        return True, *result

    def get_pre_publish_log(self, blockchain_info):
        return ""

    def prepare_publish_params(self, blockchain_info, oracle_addr):
        return PublishTaskParams(
            self._conf.TASK_MESSAGE_VERSION,
            self.cps.coin_pair,
            self._tasks_flags,
            oracle_addr,
            blockchain_info.last_pub_block,
        )

    async def create_validator(self, params: PublishTaskParams):
        are_tasks_available = await self.cps.get_are_tasks_available()
        tasks_flags = await self.cps.get_tasks_available_as_flags()
        blockchain_info: OracleBlockchainInfo = self.vi_loop.get()
        return TaskRequestValidation(
            params,
            self.oracle_turn,
            are_tasks_available,
            self._last_block_when_available,
            tasks_flags,
            blockchain_info,
        )
