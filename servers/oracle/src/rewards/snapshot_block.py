"""Deterministic snapshot block selection with confirmation depth and reorg checks.

Matches `rewards-program/scripts/snapshot/snapshot-block.ts` with confirmation
gating (`confirmations`) so every oracle selects the exact same finalized block.
"""

from typing import Optional, Tuple


class SnapshotNotReadyError(RuntimeError):
    """Raised when the cutoff has not yet reached the required confirmation depth."""


class SnapshotBoundaryError(RuntimeError):
    """Raised when the chain boundary changed during binary search (reorg)."""


async def find_snapshot_block(
    client,
    cutoff_timestamp: int,
    latest_block: int,
    initialization_block: int = 0,
    confirmations: int = 0,
) -> Tuple[int, str]:
    """Select the deterministic snapshot block and its hash for `cutoff_timestamp`.

    Returns `(snapshot_block, snapshot_block_hash)`.
    Raises `SnapshotNotReadyError` if `latest_block < confirmations` or the
    confirmed tip has not yet reached `cutoff_timestamp`.
    """
    if confirmations < 0:
        raise ValueError("confirmations must be non-negative")
    if latest_block < confirmations:
        raise SnapshotNotReadyError(
            f"Latest block {latest_block} is below required confirmations {confirmations}"
        )

    confirmed_tip = latest_block - confirmations
    if initialization_block < 0 or initialization_block > confirmed_tip:
        raise SnapshotNotReadyError(
            f"Confirmed tip {confirmed_tip} has not passed initialization block {initialization_block}"
        )

    tip_block = await client.get_block(confirmed_tip)
    if tip_block["timestamp"] < cutoff_timestamp:
        raise SnapshotNotReadyError(
            f"Confirmed tip {confirmed_tip} (ts={tip_block['timestamp']}) "
            f"has not reached cutoff {cutoff_timestamp}"
        )

    # Binary search for the first block `lower` in [0, confirmed_tip] with timestamp >= cutoff.
    lower = 0
    upper = confirmed_tip
    while lower < upper:
        middle = (lower + upper) // 2
        blk = await client.get_block(middle)
        if blk["timestamp"] < cutoff_timestamp:
            lower = middle + 1
        else:
            upper = middle

    # Bootstrap rule: if the first cutoff equals or predates initialization,
    # use initialization_block so initial registrations are visible.
    if initialization_block > 0 and lower <= initialization_block:
        snap_blk = await client.get_block(initialization_block)
        return initialization_block, snap_blk["hash"]

    if lower == 0:
        raise SnapshotBoundaryError("No block exists before the epoch cutoff")

    snapshot_block = lower - 1
    before_blk = await client.get_block(snapshot_block)
    after_blk = await client.get_block(lower)
    if before_blk["timestamp"] >= cutoff_timestamp or after_blk["timestamp"] < cutoff_timestamp:
        raise SnapshotBoundaryError(
            "Snapshot boundary changed during block selection; retry"
        )

    return snapshot_block, before_blk["hash"]


async def verify_snapshot_block_hash(
    client, snapshot_block: int, expected_hash: str
) -> bool:
    """Return True iff `snapshot_block` still has `expected_hash` on chain."""
    blk = await client.get_block(snapshot_block)
    return blk["hash"].lower() == expected_hash.lower()
