"""Incremental event indexer for Transfer, RewardsMigrated, and period budget math.

Matches `rewards-program/scripts/snapshot/snapshot.ts`, `migration.ts`, and `period-budget.ts`.
"""

from typing import Dict, List, Sequence, Tuple

from oracle.src.rewards.rpc_client import abi_decode, event_topic
from oracle.src.rewards.types import MigrationBatch

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

PERIOD_DURATION = 730 * 60 * 60
EPOCHS_PER_PERIOD = 30
EPOCH_INTERVAL = PERIOD_DURATION // EPOCHS_PER_PERIOD

TRANSFER_TOPIC = event_topic("Transfer(address,address,uint256)")
REWARDS_MIGRATED_TOPIC = event_topic(
    "RewardsMigrated(uint256,(address,uint256)[],uint256,bool)"
)


def period_for_epoch(epoch: int) -> int:
    if epoch <= 0:
        raise ValueError("Invalid epoch for period budget")
    return (epoch - 1) // EPOCHS_PER_PERIOD


def calculate_epoch_budget(
    period_budget: int, remaining_budget: int, epoch: int
) -> int:
    period_for_epoch(epoch)
    if period_budget < 0 or remaining_budget < 0 or remaining_budget > period_budget:
        raise ValueError("Invalid remaining period budget")
    quota = period_budget // EPOCHS_PER_PERIOD
    if epoch % EPOCHS_PER_PERIOD == 0:
        quota += period_budget % EPOCHS_PER_PERIOD
    return quota if quota < remaining_budget else remaining_budget


def sort_logs(logs: List[dict]) -> List[dict]:
    return sorted(
        logs,
        key=lambda log: (
            int(log["blockNumber"], 16) if isinstance(log["blockNumber"], str) else int(log["blockNumber"]),
            int(log["logIndex"], 16) if isinstance(log["logIndex"], str) else int(log["logIndex"]),
        ),
    )


def apply_transfer(
    balances: Dict[str, int], from_addr: str, to_addr: str, value: int
) -> None:
    if value < 0:
        raise ValueError("Negative Transfer value")
    from_lower = from_addr.lower()
    to_lower = to_addr.lower()

    if from_lower != ZERO_ADDRESS:
        next_bal = balances.get(from_lower, 0) - value
        if next_bal < 0:
            raise ValueError(
                f"Negative balance for {from_lower}; Transfer history is incomplete"
            )
        if next_bal == 0:
            balances.pop(from_lower, None)
        else:
            balances[from_lower] = next_bal

    if to_lower != ZERO_ADDRESS and value > 0:
        balances[to_lower] = balances.get(to_lower, 0) + value


async def index_transfer_events(
    client,
    token_address: str,
    balances: Dict[str, int],
    from_block: int,
    to_block: int,
    chunk_size: int,
) -> None:
    """Index ERC20 Transfer events over [from_block, to_block] into `balances` in-place."""
    if chunk_size <= 0:
        raise ValueError("Invalid log chunk size")

    for addr in list(balances.keys()):
        bal = balances[addr]
        if bal < 0:
            raise ValueError(
                f"Negative cached balance for {addr}; balance history is incomplete"
            )
        if bal == 0:
            del balances[addr]

    if from_block > to_block:
        return

    start = from_block
    while start <= to_block:
        end = min(start + chunk_size - 1, to_block)
        logs = await client.get_logs(
            address=token_address,
            topics=[TRANSFER_TOPIC],
            from_block=start,
            to_block=end,
        )
        for log in sort_logs(logs):
            topics = log.get("topics") or []
            if len(topics) < 3 or log.get("data") is None:
                raise ValueError("Incomplete Transfer log")
            from_addr = "0x" + topics[1][-40:].lower()
            to_addr = "0x" + topics[2][-40:].lower()
            data_hex = log["data"]
            raw = bytes.fromhex(data_hex[2:] if data_hex.startswith("0x") else data_hex)
            (value,) = abi_decode(["uint256"], raw)
            apply_transfer(balances, from_addr, to_addr, int(value))
        start = end + 1

    for addr in list(balances.keys()):
        if balances[addr] == 0:
            del balances[addr]


async def read_migration_batches(
    client,
    distributor: str,
    tip: int,
    chunk_size: int,
) -> Tuple[List[MigrationBatch], int]:
    """Read and validate all RewardsMigrated events up to `tip`."""
    if chunk_size <= 0:
        raise ValueError("Invalid migration log chunk size")

    initialization_block, expected_total, finished = await client.read_migration_state(
        distributor, block_number=tip
    )
    if initialization_block < 0 or initialization_block > tip:
        raise ValueError("Invalid initialization block")

    batches: List[MigrationBatch] = []
    total = 0
    closed = False

    start = initialization_block
    while start <= tip:
        end = min(start + chunk_size - 1, tip)
        logs = await client.get_logs(
            address=distributor,
            topics=[REWARDS_MIGRATED_TOPIC],
            from_block=start,
            to_block=end,
        )
        for log in sort_logs(logs):
            topics = log.get("topics") or []
            if len(topics) < 2 or log.get("data") is None:
                raise ValueError("Incomplete RewardsMigrated event")
            effective_epoch = int(topics[1], 16)
            data_hex = log["data"]
            raw = bytes.fromhex(data_hex[2:] if data_hex.startswith("0x") else data_hex)
            rewards_raw, total_amount, is_last_batch = abi_decode(
                ["(address,uint256)[]", "uint256", "bool"], raw
            )
            block_num = (
                int(log["blockNumber"], 16)
                if isinstance(log["blockNumber"], str)
                else int(log["blockNumber"])
            )
            log_idx = (
                int(log["logIndex"], 16)
                if isinstance(log["logIndex"], str)
                else int(log["logIndex"])
            )

            prev_epoch = batches[-1].effective_epoch if batches else 1
            if closed or effective_epoch < 1 or prev_epoch > effective_epoch:
                raise ValueError("Invalid migration sequence or batch after final closure")
            if not rewards_raw and not is_last_batch:
                raise ValueError("Empty non-final migration batch")

            previous_addr = ZERO_ADDRESS
            batch_total = 0
            rewards_list: List[Tuple[str, int]] = []
            for account, amount in rewards_raw:
                addr = str(account).lower()
                amt = int(amount)
                if addr == ZERO_ADDRESS or amt <= 0 or addr <= previous_addr:
                    raise ValueError(
                        "Invalid migrated allocation: accounts must be nonzero, "
                        "sorted within each batch and amounts positive"
                    )
                previous_addr = addr
                batch_total += amt
                rewards_list.append((addr, amt))

            if batch_total != int(total_amount):
                raise ValueError("RewardsMigrated total does not match allocations")

            batches.append(
                MigrationBatch(
                    effective_epoch=effective_epoch,
                    rewards=rewards_list,
                    total=batch_total,
                    is_last_batch=bool(is_last_batch),
                    block_number=block_num,
                    log_index=log_idx,
                )
            )
            total += batch_total
            closed = bool(is_last_batch)
        start = end + 1

    if total != expected_total or closed != finished:
        raise ValueError(
            "Incomplete migration history: total or final closure disagrees with Distributor"
        )
    return batches, total


def apply_migration_batches(
    cumulative: Dict[str, int],
    batches: Sequence[MigrationBatch],
    epoch: int,
) -> int:
    """Apply only batches whose `effective_epoch == epoch` into `cumulative`."""
    total = 0
    for batch in batches:
        if batch.effective_epoch != epoch:
            continue
        for account, amount in batch.rewards:
            addr = account.lower()
            cumulative[addr] = cumulative.get(addr, 0) + amount
        total += batch.total
    return total
