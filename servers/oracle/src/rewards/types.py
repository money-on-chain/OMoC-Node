from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class HolderEntry:
    address: str
    cumulative_amount: int
    proof: List[str]


@dataclass(frozen=True)
class BalanceEntry:
    address: str
    balance: int


@dataclass(frozen=True)
class EpochJson:
    epoch: int
    snapshot_block: int
    merkle_root: str
    holders: List[HolderEntry]
    balances: List[BalanceEntry]
    registered_contracts: List[str]


@dataclass(frozen=True)
class EpochData:
    epoch: int
    merkle_root: str
    cid: str
    snapshot_block: int
    distributed_today: int


@dataclass(frozen=True)
class CandidateResult:
    epoch_data: EpochData
    snapshot_block_hash: str
    json_path: str
    raw_bytes: bytes
    min_eligible_balance: Optional[int] = None
    total_distributed_historical: Optional[int] = None


@dataclass(frozen=True)
class SyncResult:
    source: str
    epoch: int
    snapshot_block: int
    merkle_root: str
    cid: str
    json_path: Optional[str]


@dataclass(frozen=True)
class MigrationBatch:
    effective_epoch: int
    rewards: List[Tuple[str, int]]
    total: int
    is_last_batch: bool
    block_number: int
    log_index: int


@dataclass(frozen=True)
class PublishedEpochEvent:
    epoch: int
    root: str
    cid: str
    snapshot_block: int
    distributed_today: int
    block_number: int
    log_index: int
