import asyncio
import logging
import time

from common import settings
from common.helpers import MyCfgdLogger
from common.services.blockchain import is_error
from common.services.conditional_publish import DisabledConditionalPublishService
from oracle.src.oracle_publish_message import PublishLiquidationParams
from oracle.src.oracle_turn import TasksOracleTurn
from oracle.src.lending import LendingLiquidationProvider
from oracle.src.request_validation import LiquidationRequestValidation


logger = logging.getLogger(__name__)


class LiquidationRunner(MyCfgdLogger):
    def __init__(self, conf, cps, vi_loop, lending_repository=None, lending_indexer=None):
        super().__init__(None, str(cps.coin_pair))
        self._conf = conf
        self.cps = cps
        self.vi_loop = vi_loop
        self._discovery = None
        self._retry_at = 0
        self._liquidations = []
        self.liquidation_provider = LendingLiquidationProvider(
            cps,
            lending_repository,
            lending_indexer,
            multicall_addr=self._conf.MULTICALL_ADDR,
        )
        self.signal_service = DisabledConditionalPublishService.SyncCreate(
            self.cps._blockchain, str(self.cps.coin_pair), self.vi_loop
        )
        self.oracle_turn = TasksOracleTurn(self._conf, self.cps.coin_pair)

    async def _build_liquidations(self):
        limit = await self.cps.get_max_liquidations_per_batch()
        if is_error(limit):
            raise RuntimeError(
                "Could not read LiquidationEngine maxLiquidationsPerBatch: %s"
                % limit.error
            )
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError(
                "Invalid LiquidationEngine maxLiquidationsPerBatch: %r" % limit
            )
        return await self.liquidation_provider.build_liquidations(limit)

    async def _discover_liquidations(self):
        pending = self._discovery
        if pending is not None:
            if not pending.done():
                return []
            try:
                liquidations = pending.result()
            except Exception as err:
                logger.warning("Liquidation discovery unavailable: %s", err)
                liquidations = []
            self._discovery = None
            return liquidations
        if time.monotonic() < self._retry_at:
            return []

        pending = asyncio.create_task(self._build_liquidations())
        self._discovery = pending
        pending.add_done_callback(lambda task: None if task.cancelled() else task.exception())
        try:
            liquidations = await asyncio.wait_for(
                asyncio.shield(pending), settings.LENDING_DISCOVERY_TIMEOUT
            )
            self._discovery = None
            return liquidations
        except asyncio.CancelledError:
            pending.cancel()
            raise
        except Exception as err:
            self._retry_at = time.monotonic() + settings.LENDING_INDEX_INTERVAL
            logger.warning("Liquidation discovery unavailable: %s", err)
            return []

    async def is_oracle_turn(self, blockchain_info, oracle_addr):
        self._liquidations = await self._discover_liquidations()
        if not self._liquidations:
            return False, None, None
        result = self.oracle_turn.is_oracle_turn(
            blockchain_info,
            oracle_addr,
            extra_args={
                "are_tasks_available": True,
                "last_block_when_available": blockchain_info.last_pub_block,
            },
        )
        return True, *result

    def get_pre_publish_log(self, blockchain_info):
        return "liquidations=%d" % sum(len(item.users) for item in self._liquidations)

    def prepare_publish_params(self, blockchain_info, oracle_addr):
        return PublishLiquidationParams(
            self._conf.LIQUIDATION_MESSAGE_VERSION,
            self.cps.coin_pair,
            self._liquidations,
            oracle_addr,
            blockchain_info.last_pub_block,
        )

    async def create_validator(self, params):
        blockchain_info = self.vi_loop.get()
        return LiquidationRequestValidation(
            params,
            self.oracle_turn,
            blockchain_info,
            self._conf.LIQUIDATION_MESSAGE_VERSION,
        )
