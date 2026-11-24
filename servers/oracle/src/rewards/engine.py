"""RewardsEngine orchestrator for `sync()` and incremental `compute()`."""

import logging
from typing import Dict, List, Optional, Sequence

from oracle.src.rewards.cid import compute_cid_v1
from oracle.src.rewards.eligibility import compute_allocations, read_eligibility
from oracle.src.rewards.epoch_json import (
    build_epoch_json,
    parse_epoch_json,
    serialize_epoch_json,
    verify_epoch_json_merkle,
)
from oracle.src.rewards.indexer import (
    apply_migration_batches,
    index_transfer_events,
    read_migration_batches,
)
from oracle.src.rewards.ipfs_pinner import fetch_from_ipfs_gateways
from oracle.src.rewards.recovery import recover_from_chain
from oracle.src.rewards.snapshot_block import (
    SnapshotNotReadyError,
    find_snapshot_block,
    verify_snapshot_block_hash,
)
from oracle.src.rewards.state_store import RewardsStateStore
from oracle.src.rewards.types import CandidateResult, EpochData, EpochJson, SyncResult

logger = logging.getLogger(__name__)


class RewardsEngine:
    """Pure-Python rewards snapshot, sync, and recovery engine."""

    def __init__(
        self,
        rpc_client,
        distributor_address: str,
        state_store: RewardsStateStore,
        snapshot_confirmations: int = 12,
        log_chunk_size: int = 1000,
        code_concurrency: int = 20,
        ipfs_gateways: Sequence[str] = (),
        token_start_block: int = 0,
    ):
        self.rpc = rpc_client
        self.distributor = distributor_address.lower()
        self.store = state_store
        self.snapshot_confirmations = int(snapshot_confirmations)
        self.log_chunk_size = int(log_chunk_size)
        self.code_concurrency = int(code_concurrency)
        self.ipfs_gateways = [gw.strip() for gw in ipfs_gateways if gw.strip()]
        self.token_start_block = int(token_start_block)
        self._last_synced_epoch: Optional[int] = None

    def is_synced_for(self, current_epoch: int) -> bool:
        if current_epoch == 0:
            return True
        return self._last_synced_epoch == current_epoch

    async def sync(self) -> SyncResult:
        """Ensure local published state matches `Distributor.currentEpoch()`."""
        self.store.ensure_dirs()
        tip = await self.rpc.get_block_number()
        state = await self.rpc.read_distributor_state(self.distributor, block_number=tip)
        current_epoch = state["currentEpoch"]
        current_root = state["currentRoot"]
        current_cid = state["currentIpfsCid"]
        current_snapshot_block = state["currentSnapshotBlock"]
        token_address = state["holdingsToken"]

        if current_epoch == 0:
            self._last_synced_epoch = 0
            return SyncResult(
                source="genesis",
                epoch=0,
                snapshot_block=0,
                merkle_root=current_root,
                cid=current_cid,
                json_path=None,
            )

        # 1. Local published state check
        try:
            loaded = self.store.load_published(current_epoch)
        except Exception as err:
            logger.warning("Local published epoch_%s invalid: %r", current_epoch, err)
            loaded = None

        if loaded is not None:
            ep_json, raw_bytes, path = loaded
            cid_matches = (
                not current_cid
                or not current_cid.startswith("baf")
                or compute_cid_v1(raw_bytes) == current_cid
            )
            if (
                ep_json.epoch == current_epoch
                and ep_json.snapshot_block == current_snapshot_block
                and ep_json.merkle_root.lower() == current_root.lower()
                and cid_matches
            ):
                verify_epoch_json_merkle(ep_json, current_root)
                self._last_synced_epoch = current_epoch
                return SyncResult(
                    source="local",
                    epoch=current_epoch,
                    snapshot_block=current_snapshot_block,
                    merkle_root=current_root,
                    cid=current_cid,
                    json_path=path,
                )

        # 2. Fast path via trusted IPFS gateways (authenticated by CIDv1 + Merkle root)
        if self.ipfs_gateways and current_cid:
            raw_bytes = await fetch_from_ipfs_gateways(current_cid, self.ipfs_gateways)
            if raw_bytes is not None:
                try:
                    ep_json = parse_epoch_json(raw_bytes)
                    if (
                        ep_json.epoch == current_epoch
                        and ep_json.snapshot_block == current_snapshot_block
                        and ep_json.merkle_root.lower() == current_root.lower()
                    ):
                        verify_epoch_json_merkle(ep_json, current_root)
                        path = self.store.save_published(current_epoch, raw_bytes)
                        self._last_synced_epoch = current_epoch
                        return SyncResult(
                            source="ipfs",
                            epoch=current_epoch,
                            snapshot_block=current_snapshot_block,
                            merkle_root=current_root,
                            cid=current_cid,
                            json_path=path,
                        )
                except Exception as err:
                    logger.warning(
                        "IPFS epoch_%s failed validation, falling back to chain recovery: %r",
                        current_epoch,
                        err,
                    )

        # 3. Trustless on-chain recovery fallback
        logger.info("Running trustless on-chain recovery up to epoch %s...", current_epoch)
        recovered = await recover_from_chain(
            client=self.rpc,
            distributor=self.distributor,
            token_address=token_address,
            chunk_size=self.log_chunk_size,
            code_concurrency=self.code_concurrency,
            tip=tip,
            token_start_block=self.token_start_block,
        )
        raw_bytes = serialize_epoch_json(recovered)
        computed_cid = compute_cid_v1(raw_bytes)
        if current_cid and computed_cid != current_cid:
            logger.warning(
                "Recovered epoch_%s CID %s differs from on-chain CID %s (e.g. legacy JSON); "
                "Merkle root verified (%s)",
                current_epoch,
                computed_cid,
                current_cid,
                recovered.merkle_root,
            )
        path = self.store.save_published(current_epoch, raw_bytes)
        self._last_synced_epoch = current_epoch
        return SyncResult(
            source="chain_recovery",
            epoch=current_epoch,
            snapshot_block=recovered.snapshot_block,
            merkle_root=recovered.merkle_root,
            cid=current_cid or computed_cid,
            json_path=path,
        )

    async def compute(self) -> Optional[CandidateResult]:
        """Compute (or return cached) candidate for `currentEpoch + 1`.

        Returns None if `Distributor.canPublishEpoch()` is False or cutoff has
        fewer than `snapshot_confirmations` confirmations.
        """
        self.store.ensure_dirs()
        latest_block = await self.rpc.get_block_number()
        state = await self.rpc.read_distributor_state(self.distributor, block_number=latest_block)

        if not state["canPublishEpoch"] or state["paused"]:
            return None

        current_epoch = state["currentEpoch"]
        new_epoch = current_epoch + 1
        current_snapshot_block = state["currentSnapshotBlock"]
        next_epoch_time = state["nextEpochTime"]
        init_block = state["initializationBlock"]
        min_eligible_balance = state["minEligibleBalance"]
        historical_total = state["totalDistributedHistorical"]
        token_address = state["holdingsToken"]

        try:
            snapshot_block, snapshot_block_hash = await find_snapshot_block(
                client=self.rpc,
                cutoff_timestamp=next_epoch_time,
                latest_block=latest_block,
                initialization_block=init_block,
                confirmations=self.snapshot_confirmations,
            )
        except SnapshotNotReadyError:
            return None

        if snapshot_block < init_block:
            raise ValueError("Snapshot cannot precede initialization")
        if current_epoch > 0 and snapshot_block <= current_snapshot_block:
            raise ValueError("Snapshot block must advance beyond the previous epoch")

        epoch_budget = await self.rpc.read_next_epoch_budget(
            self.distributor, block_number=latest_block
        )

        # Load prior published state (must already be synced)
        balances: Dict[str, int] = {}
        prev_cumulatives: Dict[str, int] = {}
        if current_epoch == 0:
            from_block = self.token_start_block
            reg_from_block = init_block
            prev_registered: List[str] = []
        else:
            loaded = self.store.load_published(current_epoch)
            if loaded is None:
                raise RuntimeError(
                    f"Missing synced published state for epoch {current_epoch}; run sync() first"
                )
            prev_json, _prev_raw, _prev_path = loaded
            if (
                prev_json.epoch != current_epoch
                or prev_json.snapshot_block != current_snapshot_block
                or prev_json.merkle_root.lower() != state["currentRoot"].lower()
            ):
                raise RuntimeError(
                    f"Local published epoch_{current_epoch} disagrees with Distributor; re-sync required"
                )
            for b in prev_json.balances:
                balances[b.address.lower()] = b.balance
            for h in prev_json.holders:
                prev_cumulatives[h.address.lower()] = h.cumulative_amount
            from_block = current_snapshot_block + 1
            reg_from_block = current_snapshot_block + 1
            prev_registered = list(prev_json.registered_contracts)

        # Apply pending migration batches if historical total includes unapplied migrations
        prev_total = sum(prev_cumulatives.values())
        if historical_total != prev_total:
            migration_batches, _mig_total = await read_migration_batches(
                self.rpc, self.distributor, latest_block, self.log_chunk_size
            )
            if any(b.effective_epoch > new_epoch for b in migration_batches):
                raise ValueError("Migration event targets a future epoch beyond the pinned state")
            apply_migration_batches(prev_cumulatives, migration_batches, new_epoch)

        # Incremental Transfer indexing
        await index_transfer_events(
            self.rpc, token_address, balances, from_block, snapshot_block, self.log_chunk_size
        )

        # Eligibility at snapshot_block (repeats eth_getCode, verifies snapshotBlockHash)
        registered, contracts, verified_hash = await read_eligibility(
            client=self.rpc,
            distributor=self.distributor,
            balances=balances,
            snapshot_block=snapshot_block,
            chunk_size=self.log_chunk_size,
            epoch=new_epoch,
            code_concurrency=self.code_concurrency,
            previous_from_block=reg_from_block,
            previous_registered=prev_registered,
        )
        if verified_hash.lower() != snapshot_block_hash.lower():
            raise RuntimeError("Snapshot block hash changed during computation (reorg)")

        cumulative, _daily, _supply, distributed_today = compute_allocations(
            balances=balances,
            previous_cumulative=prev_cumulatives,
            contracts=contracts,
            registered=registered,
            min_eligible_balance=min_eligible_balance,
            epoch_budget=epoch_budget,
        )

        # Final reorg check before finalizing candidate
        if not await verify_snapshot_block_hash(self.rpc, snapshot_block, snapshot_block_hash):
            raise RuntimeError("Snapshot block hash changed before candidate finalization (reorg)")

        epoch_json: EpochJson = build_epoch_json(
            epoch=new_epoch,
            snapshot_block=snapshot_block,
            holders=list(cumulative.items()),
            balances=list(balances.items()),
            registered_contracts=registered,
            expected_total=historical_total + distributed_today,
        )
        raw_bytes = serialize_epoch_json(epoch_json)
        cid = compute_cid_v1(raw_bytes)
        json_path = self.store.save_candidate(
            new_epoch, snapshot_block, snapshot_block_hash, raw_bytes
        )

        return CandidateResult(
            epoch_data=EpochData(
                epoch=new_epoch,
                merkle_root=epoch_json.merkle_root,
                cid=cid,
                snapshot_block=snapshot_block,
                distributed_today=distributed_today,
            ),
            snapshot_block_hash=snapshot_block_hash,
            json_path=json_path,
            raw_bytes=raw_bytes,
            min_eligible_balance=min_eligible_balance,
            total_distributed_historical=historical_total,
        )
