"""Historical eligibility resolution (`eth_getCode` + `ContractRegistered`) and allocation math.

Matches `rewards-program/scripts/snapshot/eligibility.ts`.
Strict rules:
- Repeat `eth_getCode` at `snapshot_block` on every epoch (never cache EOA status).
- Any RPC error or malformed response aborts computation (never assume EOA).
- Re-verify `snapshot_block` hash before and after queries to catch reorgs.
"""

import asyncio
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple

from oracle.src.rewards.rpc_client import event_topic

CONTRACT_REGISTERED_TOPIC = event_topic("ContractRegistered(uint256,address)")


def is_eligible(
    address: str,
    balance: int,
    min_eligible_balance: int,
    contracts: Set[str],
    registered: Set[str],
) -> bool:
    addr = address.lower()
    return (
        balance > 0
        and balance >= min_eligible_balance
        and (addr not in contracts or addr in registered)
    )


def compute_allocations(
    balances: Mapping[str, int],
    previous_cumulative: Mapping[str, int],
    contracts: Set[str],
    registered: Set[str],
    min_eligible_balance: int,
    epoch_budget: int,
) -> Tuple[Dict[str, int], Dict[str, int], int, int]:
    """Compute exact integer allocations for an epoch.

    Returns `(new_cumulative, daily_allocations, total_eligible_supply, distributed_today)`.
    """
    if epoch_budget < 0:
        raise ValueError("Negative epoch budget")
    if min_eligible_balance < 0:
        raise ValueError("Negative min_eligible_balance")

    eligible: Dict[str, int] = {}
    for raw_addr, bal in balances.items():
        addr = raw_addr.lower()
        if is_eligible(addr, bal, min_eligible_balance, contracts, registered):
            eligible[addr] = bal

    total_eligible_supply = sum(eligible.values())
    daily: Dict[str, int] = {}
    cumulative: Dict[str, int] = {
        addr.lower(): int(amt) for addr, amt in previous_cumulative.items() if int(amt) > 0
    }

    for addr, bal in eligible.items():
        today_share = (
            (bal * epoch_budget) // total_eligible_supply if total_eligible_supply > 0 else 0
        )
        daily[addr] = today_share
        accrued = cumulative.get(addr, 0) + today_share
        if accrued > 0:
            cumulative[addr] = accrued

    distributed_today = sum(daily.values())
    return cumulative, daily, total_eligible_supply, distributed_today


async def read_eligibility(
    client,
    distributor: str,
    balances: Mapping[str, int],
    snapshot_block: int,
    chunk_size: int,
    epoch: int,
    code_concurrency: int = 20,
    previous_from_block: int = 0,
    previous_registered: Optional[Iterable[str]] = None,
) -> Tuple[Set[str], Set[str], str]:
    """Resolve `(registered_contracts, contract_addresses, snapshot_block_hash)` at `snapshot_block`.

    Aborts if any `eth_getLogs` or `eth_getCode` call fails or if `snapshot_block`
    hash changes during queries.
    """
    if chunk_size <= 0:
        raise ValueError("Invalid log chunk size")
    if code_concurrency <= 0:
        raise ValueError("Invalid code concurrency")
    if previous_from_block < 0 or previous_from_block > snapshot_block + 1:
        raise ValueError("Invalid registration scan range")

    before_blk = await client.get_block(snapshot_block)
    before_hash = before_blk["hash"]

    registered: Set[str] = {
        addr.lower() for addr in (previous_registered or ())
    }

    start = previous_from_block
    while start <= snapshot_block:
        to_block = min(start + chunk_size - 1, snapshot_block)
        logs = await client.get_logs(
            address=distributor,
            topics=[CONTRACT_REGISTERED_TOPIC],
            from_block=start,
            to_block=to_block,
        )
        for log in logs:
            topics = log.get("topics") or []
            if len(topics) < 3:
                raise ValueError("Incomplete ContractRegistered event")
            effective_epoch = int(topics[1], 16)
            account = "0x" + topics[2][-40:].lower()
            if effective_epoch == 0:
                raise ValueError("Incomplete ContractRegistered event: effectiveEpoch == 0")
            if effective_epoch <= epoch:
                registered.add(account)
        start = to_block + 1

    # Query eth_getCode for every address with balance > 0 at snapshot_block.
    addresses: List[str] = [addr.lower() for addr, bal in balances.items() if bal > 0]
    contracts: Set[str] = set()

    for idx in range(0, len(addresses), code_concurrency):
        batch = addresses[idx : idx + code_concurrency]
        codes = await asyncio.gather(
            *(client.get_code(addr, snapshot_block) for addr in batch)
        )
        for addr, code in zip(batch, codes):
            if code != "0x":
                contracts.add(addr)

    after_blk = await client.get_block(snapshot_block)
    if not before_hash or before_hash != after_blk["hash"]:
        raise RuntimeError("Snapshot block changed during code queries (reorg detected)")

    return registered, contracts, before_hash
