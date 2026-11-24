"""RewardsRunner: non-blocking background sync/compute runner for RewardsPublisher."""

import asyncio
import logging
from typing import Dict, Optional

from common import settings
from common.helpers import MyCfgdLogger
from common.services.conditional_publish import DisabledConditionalPublishService
from common.services.oracle_dao import OracleBlockchainInfo
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfoLoop
from oracle.src.oracle_coin_pair_service import OracleCoinPairService
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.oracle_publish_message import (
    PublishRewardsParams,
    REWARDS_MESSAGE_VERSION,
    compute_epoch_data_hash,
)
from oracle.src.oracle_turn import TasksOracleTurn
from oracle.src.request_validation import RewardsRequestValidation
from oracle.src.rewards.cid import compute_cid_v1
from oracle.src.rewards.engine import RewardsEngine
from oracle.src.rewards.ipfs_pinner import IpfsPinner
from oracle.src.rewards.rpc_client import ArchiveRpcClient
from oracle.src.rewards.snapshot_block import verify_snapshot_block_hash
from oracle.src.rewards.state_store import RewardsStateStore
from oracle.src.rewards.types import CandidateResult, EpochData

logger = logging.getLogger(__name__)


class RewardsRunner(MyCfgdLogger):
    """Runner for `RewardsPublisher` coin pairs (analogous to `TasksRunner`).

    - Runs `sync()` and `compute()` in background `asyncio.Task`s so `MainLoop`
      and price/task runners are never blocked.
    - While syncing, refuses to publish and rejects `/sign-rewards/` requests.
    - Re-verifies `snapshotBlockHash` before publishing/validating to guard against reorgs.
    - Optionally pins published epoch JSONs to a local Kubo daemon in background
      without ever blocking consensus or on-chain publication.
    """

    def __init__(
        self,
        conf: OracleConfiguration,
        cps: OracleCoinPairService,
        vi_loop: OracleBlockchainInfoLoop,
        engine: Optional[RewardsEngine] = None,
        pinner: Optional[IpfsPinner] = None,
    ):
        super().__init__(None, str(cps.coin_pair))
        self._conf = conf
        self.cps = cps
        self.vi_loop = vi_loop

        self.signal_service = DisabledConditionalPublishService.SyncCreate(
            self.cps._blockchain, str(self.cps.coin_pair), self.vi_loop
        )
        self.oracle_turn = TasksOracleTurn(self._conf, self.cps.coin_pair)

        self._engine: Optional[RewardsEngine] = engine
        self._pinner: IpfsPinner = (
            pinner if pinner is not None else IpfsPinner(settings.REWARDS_IPFS_API_URL)
        )
        self._distributor_addr: Optional[str] = None
        self._chain_id: Optional[int] = None

        self._is_syncing: bool = False
        self._sync_task: Optional[asyncio.Task] = None
        self._compute_task: Optional[asyncio.Task] = None
        self._pin_task: Optional[asyncio.Task] = None

        self._candidate: Optional[CandidateResult] = None
        self._last_block_when_available: Optional[int] = None
        self._pending_pins: Dict[int, CandidateResult] = {}

    @property
    def is_syncing(self) -> bool:
        return self._is_syncing or (
            self._sync_task is not None and not self._sync_task.done()
        )

    def start_bg_task(self) -> None:
        """Lifecycle hook matching BgTaskExecutor; tasks start on demand."""
        return None

    def stop_bg_task(self) -> None:
        """Cancel any active background sync, compute, or pin tasks."""
        for attr in ("_sync_task", "_compute_task", "_pin_task"):
            task = getattr(self, attr)
            if task is not None and not task.done():
                task.cancel()
            setattr(self, attr, None)
        self._is_syncing = False
        if self._engine is not None and hasattr(self._engine.rpc, "close"):
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._engine.rpc.close())
            except RuntimeError:
                pass

    def _get_chain_id(self) -> int:
        if self._chain_id is not None:
            return self._chain_id
        bc = self.cps._blockchain
        if getattr(bc, "chain_id", None) is not None:
            self._chain_id = int(bc.chain_id)
        elif settings.CHAIN_ID is not None:
            self._chain_id = int(settings.CHAIN_ID)
        else:
            self._chain_id = int(bc.w3.eth.chainId)
        return self._chain_id

    async def _ensure_engine(self) -> RewardsEngine:
        if self._engine is not None:
            return self._engine
        if self._distributor_addr is None:
            self._distributor_addr = await self.cps.get_distributor_addr()
        rpc_url = settings.REWARDS_ARCHIVE_RPC_URL
        state_dir = settings.REWARDS_STATE_DIR
        if not rpc_url:
            raise RuntimeError("REWARDS_ARCHIVE_RPC_URL must be configured for RewardsRunner")
        if not state_dir:
            raise RuntimeError("REWARDS_STATE_DIR must be configured for RewardsRunner")
        rpc = ArchiveRpcClient(rpc_url)
        store = RewardsStateStore(state_dir)
        self._engine = RewardsEngine(
            rpc_client=rpc,
            distributor_address=self._distributor_addr,
            state_store=store,
            snapshot_confirmations=settings.REWARDS_SNAPSHOT_CONFIRMATIONS,
            log_chunk_size=settings.REWARDS_LOG_CHUNK_SIZE,
            code_concurrency=settings.REWARDS_CODE_CONCURRENCY,
            ipfs_gateways=settings.REWARDS_IPFS_GATEWAYS,
            token_start_block=settings.REWARDS_TOKEN_START_BLOCK,
        )
        return self._engine

    def _start_sync_bg(self, engine: RewardsEngine) -> None:
        if self._sync_task is not None and not self._sync_task.done():
            return
        if self._compute_task is not None and not self._compute_task.done():
            self._compute_task.cancel()
        self._compute_task = None
        self._is_syncing = True
        self._candidate = None
        self._last_block_when_available = None

        async def _run_sync():
            try:
                res = await engine.sync()
                self.info(
                    f"Rewards sync complete: source={res.source} epoch={res.epoch} "
                    f"snapshotBlock={res.snapshot_block}"
                )
                if (
                    self._pinner.enabled
                    and res.epoch > 0
                    and res.json_path
                    and res.cid
                ):
                    loaded = engine.store.load_published(res.epoch)
                    if loaded is not None:
                        _ep_json, raw_bytes, path = loaded
                        if compute_cid_v1(raw_bytes) == res.cid:
                            self._pending_pins[res.epoch] = CandidateResult(
                                epoch_data=EpochData(
                                    epoch=res.epoch,
                                    merkle_root=res.merkle_root,
                                    cid=res.cid,
                                    snapshot_block=res.snapshot_block,
                                    distributed_today=0,
                                ),
                                snapshot_block_hash="",
                                json_path=path,
                                raw_bytes=raw_bytes,
                            )
                            self._schedule_pin_bg()
            except asyncio.CancelledError:
                raise
            except Exception as err:
                self.error(f"Rewards sync failed: {err!r}")
            finally:
                self._is_syncing = False

        self._sync_task = asyncio.create_task(_run_sync())

    def _start_compute_bg(self, engine: RewardsEngine) -> None:
        if self._compute_task is not None and not self._compute_task.done():
            return

        async def _run_compute():
            try:
                candidate = await engine.compute()
                if candidate is not None and not self.is_syncing:
                    self._candidate = candidate
                    if self._last_block_when_available is None:
                        bc = self.vi_loop.get()
                        if bc is not None:
                            self._last_block_when_available = bc.block_num
                    self.info(
                        f"Rewards candidate ready: epoch={candidate.epoch_data.epoch} "
                        f"snapshotBlock={candidate.epoch_data.snapshot_block} "
                        f"cid={candidate.epoch_data.cid} "
                        f"distributedToday={candidate.epoch_data.distributed_today}"
                    )
            except asyncio.CancelledError:
                raise
            except Exception as err:
                self.error(f"Rewards compute failed: {err!r}")

        self._compute_task = asyncio.create_task(_run_compute())

    async def _is_candidate_valid_for_state(
        self, candidate: CandidateResult, state: dict, engine: RewardsEngine
    ) -> bool:
        """Verify candidate matches current target epoch, on-chain policy, and snapshotBlockHash."""
        target_epoch = state["currentEpoch"] + 1
        if candidate.epoch_data.epoch != target_epoch:
            return False
        if (
            candidate.min_eligible_balance is not None
            and candidate.min_eligible_balance != state["minEligibleBalance"]
        ):
            self.warning(
                f"minEligibleBalance changed ({candidate.min_eligible_balance} -> "
                f"{state['minEligibleBalance']}); invalidating candidate"
            )
            return False
        if (
            candidate.total_distributed_historical is not None
            and candidate.total_distributed_historical != state["totalDistributedHistorical"]
        ):
            self.warning(
                f"totalDistributedHistorical changed ({candidate.total_distributed_historical} -> "
                f"{state['totalDistributedHistorical']}); invalidating candidate"
            )
            return False
        try:
            still_valid = await verify_snapshot_block_hash(
                engine.rpc,
                candidate.epoch_data.snapshot_block,
                candidate.snapshot_block_hash,
            )
        except Exception as err:
            self.warning(f"Failed verifying snapshot block hash: {err!r}")
            return False
        if not still_valid:
            self.warning(
                f"Reorg detected at snapshotBlock {candidate.epoch_data.snapshot_block}; "
                "invalidating candidate"
            )
            return False
        return True

    def _schedule_pin_bg(self) -> None:
        if not self._pinner.enabled or not self._pending_pins:
            return
        if self._pin_task is not None and not self._pin_task.done():
            return

        async def _run_pins():
            for epoch in list(self._pending_pins.keys()):
                cand = self._pending_pins.get(epoch)
                if cand is None:
                    continue
                try:
                    await self._pinner.pin_bytes(
                        cand.raw_bytes,
                        cand.epoch_data.cid,
                        f"epoch_{epoch}.json",
                    )
                    self.info(f"Pinned epoch {epoch} to IPFS: {cand.epoch_data.cid}")
                    self._pending_pins.pop(epoch, None)
                except asyncio.CancelledError:
                    raise
                except Exception as err:
                    self.warning(f"IPFS pin for epoch {epoch} failed (will retry): {err!r}")

        self._pin_task = asyncio.create_task(_run_pins())

    async def is_oracle_turn(self, blockchain_info: OracleBlockchainInfo, oracle_addr: str):
        try:
            engine = await self._ensure_engine()
            state = await engine.rpc.read_distributor_state(engine.distributor)
        except Exception as err:
            self.error(f"Rewards state check failed: {err!r}")
            return False, None, None

        current_epoch = state["currentEpoch"]

        # Promote published candidate to published/ & queue IPFS pin once epoch advances
        if self._candidate is not None and self._candidate.epoch_data.epoch <= current_epoch:
            published_cand = self._candidate
            if (
                published_cand.epoch_data.epoch == current_epoch
                and published_cand.epoch_data.merkle_root.lower() == state["currentRoot"].lower()
                and published_cand.epoch_data.snapshot_block == state["currentSnapshotBlock"]
                and (
                    not state["currentIpfsCid"]
                    or published_cand.epoch_data.cid == state["currentIpfsCid"]
                )
            ):
                try:
                    engine.store.save_published(current_epoch, published_cand.raw_bytes)
                    engine._last_synced_epoch = current_epoch
                    if self._pinner.enabled:
                        self._pending_pins[current_epoch] = published_cand
                except Exception as err:
                    self.warning(f"Failed promoting published epoch {current_epoch}: {err!r}")
            self._candidate = None
            self._last_block_when_available = None

        self._schedule_pin_bg()

        # Sync if needed (non-blocking)
        if not engine.is_synced_for(current_epoch):
            self._start_sync_bg(engine)
            return False, None, None

        if self.is_syncing:
            return False, None, None

        # Only attempt publish when Distributor allows it and operator is RewardsPublisher
        if (
            not state["canPublishEpoch"]
            or state["paused"]
            or state["operator"].lower() != str(self.cps.addr).lower()
        ):
            self._candidate = None
            self._last_block_when_available = None
            return False, None, None

        # Re-verify cached candidate against reorgs and on-chain policy/migration changes
        if self._candidate is not None:
            if not await self._is_candidate_valid_for_state(self._candidate, state, engine):
                self._candidate = None
                self._last_block_when_available = None

        if self._candidate is None:
            self._start_compute_bg(engine)
            return False, None, None

        if not self._last_block_when_available:
            self._last_block_when_available = blockchain_info.block_num

        result = self.oracle_turn.is_oracle_turn(
            blockchain_info,
            oracle_addr,
            extra_args={
                "are_tasks_available": True,
                "last_block_when_available": self._last_block_when_available,
            },
        )
        return True, *result

    def get_pre_publish_log(self, blockchain_info):
        if self._candidate is None:
            return ""
        ed = self._candidate.epoch_data
        return f"epoch={ed.epoch} snapshotBlock={ed.snapshot_block} cid={ed.cid}"

    def prepare_publish_params(
        self, blockchain_info: OracleBlockchainInfo, oracle_addr: str
    ) -> PublishRewardsParams:
        if self._candidate is None:
            raise RuntimeError("No rewards candidate available to publish")
        ed = self._candidate.epoch_data
        epoch_data_hash = compute_epoch_data_hash(
            chain_id=self._get_chain_id(),
            publisher_address=str(self.cps.addr),
            epoch=ed.epoch,
            merkle_root=ed.merkle_root,
            cid=ed.cid,
            snapshot_block=ed.snapshot_block,
            distributed_today=ed.distributed_today,
        )
        return PublishRewardsParams(
            version=REWARDS_MESSAGE_VERSION,
            coin_pair=self.cps.coin_pair,
            epoch=ed.epoch,
            merkle_root=ed.merkle_root,
            cid=ed.cid,
            snapshot_block=ed.snapshot_block,
            distributed_today=ed.distributed_today,
            epoch_data_hash=epoch_data_hash,
            oracle_addr=oracle_addr,
            last_pub_block=blockchain_info.last_pub_block,
        )

    async def create_validator(self, params: PublishRewardsParams) -> RewardsRequestValidation:
        if params.epoch_data_hash is None:
            computed_hash = compute_epoch_data_hash(
                chain_id=self._get_chain_id(),
                publisher_address=str(self.cps.addr),
                epoch=params.epoch,
                merkle_root=params.merkle_root,
                cid=params.cid,
                snapshot_block=params.snapshot_block,
                distributed_today=params.distributed_today,
            )
            params = PublishRewardsParams(
                version=params.version,
                coin_pair=params.coin_pair,
                epoch=params.epoch,
                merkle_root=params.merkle_root,
                cid=params.cid,
                snapshot_block=params.snapshot_block,
                distributed_today=params.distributed_today,
                epoch_data_hash=computed_hash,
                oracle_addr=params.oracle_addr,
                last_pub_block=params.last_pub_block,
            )

        blockchain_info: OracleBlockchainInfo = self.vi_loop.get()
        if self.is_syncing:
            return RewardsRequestValidation(
                params=params,
                oracle_turn=self.oracle_turn,
                is_syncing=True,
                is_ready=False,
                last_block_when_available=self._last_block_when_available,
                local_candidate=None,
                blockchain_info=blockchain_info,
            )

        local_candidate = self._candidate
        is_ready = False
        expected_hash = None
        try:
            engine = await self._ensure_engine()
            state = await engine.rpc.read_distributor_state(engine.distributor)
            if not engine.is_synced_for(state["currentEpoch"]):
                self._start_sync_bg(engine)
                return RewardsRequestValidation(
                    params=params,
                    oracle_turn=self.oracle_turn,
                    is_syncing=True,
                    is_ready=False,
                    last_block_when_available=self._last_block_when_available,
                    local_candidate=None,
                    blockchain_info=blockchain_info,
                )

            if (
                state["canPublishEpoch"]
                and not state["paused"]
                and state["operator"].lower() == str(self.cps.addr).lower()
            ):
                if local_candidate is not None and await self._is_candidate_valid_for_state(
                    local_candidate, state, engine
                ):
                    is_ready = True
                    if self._last_block_when_available is None and blockchain_info is not None:
                        self._last_block_when_available = blockchain_info.block_num
                else:
                    if local_candidate is not None:
                        self._candidate = None
                        self._last_block_when_available = None
                    local_candidate = None
                    self._start_compute_bg(engine)

            if is_ready and local_candidate is not None:
                ed = local_candidate.epoch_data
                expected_hash = compute_epoch_data_hash(
                    chain_id=self._get_chain_id(),
                    publisher_address=str(self.cps.addr),
                    epoch=ed.epoch,
                    merkle_root=ed.merkle_root,
                    cid=ed.cid,
                    snapshot_block=ed.snapshot_block,
                    distributed_today=ed.distributed_today,
                )
        except Exception as err:
            self.warning(f"Rewards validator preparation error: {err!r}")
            is_ready = False
            local_candidate = None

        return RewardsRequestValidation(
            params=params,
            oracle_turn=self.oracle_turn,
            is_syncing=False,
            is_ready=is_ready,
            last_block_when_available=self._last_block_when_available,
            local_candidate=local_candidate,
            blockchain_info=blockchain_info,
            expected_epoch_data_hash=expected_hash,
        )
