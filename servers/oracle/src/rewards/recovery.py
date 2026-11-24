"""Trustless full on-chain recovery from Distributor + ERC20 events and historical eth_getCode.

Matches `rewards-program/scripts/snapshot/recover.ts` and `recovery.ts`.
Any discrepancy in `distributedToday` or `EpochPublished.root` aborts with an error.
"""

from typing import Dict, List, Optional, Set, Tuple

from oracle.src.rewards.eligibility import compute_allocations, read_eligibility
from oracle.src.rewards.epoch_json import build_epoch_json
from oracle.src.rewards.indexer import (
    PERIOD_DURATION,
    apply_migration_batches,
    calculate_epoch_budget,
    index_transfer_events,
    period_for_epoch,
    read_migration_batches,
    sort_logs,
)
from oracle.src.rewards.merkle import StandardMerkleTree, ZERO_ROOT
from oracle.src.rewards.rpc_client import abi_decode, event_topic
from oracle.src.rewards.types import EpochJson, PublishedEpochEvent

EPOCH_PUBLISHED_TOPIC = event_topic(
    "EpochPublished(uint256,bytes32,string,uint256,uint256)"
)
MIN_ELIGIBLE_UPDATED_TOPIC = event_topic(
    "MinEligibleBalanceUpdated(uint256,uint256)"
)
DISTRIBUTION_PERIOD_STARTED_TOPIC = event_topic(
    "DistributionPeriodStarted(uint256,uint256,uint256,uint256)"
)


def _int_field(val) -> int:
    return int(val, 16) if isinstance(val, str) else int(val)


def recover_epoch(
    epoch: int,
    balances: Dict[str, int],
    previous_cumulative: Dict[str, int],
    contracts: Set[str],
    registered: Set[str],
    min_balance: int,
    epoch_budget: int,
    distributed_today: int,
    expected_root: str,
) -> Dict[str, int]:
    """Recompute one epoch's cumulative map and verify exact distributedToday & Merkle root."""
    if distributed_today < 0:
        raise ValueError("Negative distribution")
    if epoch_budget < 0:
        raise ValueError("Negative epoch budget")

    cumulative, _daily, _supply, computed_distributed = compute_allocations(
        balances=balances,
        previous_cumulative=previous_cumulative,
        contracts=contracts,
        registered=registered,
        min_eligible_balance=min_balance,
        epoch_budget=epoch_budget,
    )
    if computed_distributed != distributed_today:
        raise ValueError(
            f"Epoch {epoch}: distribution calculated from epochBudget {epoch_budget} "
            f"is {computed_distributed}, expected distributedToday {distributed_today}"
        )

    entries = sorted(cumulative.items(), key=lambda item: item[0])
    root = StandardMerkleTree(entries).root if entries else ZERO_ROOT
    if root.lower() != expected_root.lower():
        raise ValueError(
            f"Epoch {epoch}: Merkle root mismatch ({root} != {expected_root}); "
            "historical inputs or rules are incomplete"
        )
    return cumulative


async def recover_from_chain(
    client,
    distributor: str,
    token_address: str,
    chunk_size: int,
    code_concurrency: int = 20,
    tip: Optional[int] = None,
    token_start_block: int = 0,
) -> EpochJson:
    """Reconstruct and verify the latest published EpochJson solely from on-chain state."""
    if chunk_size <= 0:
        raise ValueError("Invalid chunk size")

    ref_tip = tip if tip is not None else await client.get_block_number()
    state = await client.read_distributor_state(distributor, block_number=ref_tip)

    last_epoch = state["currentEpoch"]
    if last_epoch == 0:
        raise ValueError("No published epochs to recover")

    current_root = state["currentRoot"]
    current_cid = state["currentIpfsCid"]
    current_snapshot_block = state["currentSnapshotBlock"]
    historical_total = state["totalDistributedHistorical"]
    distribution_start_time = state["distributionStartTime"]
    opened_period_count = state["openedPeriodCount"]
    init_block = state["initializationBlock"]

    publications: List[PublishedEpochEvent] = []
    budgets: List[Tuple[int, int, int, int]] = []  # (period, budget, blockNumber, logIndex)
    minimums: List[Tuple[int, int, int]] = []  # (effectiveEpoch, value, blockNumber)

    # Scan Distributor events from initializationBlock..ref_tip
    start = init_block
    while start <= ref_tip:
        end = min(start + chunk_size - 1, ref_tip)

        budget_logs = sort_logs(
            await client.get_logs(
                address=distributor,
                topics=[DISTRIBUTION_PERIOD_STARTED_TOPIC],
                from_block=start,
                to_block=end,
            )
        )
        for log in budget_logs:
            topics = log.get("topics") or []
            if len(topics) < 2 or log.get("data") is None:
                raise ValueError("Incomplete DistributionPeriodStarted event")
            period = int(topics[1], 16)
            raw = bytes.fromhex(log["data"][2:] if log["data"].startswith("0x") else log["data"])
            start_time, end_time, budget = abi_decode(["uint256", "uint256", "uint256"], raw)
            start_time, end_time, budget = int(start_time), int(end_time), int(budget)
            if (
                start_time != distribution_start_time + period * PERIOD_DURATION
                or end_time != start_time + PERIOD_DURATION
            ):
                raise ValueError("Distribution period dates disagree with schedule")
            if period != len(budgets):
                raise ValueError("Missing, duplicate or out-of-order distribution period")
            budgets.append((period, budget, _int_field(log["blockNumber"]), _int_field(log["logIndex"])))

        min_logs = sort_logs(
            await client.get_logs(
                address=distributor,
                topics=[MIN_ELIGIBLE_UPDATED_TOPIC],
                from_block=start,
                to_block=end,
            )
        )
        for log in min_logs:
            topics = log.get("topics") or []
            if len(topics) < 2 or log.get("data") is None:
                raise ValueError("Incomplete MinEligibleBalanceUpdated event")
            eff_epoch = int(topics[1], 16)
            raw = bytes.fromhex(log["data"][2:] if log["data"].startswith("0x") else log["data"])
            (min_val,) = abi_decode(["uint256"], raw)
            minimums.append((eff_epoch, int(min_val), _int_field(log["blockNumber"])))

        pub_logs = sort_logs(
            await client.get_logs(
                address=distributor,
                topics=[EPOCH_PUBLISHED_TOPIC],
                from_block=start,
                to_block=end,
            )
        )
        for log in pub_logs:
            topics = log.get("topics") or []
            if len(topics) < 2 or log.get("data") is None:
                raise ValueError("Incomplete EpochPublished log")
            ep = int(topics[1], 16)
            raw = bytes.fromhex(log["data"][2:] if log["data"].startswith("0x") else log["data"])
            root_bytes, cid, snap_blk, dist_today = abi_decode(
                ["bytes32", "string", "uint256", "uint256"], raw
            )
            block_num = _int_field(log["blockNumber"])
            log_idx = _int_field(log["logIndex"])
            if ep != len(publications) + 1:
                raise ValueError(
                    f"Missing, duplicate or out-of-order EpochPublished event at epoch {ep}"
                )
            if int(snap_blk) >= block_num or int(dist_today) < 0:
                raise ValueError(f"Epoch {ep}: invalid publication metadata")
            publications.append(
                PublishedEpochEvent(
                    epoch=ep,
                    root="0x" + bytes(root_bytes).hex(),
                    cid=str(cid),
                    snapshot_block=int(snap_blk),
                    distributed_today=int(dist_today),
                    block_number=block_num,
                    log_index=log_idx,
                )
            )
        start = end + 1

    expected_periods = (budgets[-1][0] + 1) if budgets else 0
    if expected_periods != opened_period_count:
        raise ValueError("Incomplete distribution period history")
    if len(publications) != last_epoch:
        raise ValueError(
            f"Missing EpochPublished events: found {len(publications)}, expected {last_epoch}"
        )

    last_pub = publications[-1]
    if (
        last_pub.root.lower() != current_root.lower()
        or last_pub.cid != current_cid
        or last_pub.snapshot_block != current_snapshot_block
    ):
        raise ValueError("Latest EpochPublished event disagrees with Distributor")

    migration_batches, migration_total = await read_migration_batches(
        client, distributor, ref_tip, chunk_size
    )
    if any(b.effective_epoch > last_epoch + 1 for b in migration_batches):
        raise ValueError("Invalid migration effective epoch")

    balances: Dict[str, int] = {}
    cumulative: Dict[str, int] = {}
    included_migration = 0
    recovered_total = 0
    remaining_budgets: Dict[int, int] = {period: budget for period, budget, _, _ in budgets}
    registered_contracts: List[str] = []
    from_block = token_start_block
    reg_from_block = init_block
    final_epoch_json: Optional[EpochJson] = None

    for pub in publications:
        for batch in migration_batches:
            if batch.effective_epoch == pub.epoch:
                if batch.block_number > pub.block_number or (
                    batch.block_number == pub.block_number and batch.log_index >= pub.log_index
                ):
                    raise ValueError(
                        "Migration batch must precede its effective epoch publication"
                    )
        imported = apply_migration_batches(cumulative, migration_batches, pub.epoch)
        included_migration += imported
        recovered_total += imported

        if pub.snapshot_block < from_block or pub.distributed_today < 0:
            raise ValueError(f"Epoch {pub.epoch}: invalid publication history")

        await index_transfer_events(
            client, token_address, balances, from_block, pub.snapshot_block, chunk_size
        )

        checkpoints = [
            (eff_ep, val)
            for eff_ep, val, blk in minimums
            if blk <= pub.block_number and eff_ep <= pub.epoch
        ]
        if not any(eff_ep == 1 for eff_ep, _ in checkpoints):
            raise ValueError("Missing initial minimum event")
        latest_eff = checkpoints[0][0]
        min_balance = checkpoints[0][1]
        for eff_ep, val in checkpoints[1:]:
            if eff_ep >= latest_eff:
                latest_eff = eff_ep
                min_balance = val

        budget_checkpoints = [
            (period, budget)
            for period, budget, blk, lidx in budgets
            if blk < pub.block_number or (blk == pub.block_number and lidx < pub.log_index)
        ]
        period = period_for_epoch(pub.epoch)
        if not budget_checkpoints or budget_checkpoints[-1][0] != period:
            raise ValueError(f"Missing distribution period {period} before epoch {pub.epoch}")
        period_budget = budget_checkpoints[-1][1]
        remaining = remaining_budgets[period]
        epoch_budget = calculate_epoch_budget(period_budget, remaining, pub.epoch)

        registered, contracts, _snap_hash = await read_eligibility(
            client=client,
            distributor=distributor,
            balances=balances,
            snapshot_block=pub.snapshot_block,
            chunk_size=chunk_size,
            epoch=pub.epoch,
            code_concurrency=code_concurrency,
            previous_from_block=reg_from_block,
            previous_registered=registered_contracts,
        )
        registered_contracts = sorted(registered)

        cumulative = recover_epoch(
            epoch=pub.epoch,
            balances=balances,
            previous_cumulative=cumulative,
            contracts=contracts,
            registered=registered,
            min_balance=min_balance,
            epoch_budget=epoch_budget,
            distributed_today=pub.distributed_today,
            expected_root=pub.root,
        )

        if pub.epoch == last_epoch:
            final_epoch_json = build_epoch_json(
                epoch=pub.epoch,
                snapshot_block=pub.snapshot_block,
                holders=list(cumulative.items()),
                balances=list(balances.items()),
                registered_contracts=registered_contracts,
                expected_total=recovered_total + pub.distributed_today,
            )

        remaining_budgets[period] = remaining - pub.distributed_today
        recovered_total += pub.distributed_today
        from_block = pub.snapshot_block + 1
        reg_from_block = pub.snapshot_block + 1

    if recovered_total + migration_total - included_migration != historical_total:
        raise ValueError("Historical distribution total disagrees with Distributor")
    if final_epoch_json is None:
        raise ValueError("Missing latest epoch")

    return final_epoch_json
