"""Tests for the standalone single-operator Rewards CLI and PinataPinner."""

import pytest
from eth_account import Account

from oracle.src.rewards.cli import CliConfig, run_epoch_cycle
from oracle.src.rewards.cid import compute_cid_v1
from oracle.src.rewards.ipfs_pinner import PinataPinner
from oracle.src.rewards.types import EpochData
from oracle.src.test_rewards_engine import (
    DISTRIBUTOR,
    EOA_1,
    FakeArchiveRpc,
    ZERO_ADDR,
    _transfer_log,
)

OPERATOR_KEY = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
OPERATOR_ADDR = Account.from_key(OPERATOR_KEY).address.lower()
OTHER_KEY = "0xabcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"


class FakePinner:
    def __init__(self):
        self.calls = []

    async def pin_bytes(self, raw_bytes: bytes, expected_cid: str, filename: str) -> str:
        assert compute_cid_v1(raw_bytes) == expected_cid
        self.calls.append((filename, expected_cid, raw_bytes))
        return expected_cid


class FakeTxSender:
    def __init__(self, rpc: FakeArchiveRpc, next_cutoff_step: int = 30):
        self.rpc = rpc
        self.next_cutoff_step = next_cutoff_step
        self.published = []
        self.started_periods = 0

    async def publish_epoch(self, epoch_data: EpochData, operator_private_key: str) -> str:
        self.published.append(epoch_data)
        self.rpc.state["currentEpoch"] = epoch_data.epoch
        self.rpc.state["currentRoot"] = epoch_data.merkle_root
        self.rpc.state["currentIpfsCid"] = epoch_data.cid
        self.rpc.state["currentSnapshotBlock"] = epoch_data.snapshot_block
        self.rpc.state["totalDistributedHistorical"] += epoch_data.distributed_today
        # Advance nextEpochTime beyond confirmed tip unless catching up
        next_blk = epoch_data.snapshot_block + 1 + self.next_cutoff_step
        if next_blk in self.rpc.blocks:
            self.rpc.state["nextEpochTime"] = self.rpc.blocks[next_blk]["timestamp"]
        else:
            self.rpc.state["canPublishEpoch"] = False
        return "0x" + f"{epoch_data.epoch:064x}"

    async def start_distribution_period(self, task_private_key: str) -> str:
        self.started_periods += 1
        return "0x" + "aa" * 32


@pytest.mark.asyncio
async def test_cli_not_due_returns_cleanly(tmp_path):
    rpc = FakeArchiveRpc(num_blocks=60)
    rpc.state["canPublishEpoch"] = False
    rpc.state["operator"] = OPERATOR_ADDR

    cfg = CliConfig(
        rpc_url="http://localhost:8545",
        distributor_address=DISTRIBUTOR,
        state_dir=str(tmp_path / "state"),
        operator_private_key=OPERATOR_KEY,
        snapshot_confirmations=12,
    )
    pinner = FakePinner()
    sender = FakeTxSender(rpc)

    res = await run_epoch_cycle(cfg, rpc_client=rpc, tx_sender=sender, pinners=[pinner])
    assert res.status == "not_due"
    assert res.published_epochs == []
    assert pinner.calls == []
    assert sender.published == []


@pytest.mark.asyncio
async def test_cli_dry_run_computes_without_pinning_or_publishing(tmp_path):
    rpc = FakeArchiveRpc(num_blocks=60)
    rpc.state["operator"] = OPERATOR_ADDR
    rpc.logs.append(_transfer_log(10, 0, ZERO_ADDR, EOA_1, 500))

    cfg = CliConfig(
        rpc_url="http://localhost:8545",
        distributor_address=DISTRIBUTOR,
        state_dir=str(tmp_path / "state"),
        snapshot_confirmations=12,
        dry_run=True,
    )
    pinner = FakePinner()
    sender = FakeTxSender(rpc)

    res = await run_epoch_cycle(cfg, rpc_client=rpc, tx_sender=sender, pinners=[pinner])
    assert res.status == "dry_run"
    assert res.published_epochs == []
    assert res.last_epoch_data is not None
    assert res.last_epoch_data.epoch == 1
    assert res.last_epoch_data.distributed_today == 3000
    assert pinner.calls == []
    assert sender.published == []


@pytest.mark.asyncio
async def test_cli_publishes_overdue_epochs_and_prunes_disk(tmp_path):
    # Cutoff 1 at block 20 (snap 19), cutoff 2 at block 40 (snap 39), tip 80 (confirmations 12 -> 68)
    rpc = FakeArchiveRpc(num_blocks=80)
    rpc.state["operator"] = OPERATOR_ADDR
    rpc.logs.append(_transfer_log(10, 0, ZERO_ADDR, EOA_1, 500))

    cfg = CliConfig(
        rpc_url="http://localhost:8545",
        distributor_address=DISTRIBUTOR,
        state_dir=str(tmp_path / "state"),
        operator_private_key=OPERATOR_KEY,
        snapshot_confirmations=12,
        max_epochs=5,
    )
    pinner = FakePinner()
    sender = FakeTxSender(rpc, next_cutoff_step=20)

    res = await run_epoch_cycle(cfg, rpc_client=rpc, tx_sender=sender, pinners=[pinner])
    assert res.status == "published"
    # Should publish epochs 1 (snap 19), 2 (snap 39), and 3 (snap 59); block 80 - 12 = 68 < 80
    assert res.published_epochs == [1, 2, 3]
    assert len(pinner.calls) == 3
    assert [ed.epoch for ed in sender.published] == [1, 2, 3]

    # Disk must retain ONLY the latest published epoch_3.json and zero candidates
    published_files = sorted(p.name for p in (tmp_path / "state" / "published").iterdir())
    candidate_files = sorted(p.name for p in (tmp_path / "state" / "candidates").iterdir())
    assert published_files == ["epoch_3.json"]
    assert candidate_files == []


@pytest.mark.asyncio
async def test_cli_rejects_mismatched_operator_key(tmp_path):
    rpc = FakeArchiveRpc(num_blocks=60)
    rpc.state["operator"] = OPERATOR_ADDR
    rpc.logs.append(_transfer_log(10, 0, ZERO_ADDR, EOA_1, 500))

    cfg = CliConfig(
        rpc_url="http://localhost:8545",
        distributor_address=DISTRIBUTOR,
        state_dir=str(tmp_path / "state"),
        operator_private_key=OTHER_KEY,
        snapshot_confirmations=12,
    )
    pinner = FakePinner()
    sender = FakeTxSender(rpc)

    with pytest.raises(RuntimeError, match="does not match Distributor.operator"):
        await run_epoch_cycle(cfg, rpc_client=rpc, tx_sender=sender, pinners=[pinner])
    assert pinner.calls == []
    assert sender.published == []


def test_pinata_pinner_enabled_flag():
    assert not PinataPinner("").enabled
    assert PinataPinner("jwt-token").enabled


@pytest.mark.asyncio
async def test_cli_aborts_publish_if_policy_or_snapshot_changes_during_pinning(tmp_path):
    rpc = FakeArchiveRpc(num_blocks=60)
    rpc.state["operator"] = OPERATOR_ADDR
    rpc.logs.append(_transfer_log(10, 0, ZERO_ADDR, EOA_1, 500))

    class MutatingPinner(FakePinner):
        async def pin_bytes(self, raw_bytes: bytes, expected_cid: str, filename: str) -> str:
            res = await super().pin_bytes(raw_bytes, expected_cid, filename)
            # Simulate governance updating minEligibleBalance while pinning was in flight
            rpc.state["minEligibleBalance"] = 9999
            return res

    cfg = CliConfig(
        rpc_url="http://localhost:8545",
        distributor_address=DISTRIBUTOR,
        state_dir=str(tmp_path / "state"),
        operator_private_key=OPERATOR_KEY,
        snapshot_confirmations=12,
    )
    sender = FakeTxSender(rpc)
    with pytest.raises(RuntimeError, match="minEligibleBalance changed during pinning"):
        await run_epoch_cycle(cfg, rpc_client=rpc, tx_sender=sender, pinners=[MutatingPinner()])
    assert sender.published == []