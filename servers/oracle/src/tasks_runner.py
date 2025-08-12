import time

from common.helpers import MyCfgdLogger
from common.services.conditional_publish import ConditionalPublishServiceBase
from common.services.oracle_dao import OracleBlockchainInfo
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfoLoop
from oracle.src.oracle_coin_pair_service import OracleCoinPairService
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.oracle_publish_message import PublishPriceParams, PublishTaskParams
from oracle.src.oracle_turn import TasksOracleTurn
from oracle.src.price_feeder.price_feeder import PriceFeederLoop
from oracle.src.request_validation import PriceRequestValidation, TaskRequestValidation

ETHER = 10**18

class TasksRunner(MyCfgdLogger):
    def __init__(
        self,
        conf: OracleConfiguration,
        price_feeder_loop: PriceFeederLoop,
        cps: OracleCoinPairService,
        vi_loop: OracleBlockchainInfoLoop,
    ):
        self._conf = conf
        self.price_feeder_loop = price_feeder_loop
        self.cps = cps
        self.vi_loop = vi_loop

        self.signal_service = ConditionalPublishServiceBase.SyncCreate(
            self.cps._blockchain, str(self.cps.coin_pair), self.vi_loop
        )

        self.oracle_turn = TasksOracleTurn(
            self._conf, self.cps.coin_pair
        )

    async def is_oracle_turn(self, blockchain_info, oracle_addr):
        result = self.oracle_turn.is_oracle_turn(
            blockchain_info,
            oracle_addr,
        )
        return True, *result

    def get_log(self, blockchain_info):
        try:
            cur = blockchain_info.blockchain_price / ETHER
        except Exception as err:
            cur = f"({err})"
        return f"X:{self._exchange_price.price / ETHER} C:{cur}"

    def prepare_publish_params(self, blockchain_info, oracle_addr):
        return PublishTaskParams(
            self._conf.MESSAGE_VERSION,
            self.cps.coin_pair,
            self._exchange_price,
            oracle_addr,
                blockchain_info.last_pub_block,
        )

    async def create_validator(self, params: PublishTaskParams):
        exchange_price = await self.price_feeder_loop.get_last_price(params.price_ts_utc, False)
        blockchain_info: OracleBlockchainInfo = self.vi_loop.get()
        return TaskRequestValidation(
            self._conf.ORACLE_PRICE_REJECT_DELTA_PCT,
            params,
            self.oracle_turn,
            exchange_price,
            blockchain_info,
        )