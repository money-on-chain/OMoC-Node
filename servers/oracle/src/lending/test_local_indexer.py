from pathlib import Path
from types import SimpleNamespace

import pytest
from eth_abi import encode_abi
from hexbytes import HexBytes

from oracle.src.lending.event_scanner import (
    EVENT_TOPIC,
    LendingEventScanner,
)
from oracle.src.lending.indexer_loop import LendingIndexerLoop
from oracle.src.lending.repository import LendingRepository

USER_A = "0x0000000000000000000000000000000000000001"
USER_B = "0x0000000000000000000000000000000000000002"
TP_TOKEN = "0x0000000000000000000000000000000000000010"
MOC_BUCKET = "0x0000000000000000000000000000000000000020"
MANAGER = "0x0000000000000000000000000000000000000030"


def event(user, block, log_index, ac_balance, credit_units, liquidating=False):
    suffix = "%064x" % (block * 100 + log_index)
    return {
        "chain_id": 31,
        "transaction_hash": "0x" + suffix,
        "log_index": log_index,
        "block_number": block,
        "block_hash": "0xblock%d" % block,
        "transaction_index": 0,
        "user": user,
        "tp_token": TP_TOKEN,
        "moc_bucket": MOC_BUCKET,
        "ac_balance": ac_balance,
        "credit_units": credit_units,
        "liquidating": liquidating,
    }


def block(number):
    return {
        "chain_id": 31,
        "block_number": number,
        "block_hash": "0xblock%d" % number,
        "parent_hash": "0xblock%d" % (number - 1),
    }


def test_repository_is_idempotent_orders_exact_risk_and_rolls_back(tmp_path):
    repository = LendingRepository(tmp_path / "lending.db", 31, MANAGER, 10)
    repository.initialize()
    first = event(USER_A, 10, 0, 100, 50)
    more_risky = event(USER_B, 11, 0, 100, 90)

    repository.apply([first, more_risky], [block(10), block(11)], 11, "0xblock11")
    repository.apply([first, more_risky], [block(10), block(11)], 11, "0xblock11")

    assert [vault.user for vault in repository.top_vaults(TP_TOKEN, MOC_BUCKET, 2)] == [
        USER_B,
        USER_A,
    ]
    assert repository.active_vault_count() == 2

    repository.rollback_to(10, "0xblock10")

    assert [vault.user for vault in repository.top_vaults(TP_TOKEN, MOC_BUCKET, 2)] == [
        USER_A
    ]
    assert repository.cursor().last_projected_block == 10


def test_event_scanner_decodes_absolute_vault_state():
    raw = {
        "topics": [
            HexBytes("0x" + EVENT_TOPIC),
            HexBytes("0x" + USER_A[2:].rjust(64, "0")),
            HexBytes("0x" + TP_TOKEN[2:].rjust(64, "0")),
            HexBytes("0x" + MOC_BUCKET[2:].rjust(64, "0")),
        ],
        "data": HexBytes(encode_abi(["uint256", "uint256", "bool"], [100, 90, True])),
        "transactionHash": HexBytes("0x" + "01" * 32),
        "logIndex": 2,
        "blockNumber": 12,
        "blockHash": HexBytes("0x" + "02" * 32),
        "transactionIndex": 1,
    }

    decoded = LendingEventScanner.decode(raw)

    assert decoded["user"] == USER_A
    assert decoded["tp_token"] == TP_TOKEN
    assert decoded["moc_bucket"] == MOC_BUCKET
    assert decoded["ac_balance"] == 100
    assert decoded["credit_units"] == 90
    assert decoded["liquidating"] is True


@pytest.mark.asyncio
async def test_indexer_scans_to_safe_head_and_becomes_ready(tmp_path):
    raw = {
        "topics": [
            HexBytes("0x" + EVENT_TOPIC),
            HexBytes("0x" + USER_A[2:].rjust(64, "0")),
            HexBytes("0x" + TP_TOKEN[2:].rjust(64, "0")),
            HexBytes("0x" + MOC_BUCKET[2:].rjust(64, "0")),
        ],
        "data": HexBytes(encode_abi(["uint256", "uint256", "bool"], [100, 90, False])),
        "transactionHash": HexBytes("0x" + "01" * 32),
        "logIndex": 0,
        "blockNumber": 10,
        "blockHash": HexBytes("0x" + "0a" * 32),
        "transactionIndex": 0,
    }

    class Blockchain:
        async def get_last_block(self):
            return 12

        async def get_logs(self, params):
            assert params["fromBlock"] == 10
            assert params["toBlock"] == 10
            return [raw]

        async def get_block_by_number(self, number):
            return {
                "hash": HexBytes("0x" + format(number, "02x") * 32),
                "parentHash": HexBytes("0x" + format(number - 1, "02x") * 32),
            }

    config = SimpleNamespace(
        LENDING_MANAGER_ADDRESS=MANAGER,
        LENDING_REORG_RETENTION_BLOCKS=100,
        LENDING_CONFIRMATIONS=2,
        LENDING_GET_LOGS_BLOCK_RANGE=100,
        LENDING_INDEX_INTERVAL=5,
        LENDING_MAX_LAG_BLOCKS=0,
    )
    repository = LendingRepository(tmp_path / "indexer.db", 31, MANAGER, 10)
    indexer = LendingIndexerLoop(Blockchain(), repository, config)

    await indexer.run()

    assert indexer.status()["status"] == "ready"
    assert indexer.status()["lastProjectedBlock"] == 10
    assert repository.top_vaults(TP_TOKEN, MOC_BUCKET, 1)[0].user == USER_A


@pytest.mark.parametrize("as_hex", [False, True])
def test_decoder_accepts_web3_log_data(as_hex):
    from web3._utils.method_formatters import log_entry_formatter

    raw = {
        "topics": ["0x" + EVENT_TOPIC] + [
            "0x" + address[2:].rjust(64, "0")
            for address in (USER_A, TP_TOKEN, MOC_BUCKET)
        ],
        "data": "0x" + encode_abi(["uint256", "uint256", "bool"], [100, 90, True]).hex(),
        "transactionHash": "0x" + "01" * 32,
        "logIndex": "0x0", "blockNumber": "0xa",
        "blockHash": "0x" + "02" * 32, "transactionIndex": "0x0",
    }
    formatted = log_entry_formatter(raw)
    if not as_hex:
        formatted["data"] = HexBytes(formatted["data"])
    decoded = LendingEventScanner.decode(formatted)
    assert (decoded["ac_balance"], decoded["credit_units"], decoded["liquidating"]) == (100, 90, True)


def indexer_config():
    return SimpleNamespace(
        LENDING_MANAGER_ADDRESS=MANAGER, LENDING_REORG_RETENTION_BLOCKS=100,
        LENDING_CONFIRMATIONS=0, LENDING_GET_LOGS_BLOCK_RANGE=100,
        LENDING_INDEX_INTERVAL=5, LENDING_MAX_LAG_BLOCKS=0,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("reorg_at", ["logs", "headers", "commit"])
async def test_reorg_during_empty_scan_never_commits_mixed_projection(tmp_path, reorg_at):
    repository = LendingRepository(tmp_path / "reorg.db", 31, MANAGER, 10)
    repository.initialize()
    repository.apply([event(USER_A, 10, 0, 100, 90)], [block(10)], 10, "0xblock10")

    class Chain:
        reorg = False
        end_reads = 0

        async def get_last_block(self):
            return 12

        async def get_logs(self, params):
            if reorg_at == "logs":
                self.reorg = True
            return []

        async def get_block_by_number(self, number):
            if number == 12:
                self.end_reads += 1
                if (reorg_at == "headers" and self.end_reads == 2) or (
                    reorg_at == "commit" and self.end_reads == 3
                ):
                    self.reorg = True
            prefix = "0xnew" if self.reorg else "0xblock"
            return {"hash": prefix + str(number), "parentHash": prefix + str(number - 1)}

    indexer = LendingIndexerLoop(Chain(), repository, indexer_config())
    await indexer.run()
    assert repository.cursor().last_projected_block == 10
    assert indexer.status()["status"] != "ready"
    await indexer.run()
    assert repository.cursor().last_projected_hash == "0xnew12"
    assert repository.active_vault_count() == 0
    assert indexer.status()["status"] == "ready"
    assert indexer.reorg_count == 1


@pytest.mark.asyncio
async def test_short_reorg_restores_risk_and_cursor(tmp_path):
    repository = LendingRepository(tmp_path / "short.db", 31, MANAGER, 10)
    repository.initialize()
    repository.apply([event(USER_A, 10, 0, 100, 90), event(USER_B, 11, 0, 10, 90)],
                     [block(10), block(11)], 11, "0xblock11")

    class Chain:
        async def get_last_block(self): return 12
        async def get_logs(self, params): return []
        async def get_block_by_number(self, number):
            return {"hash": ("0xblock" if number == 10 else "0xnew") + str(number),
                    "parentHash": "0xnew" + str(number - 1)}

    indexer = LendingIndexerLoop(Chain(), repository, indexer_config())
    await indexer.run()
    assert repository.cursor().last_projected_block == 12
    assert [v.user for v in repository.top_vaults(TP_TOKEN, MOC_BUCKET, 10)] == [USER_A]


def test_corrupt_database_is_preserved_and_rebuilt(tmp_path):
    path = tmp_path / "corrupt.db"
    original = b"not a SQLite database"
    path.write_bytes(original)
    repository = LendingRepository(path, 31, MANAGER, 10)
    cursor = repository.initialize()
    assert cursor.last_projected_block == 9
    assert repository.resync_count == 1
    assert Path(repository.last_backup).read_bytes() == original
    assert repository.active_vault_count() == 0


def test_schema_upgrade_backfills_and_preserves_backup(tmp_path):
    path = tmp_path / "schema.db"
    repository = LendingRepository(path, 31, MANAGER, 10)
    repository.initialize()
    repository.apply([event(USER_A, 10, 0, 1, 1)], [block(10)], 10, "0xblock10")
    import sqlite3
    with sqlite3.connect(str(path)) as db:
        db.execute("UPDATE lending_cursor SET schema_version = 99")
    restarted = LendingRepository(path, 31, MANAGER, 10)
    assert restarted.initialize().last_projected_block == 9
    assert restarted.active_vault_count() == 0
    assert Path(restarted.last_backup).exists()


def test_database_lock_is_not_treated_as_corruption(tmp_path, monkeypatch):
    from peewee import OperationalError
    repository = LendingRepository(tmp_path / "locked.db", 31, MANAGER, 10)
    def locked(): raise OperationalError("database is locked")
    monkeypatch.setattr(repository, "_initialize", locked)
    with pytest.raises(OperationalError):
        repository.initialize()
    assert repository.resync_count == 0


def test_heap_restarts_compacts_and_rolls_back_without_stale_entries(tmp_path):
    from unittest.mock import patch
    from oracle.src.lending.models import LendingVault
    path = tmp_path / "heap.db"
    repository = LendingRepository(path, 31, MANAGER, 10)
    repository.initialize()
    repository.apply([event(USER_A, 10, 0, 2**200, 2**200 + 1),
                      event(USER_B, 10, 1, 2**200, 2**200)], [block(10)], 10, "0xblock10")
    for number in range(11, 100):
        repository.apply([event(USER_A, number, 0, 100, number)], [block(number)], number, "0xblock%d" % number)
    heap, current = repository.risk.markets[(TP_TOKEN, MOC_BUCKET)]
    assert len(heap) <= 64
    # Top queries never materialize the SQL table.
    with patch.object(LendingVault, "select", side_effect=AssertionError("unexpected SQL")):
        assert repository.top_vaults(TP_TOKEN, MOC_BUCKET, 1)[0].user == USER_B
    repository.rollback_to(10, "0xblock10")
    assert repository.top_vaults(TP_TOKEN, MOC_BUCKET, 1)[0].user == USER_A
    restarted = LendingRepository(path, 31, MANAGER, 10)
    restarted.initialize()
    assert restarted.top_vaults(TP_TOKEN, MOC_BUCKET, 1)[0].user == USER_A
    # The older repository still binds its own database after another is created.
    other = LendingRepository(tmp_path / "other.db", 31, MANAGER, 10)
    other.initialize()
    assert other.active_vault_count() == 0
    assert repository.active_vault_count() == 2


def test_failed_transaction_does_not_advance_heap_or_cursor(tmp_path):
    repository = LendingRepository(tmp_path / "atomic.db", 31, MANAGER, 10)
    repository.initialize()
    broken = event(USER_B, 10, 1, 1, 100)
    del broken["liquidating"]
    with pytest.raises(KeyError):
        repository.apply([event(USER_A, 10, 0, 100, 90), broken], [block(10)], 10, "0xblock10")
    assert repository.cursor().last_projected_block == 9
    assert repository.top_vaults(TP_TOKEN, MOC_BUCKET, 10) == []
    repository.initialize()
    assert repository.active_vault_count() == 0


@pytest.mark.asyncio
async def test_runtime_corruption_backfills_on_next_iteration(tmp_path):
    path = tmp_path / "runtime.db"
    repository = LendingRepository(path, 31, MANAGER, 10)
    class Chain:
        async def get_last_block(self): return 10
        async def get_logs(self, params): return []
        async def get_block_by_number(self, number):
            return {"hash": "0xblock" + str(number), "parentHash": "0xblock" + str(number - 1)}
    indexer = LendingIndexerLoop(Chain(), repository, indexer_config())
    await indexer.run()
    path.write_bytes(b"corruption after startup")
    await indexer.run()
    assert indexer.status()["status"] != "ready"
    assert repository.resync_count == 1
    await indexer.run()
    assert indexer.status()["status"] == "ready"
    assert repository.cursor().last_projected_block == 10


@pytest.mark.asyncio
async def test_worker_reads_and_writes_are_serialized(tmp_path):
    import asyncio
    from common.services.blockchain import run_in_executor
    repository = LendingRepository(tmp_path / "concurrent.db", 31, MANAGER, 10)
    await run_in_executor(repository.initialize)
    async def write():
        for number in range(10, 30):
            await run_in_executor(lambda: repository.apply(
                [event(USER_A, number, 0, 100, number)], [block(number)], number, "0xblock%d" % number))
    async def read():
        for _ in range(20):
            rows = await run_in_executor(lambda: repository.top_vaults(TP_TOKEN, MOC_BUCKET, 10))
            assert len(rows) <= 1
    await asyncio.gather(write(), read(), read())
    assert repository.top_vaults(TP_TOKEN, MOC_BUCKET, 1)[0].credit_units == "29"
    assert repository.cursor().last_projected_block == 29


def test_heap_matches_exact_order_for_many_vaults():
    import random
    from fractions import Fraction
    from oracle.src.lending.risk_index import RiskIndex
    rng = random.Random(42)
    index = RiskIndex()
    states = {}
    def update(user):
        state = dict(user="0x%040x" % user, tp_token=TP_TOKEN, moc_bucket=MOC_BUCKET,
                     ac_balance=str(rng.randrange(0, 10)), credit_units=str(rng.randrange(0, 10**60)),
                     liquidating=bool(rng.randrange(0, 2)), generation=1)
        states[user] = state
        index.update(state)
    for user in range(5000): update(user)
    for _ in range(2000): update(rng.randrange(5000))
    def order(state):
        ac = int(state["ac_balance"])
        return (not state["liquidating"], ac != 0,
                -Fraction(int(state["credit_units"]), ac or 1) if ac else 0, state["user"])
    expected = sorted(states.values(), key=order)[:100]
    assert [row.user for row in index.top(TP_TOKEN, MOC_BUCKET, 100)] == [row["user"] for row in expected]
    assert index.count() == 5000
