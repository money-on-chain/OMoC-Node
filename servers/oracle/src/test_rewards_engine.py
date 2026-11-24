"""Tests for RewardsEngine, eligibility, migrations, reorg handling, recovery, and RewardsRunner."""

import asyncio
from typing import Dict, List, Tuple
from unittest.mock import Mock

import pytest
from web3 import Web3

from common.services.coin_pair_service_types import CoinPairServiceType
from common.services.oracle_dao import CoinPair, FullOracleRoundInfo, OracleBlockchainInfo
from oracle.src.rewards.cid import compute_cid_v1
from oracle.src.rewards.eligibility import CONTRACT_REGISTERED_TOPIC, compute_allocations
from oracle.src.rewards.engine import RewardsEngine
from oracle.src.rewards.epoch_json import build_epoch_json, serialize_epoch_json
from oracle.src.rewards.indexer import (
    EPOCH_INTERVAL,
    PERIOD_DURATION,
    REWARDS_MIGRATED_TOPIC,
    TRANSFER_TOPIC,
)
from oracle.src.rewards.ipfs_pinner import IpfsPinner
from oracle.src.rewards.recovery import (
    DISTRIBUTION_PERIOD_STARTED_TOPIC,
    EPOCH_PUBLISHED_TOPIC,
    MIN_ELIGIBLE_UPDATED_TOPIC,
)
from oracle.src.rewards.rpc_client import ArchiveRpcError, abi_encode
from oracle.src.rewards.state_store import RewardsStateStore
from oracle.src.rewards_runner import RewardsRunner

ZERO_ADDR = "0x0000000000000000000000000000000000000000"
DISTRIBUTOR = "0x000000000000000000000000000000000000d157"
PUBLISHER = "0x00000000000000000000000000000000000090b1"
TOKEN = "0x000000000000000000000000000000000000b900"

EOA_1 = "0x0000000000000000000000000000000000000011"
EOA_2 = "0x0000000000000000000000000000000000000022"
CONTRACT_REG = "0x0000000000000000000000000000000000000033"
CONTRACT_UNREG = "0x0000000000000000000000000000000000000044"


def _topic_uint(val: int) -> str:
    return "0x" + f"{val:064x}"


def _topic_addr(addr: str) -> str:
    return "0x" + "0" * 24 + addr.lower().replace("0x", "")


def _transfer_log(block: int, log_index: int, from_addr: str, to_addr: str, value: int):
    return {
        "address": TOKEN,
        "topics": [TRANSFER_TOPIC, _topic_addr(from_addr), _topic_addr(to_addr)],
        "data": "0x" + abi_encode(["uint256"], [value]).hex(),
        "blockNumber": hex(block),
        "logIndex": hex(log_index),
    }


def _contract_registered_log(block: int, log_index: int, effective_epoch: int, account: str):
    return {
        "address": DISTRIBUTOR,
        "topics": [CONTRACT_REGISTERED_TOPIC, _topic_uint(effective_epoch), _topic_addr(account)],
        "data": "0x",
        "blockNumber": hex(block),
        "logIndex": hex(log_index),
    }


def _min_eligible_log(block: int, log_index: int, effective_epoch: int, value: int):
    return {
        "address": DISTRIBUTOR,
        "topics": [MIN_ELIGIBLE_UPDATED_TOPIC, _topic_uint(effective_epoch)],
        "data": "0x" + abi_encode(["uint256"], [value]).hex(),
        "blockNumber": hex(block),
        "logIndex": hex(log_index),
    }


def _period_started_log(block: int, log_index: int, period: int, start_time: int, budget: int):
    return {
        "address": DISTRIBUTOR,
        "topics": [DISTRIBUTION_PERIOD_STARTED_TOPIC, _topic_uint(period)],
        "data": "0x" + abi_encode(["uint256", "uint256", "uint256"], [start_time, start_time + PERIOD_DURATION, budget]).hex(),
        "blockNumber": hex(block),
        "logIndex": hex(log_index),
    }


def _epoch_published_log(block: int, log_index: int, epoch: int, root: str, cid: str, snap_blk: int, distributed: int):
    return {
        "address": DISTRIBUTOR,
        "topics": [EPOCH_PUBLISHED_TOPIC, _topic_uint(epoch)],
        "data": "0x"
        + abi_encode(
            ["bytes32", "string", "uint256", "uint256"],
            [bytes.fromhex(root[2:]), cid, snap_blk, distributed],
        ).hex(),
        "blockNumber": hex(block),
        "logIndex": hex(log_index),
    }


def _migration_log(block: int, log_index: int, effective_epoch: int, rewards: List[Tuple[str, int]], is_last: bool):
    total = sum(amt for _, amt in rewards)
    checksum_rewards = [(Web3.toChecksumAddress(a), amt) for a, amt in rewards]
    return {
        "address": DISTRIBUTOR,
        "topics": [REWARDS_MIGRATED_TOPIC, _topic_uint(effective_epoch)],
        "data": "0x"
        + abi_encode(
            ["(address,uint256)[]", "uint256", "bool"],
            [checksum_rewards, total, is_last],
        ).hex(),
        "blockNumber": hex(block),
        "logIndex": hex(log_index),
    }


class FakeArchiveRpc:
    """In-memory archive RPC simulator supporting blocks, logs, eth_getCode, and Distributor state."""

    def __init__(self, start_ts: int = 1_700_000_000, num_blocks: int = 120):
        self.blocks: Dict[int, dict] = {}
        for n in range(num_blocks + 1):
            self.blocks[n] = {
                "number": n,
                "hash": "0x" + f"{n + 1:064x}",
                "timestamp": start_ts + n * 30,
            }
        self.logs: List[dict] = []
        # code_at[(addr_lower, block_number)] = "0x..." ; defaults to "0x"
        self.code_by_block: Dict[Tuple[str, int], str] = {}
        self.fail_code_for: set = set()
        self.reorg_block_on_second_read: Dict[int, str] = {}
        self._block_read_counts: Dict[int, int] = {}

        self.state = {
            "currentEpoch": 0,
            "currentRoot": "0x" + "00" * 32,
            "currentIpfsCid": "",
            "currentSnapshotBlock": 0,
            "nextEpochTime": start_ts + 20 * 30,
            "canPublishEpoch": True,
            "minEligibleBalance": 100,
            "totalDistributedHistorical": 0,
            "initializationBlock": 5,
            "holdingsToken": TOKEN,
            "openedPeriodCount": 1,
            "operator": PUBLISHER,
            "paused": False,
            "distributionStartTime": start_ts + 20 * 30,
            "epochInterval": EPOCH_INTERVAL,
        }
        self.next_epoch_budget = 3000
        self.total_migrated = 0
        self.migration_finished = False

    async def get_block_number(self) -> int:
        return max(self.blocks.keys())

    async def get_block(self, block_number: int) -> dict:
        self._block_read_counts[block_number] = self._block_read_counts.get(block_number, 0) + 1
        blk = dict(self.blocks[block_number])
        if (
            block_number in self.reorg_block_on_second_read
            and self._block_read_counts[block_number] >= 3
        ):
            blk["hash"] = self.reorg_block_on_second_read[block_number]
        return blk

    async def get_code(self, address: str, block_number: int) -> str:
        addr = address.lower()
        if addr in self.fail_code_for:
            raise ArchiveRpcError(f"Simulated archive error for {addr}")
        return self.code_by_block.get((addr, block_number), "0x")

    async def get_logs(self, address: str, topics, from_block: int, to_block: int):
        addr = address.lower()
        topic0 = topics[0] if topics else None
        out = []
        for log in self.logs:
            blk = int(log["blockNumber"], 16)
            if blk < from_block or blk > to_block:
                continue
            if log["address"].lower() != addr:
                continue
            if topic0 and log["topics"][0] != topic0:
                continue
            out.append(log)
        return out

    async def read_distributor_state(self, distributor: str, block_number="latest") -> dict:
        return dict(self.state)

    async def read_next_epoch_budget(self, distributor: str, block_number="latest") -> int:
        return self.next_epoch_budget

    async def read_migration_state(self, distributor: str, block_number="latest"):
        return self.state["initializationBlock"], self.total_migrated, self.migration_finished


@pytest.mark.asyncio
async def test_eligibility_eoa_registered_unregistered_and_migration(tmp_path):
    rpc = FakeArchiveRpc(num_blocks=60)
    # Cutoff at block 20 -> snapshot_block = 19 (since block 19 ts < cutoff <= block 20 ts)
    rpc.logs.extend(
        [
            _transfer_log(10, 0, ZERO_ADDR, EOA_1, 300),          # eligible (>= 100)
            _transfer_log(10, 1, ZERO_ADDR, EOA_2, 50),           # below minEligibleBalance (100)
            _transfer_log(10, 2, ZERO_ADDR, CONTRACT_REG, 300),   # registered contract -> eligible
            _transfer_log(10, 3, ZERO_ADDR, CONTRACT_UNREG, 300), # unregistered contract -> excluded
            _contract_registered_log(12, 0, 1, CONTRACT_REG),
            _migration_log(15, 0, 1, [(EOA_2, 500)], is_last=True),
        ]
    )
    rpc.code_by_block[(CONTRACT_REG, 19)] = "0x6080"
    rpc.code_by_block[(CONTRACT_UNREG, 19)] = "0x6080"
    rpc.total_migrated = 500
    rpc.migration_finished = True
    rpc.state["totalDistributedHistorical"] = 500  # migration debt added before epoch 1

    store = RewardsStateStore(str(tmp_path / "state"))
    engine = RewardsEngine(
        rpc_client=rpc,
        distributor_address=DISTRIBUTOR,
        state_store=store,
        snapshot_confirmations=12,
        log_chunk_size=10,
        code_concurrency=2,
    )

    sync_res = await engine.sync()
    assert sync_res.source == "genesis"

    cand = await engine.compute()
    assert cand is not None
    assert cand.epoch_data.epoch == 1
    assert cand.epoch_data.snapshot_block == 19
    # Budget 3000 split equally between EOA_1 (300) and CONTRACT_REG (300) -> 1500 each
    assert cand.epoch_data.distributed_today == 3000

    loaded = store.load_candidate(1, 19, cand.snapshot_block_hash)
    assert loaded is not None
    ep_json, raw_bytes, _ = loaded
    assert compute_cid_v1(raw_bytes) == cand.epoch_data.cid
    holder_map = {h.address: h.cumulative_amount for h in ep_json.holders}
    assert holder_map == {
        EOA_1: 1500,
        EOA_2: 500,          # migrated balance preserved even though ineligible today
        CONTRACT_REG: 1500,
    }
    assert CONTRACT_UNREG not in holder_map


@pytest.mark.asyncio
async def test_eoa_becoming_contract_in_later_epoch_is_not_cached(tmp_path):
    rpc = FakeArchiveRpc(num_blocks=100)
    # Epoch 1 at snapshotBlock 19: EOA_1 has no code
    rpc.logs.extend(
        [
            _transfer_log(10, 0, ZERO_ADDR, EOA_1, 500),
            _transfer_log(10, 1, ZERO_ADDR, EOA_2, 500),
        ]
    )
    rpc.state["minEligibleBalance"] = 0
    store = RewardsStateStore(str(tmp_path / "state"))
    engine = RewardsEngine(
        rpc_client=rpc,
        distributor_address=DISTRIBUTOR,
        state_store=store,
        snapshot_confirmations=12,
        log_chunk_size=25,
    )
    await engine.sync()
    cand1 = await engine.compute()
    assert cand1 is not None
    store.save_published(1, cand1.raw_bytes)
    engine._last_synced_epoch = 1

    # Advance to epoch 2 (cutoff at block 50 -> snapshotBlock 49)
    # EOA_1 deploys code at block 49 and is NOT registered!
    rpc.state["currentEpoch"] = 1
    rpc.state["currentRoot"] = cand1.epoch_data.merkle_root
    rpc.state["currentIpfsCid"] = cand1.epoch_data.cid
    rpc.state["currentSnapshotBlock"] = 19
    rpc.state["totalDistributedHistorical"] = cand1.epoch_data.distributed_today
    rpc.state["nextEpochTime"] = rpc.blocks[50]["timestamp"]
    rpc.code_by_block[(EOA_1, 49)] = "0x6000"

    cand2 = await engine.compute()
    assert cand2 is not None
    assert cand2.epoch_data.epoch == 2
    assert cand2.epoch_data.snapshot_block == 49

    loaded = store.load_candidate(2, 49, cand2.snapshot_block_hash)
    ep2_json = loaded[0]
    holder_map = {h.address: h.cumulative_amount for h in ep2_json.holders}
    # Epoch 1: EOA_1 got 1500, EOA_2 got 1500.
    # Epoch 2: only EOA_2 is eligible -> EOA_2 gets all 3000 (total 4500), EOA_1 stays at 1500.
    assert holder_map == {EOA_1: 1500, EOA_2: 4500}


@pytest.mark.asyncio
async def test_eth_get_code_error_aborts_and_reorg_aborts(tmp_path):
    rpc = FakeArchiveRpc(num_blocks=60)
    rpc.logs.append(_transfer_log(10, 0, ZERO_ADDR, EOA_1, 500))
    rpc.fail_code_for.add(EOA_1)

    store = RewardsStateStore(str(tmp_path / "state"))
    engine = RewardsEngine(
        rpc_client=rpc,
        distributor_address=DISTRIBUTOR,
        state_store=store,
        snapshot_confirmations=12,
    )
    await engine.sync()
    with pytest.raises(ArchiveRpcError):
        await engine.compute()

    # Now fix eth_getCode, but simulate reorg changing snapshot block 19 hash mid-query
    rpc.fail_code_for.clear()
    rpc._block_read_counts.clear()
    rpc.reorg_block_on_second_read[19] = "0x" + "ff" * 32
    with pytest.raises(RuntimeError, match="reorg|changed"):
        await engine.compute()


@pytest.mark.asyncio
async def test_new_node_sync_recovers_trustlessly_from_chain_and_computes_next(tmp_path):
    rpc = FakeArchiveRpc(num_blocks=120)
    start_ts = rpc.state["distributionStartTime"]
    period_budget = 90_000  # 3000 per epoch
    # Epoch 1 published on-chain at block 25 using snapshotBlock 19
    ep1_cum, _, _, ep1_dist = compute_allocations(
        balances={EOA_1: 400, EOA_2: 600},
        previous_cumulative={},
        contracts=set(),
        registered=set(),
        min_eligible_balance=100,
        epoch_budget=3000,
    )
    ep1_json = build_epoch_json(
        epoch=1,
        snapshot_block=19,
        holders=list(ep1_cum.items()),
        balances=[(EOA_1, 400), (EOA_2, 600)],
        registered_contracts=[],
        expected_total=ep1_dist,
    )
    ep1_cid = compute_cid_v1(serialize_epoch_json(ep1_json))

    rpc.logs.extend(
        [
            _min_eligible_log(5, 0, 1, 100),
            _period_started_log(6, 0, 0, start_ts, period_budget),
            _transfer_log(10, 0, ZERO_ADDR, EOA_1, 400),
            _transfer_log(10, 1, ZERO_ADDR, EOA_2, 600),
            _epoch_published_log(25, 0, 1, ep1_json.merkle_root, ep1_cid, 19, ep1_dist),
            # Additional transfer before epoch 2 snapshot (block 49)
            _transfer_log(30, 0, EOA_2, EOA_1, 100),
        ]
    )
    rpc.state["currentEpoch"] = 1
    rpc.state["currentRoot"] = ep1_json.merkle_root
    rpc.state["currentIpfsCid"] = ep1_cid
    rpc.state["currentSnapshotBlock"] = 19
    rpc.state["totalDistributedHistorical"] = ep1_dist
    rpc.state["nextEpochTime"] = rpc.blocks[50]["timestamp"]

    # Brand new node: empty state dir, NO IPFS gateways
    store = RewardsStateStore(str(tmp_path / "fresh_node"))
    engine = RewardsEngine(
        rpc_client=rpc,
        distributor_address=DISTRIBUTOR,
        state_store=store,
        snapshot_confirmations=12,
        log_chunk_size=15,
        ipfs_gateways=(),
    )

    sync_res = await engine.sync()
    assert sync_res.source == "chain_recovery"
    assert sync_res.epoch == 1
    assert sync_res.merkle_root == ep1_json.merkle_root
    assert store.load_published(1) is not None

    # Now compute epoch 2 incrementally
    cand2 = await engine.compute()
    assert cand2 is not None
    assert cand2.epoch_data.epoch == 2
    assert cand2.epoch_data.snapshot_block == 49
    # Balances at block 49 are 500 / 500 -> each gets 1500 on top of epoch 1 (1200 / 1800)
    ep2_json = store.load_candidate(2, 49, cand2.snapshot_block_hash)[0]
    holder_map = {h.address: h.cumulative_amount for h in ep2_json.holders}
    assert holder_map == {EOA_1: 2700, EOA_2: 3300}


@pytest.mark.asyncio
async def test_rewards_runner_syncing_blocks_turn_and_ipfs_failure_does_not_block(tmp_path, monkeypatch):
    from starlette.datastructures import Secret
    from common.services.blockchain import BlockchainAccount
    from oracle.src import oracle_settings
    from oracle.src import oracle_turn

    acc = BlockchainAccount(EOA_1, Secret("0x" + "11" * 32))
    monkeypatch.setattr(oracle_settings, "get_oracle_account", lambda: acc)
    monkeypatch.setattr(oracle_turn, "get_oracle_account", lambda: acc)

    rpc = FakeArchiveRpc(num_blocks=60)
    rpc.logs.append(_transfer_log(10, 0, ZERO_ADDR, EOA_1, 500))
    store = RewardsStateStore(str(tmp_path / "runner_state"))
    engine = RewardsEngine(
        rpc_client=rpc,
        distributor_address=DISTRIBUTOR,
        state_store=store,
        snapshot_confirmations=12,
    )

    # Failing Kubo pinner must never block publishing
    failing_pinner = IpfsPinner("http://127.0.0.1:1")
    cps = Mock()
    cps.coin_pair = CoinPair("BPRO_REWARDS")
    cps.addr = PUBLISHER
    cps.coin_pair_type = CoinPairServiceType.REWARDS_PUBLISHER
    cps._blockchain = Mock(chain_id=31)

    bc_info = OracleBlockchainInfo(
        coin_pair=CoinPair("BPRO_REWARDS"),
        selected_oracles=[FullOracleRoundInfo(EOA_1, "http://o1:5556", 100, EOA_1, 0, True, 1)],
        blockchain_price=0,
        block_num=60,
        last_pub_block=10,
        last_pub_block_hash=b"\x02" * 32,
        valid_price_period_in_blocks=0,
    )
    vi_loop = Mock()
    vi_loop.get.return_value = bc_info

    conf = Mock()
    conf.get_oracle_turn_conf.return_value = Mock(
        price_delta_pct=0,
        price_publish_blocks=0,
        entering_fallbacks_amounts=b"\x00\x01",
        trigger_valid_publication_blocks=10,
    )

    runner = RewardsRunner(conf, cps, vi_loop, engine=engine, pinner=failing_pinner)
    # First call triggers background compute and returns not available yet (non-blocking)
    avail, my_turn, order = await runner.is_oracle_turn(bc_info, EOA_1)
    assert avail is False

    # Wait for background compute task to finish
    await runner._compute_task

    # Next call sees ready candidate and evaluates turn
    avail2, my_turn2, order2 = await runner.is_oracle_turn(bc_info, EOA_1)
    assert avail2 is True
    assert my_turn2 is True
    params = runner.prepare_publish_params(bc_info, EOA_1)
    assert params.epoch == 1
    assert params.distributed_today == 3000


@pytest.mark.asyncio
async def test_rewards_runner_requeues_ipfs_pin_after_restart_sync(tmp_path, monkeypatch):
    from starlette.datastructures import Secret
    from common.services.blockchain import BlockchainAccount
    from oracle.src import oracle_settings
    from oracle.src import oracle_turn

    acc = BlockchainAccount(EOA_1, Secret("0x" + "11" * 32))
    monkeypatch.setattr(oracle_settings, "get_oracle_account", lambda: acc)
    monkeypatch.setattr(oracle_turn, "get_oracle_account", lambda: acc)

    rpc = FakeArchiveRpc(num_blocks=60)
    ep1_json = build_epoch_json(
        epoch=1,
        snapshot_block=19,
        holders=[(EOA_1, 3000)],
        balances=[(EOA_1, 500)],
        registered_contracts=[],
        expected_total=3000,
    )
    ep1_raw = serialize_epoch_json(ep1_json)
    ep1_cid = compute_cid_v1(ep1_raw)

    store = RewardsStateStore(str(tmp_path / "restart_state"))
    store.save_published(1, ep1_raw)

    rpc.state["currentEpoch"] = 1
    rpc.state["currentRoot"] = ep1_json.merkle_root
    rpc.state["currentIpfsCid"] = ep1_cid
    rpc.state["currentSnapshotBlock"] = 19
    rpc.state["totalDistributedHistorical"] = 3000
    rpc.state["canPublishEpoch"] = False

    engine = RewardsEngine(
        rpc_client=rpc,
        distributor_address=DISTRIBUTOR,
        state_store=store,
        snapshot_confirmations=12,
    )

    pinned_calls = []

    class RecordingPinner(IpfsPinner):
        def __init__(self):
            super().__init__("http://127.0.0.1:5001")

        async def pin_bytes(self, raw_bytes: bytes, expected_cid: str, filename: str) -> str:
            pinned_calls.append((expected_cid, filename, raw_bytes))
            return expected_cid

    cps = Mock()
    cps.coin_pair = CoinPair("BPRO_REWARDS")
    cps.addr = PUBLISHER
    cps.coin_pair_type = CoinPairServiceType.REWARDS_PUBLISHER
    cps._blockchain = Mock(chain_id=31)

    bc_info = OracleBlockchainInfo(
        coin_pair=CoinPair("BPRO_REWARDS"),
        selected_oracles=[FullOracleRoundInfo(EOA_1, "http://o1:5556", 100, EOA_1, 0, True, 1)],
        blockchain_price=0,
        block_num=60,
        last_pub_block=10,
        last_pub_block_hash=b"\x02" * 32,
        valid_price_period_in_blocks=0,
    )
    vi_loop = Mock()
    vi_loop.get.return_value = bc_info
    conf = Mock()
    conf.get_oracle_turn_conf.return_value = Mock(
        price_delta_pct=0,
        price_publish_blocks=0,
        entering_fallbacks_amounts=b"\x00\x01",
        trigger_valid_publication_blocks=10,
    )

    runner = RewardsRunner(conf, cps, vi_loop, engine=engine, pinner=RecordingPinner())
    avail, _, _ = await runner.is_oracle_turn(bc_info, EOA_1)
    assert avail is False
    await runner._sync_task
    assert runner._pin_task is not None
    await runner._pin_task
    assert len(pinned_calls) == 1
    assert pinned_calls[0][0] == ep1_cid
    assert pinned_calls[0][1] == "epoch_1.json"
    assert pinned_calls[0][2] == ep1_raw
    assert 1 not in runner._pending_pins

    # Verify stop_bg_task cancels active tasks cleanly
    runner._sync_task = asyncio.create_task(asyncio.sleep(60))
    runner._compute_task = asyncio.create_task(asyncio.sleep(60))
    runner._pin_task = asyncio.create_task(asyncio.sleep(60))
    runner.stop_bg_task()
    assert runner._sync_task is None
    assert runner._compute_task is None
    assert runner._pin_task is None
    assert runner.is_syncing is False


@pytest.mark.asyncio
async def test_state_store_prunes_old_published_and_candidates(tmp_path):
    store = RewardsStateStore(str(tmp_path / "prune_state"))
    ep1_raw = serialize_epoch_json(
        build_epoch_json(1, 10, [(EOA_1, 100)], [(EOA_1, 500)], [], 100)
    )
    ep2_raw = serialize_epoch_json(
        build_epoch_json(2, 20, [(EOA_1, 200)], [(EOA_1, 500)], [], 200)
    )
    store.save_candidate(1, 10, "0x" + "aa" * 32, ep1_raw)
    store.save_candidate(1, 10, "0x" + "bb" * 32, ep1_raw)
    # Only the latest candidate for epoch 1 should remain
    assert len(list((tmp_path / "prune_state" / "candidates").iterdir())) == 1

    store.save_published(1, ep1_raw)
    assert (tmp_path / "prune_state" / "published" / "epoch_1.json").exists()
    assert list((tmp_path / "prune_state" / "candidates").iterdir()) == []

    store.save_candidate(2, 20, "0x" + "cc" * 32, ep2_raw)
    store.save_published(2, ep2_raw)
    assert not (tmp_path / "prune_state" / "published" / "epoch_1.json").exists()
    assert (tmp_path / "prune_state" / "published" / "epoch_2.json").exists()
    assert list((tmp_path / "prune_state" / "candidates").iterdir()) == []


@pytest.mark.asyncio
async def test_sync_accepts_local_legacy_cidv0_without_re_recovery(tmp_path):
    rpc = FakeArchiveRpc(num_blocks=60)
    ep1_json = build_epoch_json(1, 19, [(EOA_1, 3000)], [(EOA_1, 500)], [], 3000)
    ep1_raw = serialize_epoch_json(ep1_json)

    store = RewardsStateStore(str(tmp_path / "legacy_state"))
    store.save_published(1, ep1_raw)

    rpc.state["currentEpoch"] = 1
    rpc.state["currentRoot"] = ep1_json.merkle_root
    rpc.state["currentIpfsCid"] = "QmLegacyPinataCidV0HashExample1234567890123456"
    rpc.state["currentSnapshotBlock"] = 19
    rpc.state["totalDistributedHistorical"] = 3000

    engine = RewardsEngine(
        rpc_client=rpc,
        distributor_address=DISTRIBUTOR,
        state_store=store,
        snapshot_confirmations=12,
    )
    res = await engine.sync()
    assert res.source == "local"
    assert res.epoch == 1


@pytest.mark.asyncio
async def test_runner_invalidates_candidate_on_policy_change_and_initializes_turn_block(
    tmp_path, monkeypatch
):
    from starlette.datastructures import Secret
    from common.services.blockchain import BlockchainAccount
    from oracle.src import oracle_settings, oracle_turn
    from oracle.src.oracle_publish_message import PublishRewardsParams, REWARDS_MESSAGE_VERSION

    acc = BlockchainAccount(EOA_1, Secret("0x" + "11" * 32))
    monkeypatch.setattr(oracle_settings, "get_oracle_account", lambda: acc)
    monkeypatch.setattr(oracle_turn, "get_oracle_account", lambda: acc)

    rpc = FakeArchiveRpc(num_blocks=60)
    rpc.logs.append(_transfer_log(10, 0, ZERO_ADDR, EOA_1, 500))
    store = RewardsStateStore(str(tmp_path / "policy_state"))
    engine = RewardsEngine(
        rpc_client=rpc,
        distributor_address=DISTRIBUTOR,
        state_store=store,
        snapshot_confirmations=12,
    )
    cps = Mock()
    cps.coin_pair = CoinPair("BPRO_REWARDS")
    cps.addr = PUBLISHER
    cps.coin_pair_type = CoinPairServiceType.REWARDS_PUBLISHER
    cps._blockchain = Mock(chain_id=31)

    bc_info = OracleBlockchainInfo(
        coin_pair=CoinPair("BPRO_REWARDS"),
        selected_oracles=[FullOracleRoundInfo(EOA_1, "http://o1:5556", 100, EOA_1, 0, True, 1)],
        blockchain_price=0,
        block_num=60,
        last_pub_block=10,
        last_pub_block_hash=b"\x02" * 32,
        valid_price_period_in_blocks=0,
    )
    vi_loop = Mock()
    vi_loop.get.return_value = bc_info
    conf = Mock()
    conf.get_oracle_turn_conf.return_value = Mock(
        price_delta_pct=0,
        price_publish_blocks=0,
        entering_fallbacks_amounts=b"\x00\x01",
        trigger_valid_publication_blocks=10,
    )

    runner = RewardsRunner(conf, cps, vi_loop, engine=engine, pinner=IpfsPinner(""))
    # Simulate candidate computed while _last_block_when_available is still None
    cand = await engine.compute()
    assert cand is not None
    runner._candidate = cand
    runner._last_block_when_available = None

    params = PublishRewardsParams(
        version=REWARDS_MESSAGE_VERSION,
        coin_pair=CoinPair("BPRO_REWARDS"),
        epoch=cand.epoch_data.epoch,
        merkle_root=cand.epoch_data.merkle_root,
        cid=cand.epoch_data.cid,
        snapshot_block=cand.epoch_data.snapshot_block,
        distributed_today=cand.epoch_data.distributed_today,
        epoch_data_hash=None,
        oracle_addr=EOA_1,
        last_pub_block=10,
    )
    validator = await runner.create_validator(params)
    assert validator.is_ready is True
    assert validator.last_block_when_available == 60
    validator.validate_params()
    validator.validate_turn()

    # Now mutate minEligibleBalance on-chain -> cached candidate must be invalidated
    rpc.state["minEligibleBalance"] = 9999
    avail, _, _ = await runner.is_oracle_turn(bc_info, EOA_1)
    assert avail is False
    if runner._compute_task is not None:
        await runner._compute_task
    assert runner._candidate is not None
    assert runner._candidate.epoch_data.distributed_today == 0
