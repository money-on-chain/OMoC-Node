import json
from functools import wraps
import logging
import threading
import uuid
from pathlib import Path

from peewee import DatabaseError, SqliteDatabase

from oracle.src.lending.risk_index import RiskIndex

from oracle.src.lending.models import (
    MODELS,
    LendingBlock,
    LendingCursor,
    LendingEvent,
    LendingVault,
    database_proxy,
)


logger = logging.getLogger(__name__)
# Peewee models share a binding. Serialize bindings and DB/heap mutations;
# close each worker's connection before allowing recovery to move the files.
_repository_lock = threading.RLock()
SCHEMA_VERSION = 1


class RebuildRequired(Exception):
    pass


def serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with _repository_lock, self.db.bind_ctx(MODELS):
            outer = self._depth == 0
            self._depth += 1
            try:
                return method(self, *args, **kwargs)
            finally:
                self._depth -= 1
                if outer and self.path != ":memory:" and not self.db.is_closed():
                    self.db.close()
    return call


class LendingRepository:
    def __init__(self, path, chain_id, manager, deployment_block):
        self.path = str(Path(path).expanduser().resolve()) if str(path) != ":memory:" else str(path)
        self._depth = 0
        self.risk = RiskIndex()
        self.resync_count = 0
        self.last_backup = None
        self.chain_id = int(chain_id)
        self.manager = manager.lower()
        self.deployment_block = deployment_block
        self.db = SqliteDatabase(
            self.path,
            pragmas={"journal_mode": "wal", "foreign_keys": 1},
            check_same_thread=False,
            thread_safe=False,
        )
        database_proxy.initialize(self.db)

    @staticmethod
    def is_corruption(err):
        return isinstance(err, DatabaseError) and any(
            text in str(err).lower()
            for text in ("malformed", "not a database", "file is encrypted")
        )

    @serialized
    def initialize(self):
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        try:
            return self._initialize()
        except (DatabaseError, RebuildRequired) as err:
            if not isinstance(err, RebuildRequired) and not self.is_corruption(err):
                raise
            self._quarantine(str(err))
            return self._initialize()

    def _initialize(self):
        self.db.connect(reuse_if_open=True)
        if self.db.execute_sql("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RebuildRequired("SQLite integrity check failed")
        tables = set(self.db.get_tables())
        if tables:
            if not {model._meta.table_name for model in MODELS}.issubset(tables):
                raise RebuildRequired("Incomplete lending schema")
            for model in MODELS:
                columns = {column.name for column in self.db.get_columns(model._meta.table_name)}
                if not set(model._meta.columns).issubset(columns):
                    raise RebuildRequired("Unsupported lending schema")
            cursors = list(LendingCursor.select())
            if any(c.schema_version != SCHEMA_VERSION or c.chain_id != self.chain_id
                   or c.manager != self.manager or c.deployment_block != self.deployment_block
                   for c in cursors):
                raise RebuildRequired("Lending schema or index configuration changed")
        self.db.create_tables(MODELS)
        cursor, _ = LendingCursor.get_or_create(
            chain_id=self.chain_id,
            manager=self.manager,
            defaults={
                "deployment_block": self.deployment_block,
                "last_projected_block": self.deployment_block - 1,
                "last_projected_hash": "",
                "schema_version": SCHEMA_VERSION,
            },
        )
        self._rebuild_risk()
        return cursor

    def _quarantine(self, reason):
        if not self.db.is_closed():
            self.db.close()
        if self.path != ":memory:":
            backup = self.path + ".backup-" + uuid.uuid4().hex
            for suffix in ("", "-wal", "-shm"):
                source = Path(self.path + suffix)
                if source.exists():
                    source.rename(backup + suffix)
            self.last_backup = backup
        self.risk = RiskIndex()
        self.resync_count += 1
        logger.warning("Rebuilding lending index (%s); backup: %s", reason, self.last_backup)

    @serialized
    def recover(self):
        self._quarantine("corrupt database during indexing")
        return self._initialize()

    def _rebuild_risk(self):
        rebuilt = RiskIndex()
        for vault in LendingVault.select().where(LendingVault.chain_id == self.chain_id).iterator():
            rebuilt.update(self._state(vault))
        self.risk = rebuilt

    @serialized
    def cursor(self):
        return LendingCursor.get(
            LendingCursor.chain_id == self.chain_id,
            LendingCursor.manager == self.manager,
        )

    @staticmethod
    def _vault_key(event):
        return (
            (LendingVault.chain_id == event["chain_id"])
            & (LendingVault.user == event["user"])
            & (LendingVault.tp_token == event["tp_token"])
            & (LendingVault.moc_bucket == event["moc_bucket"])
        )

    @staticmethod
    def _state(vault):
        if vault is None:
            return None
        return {
            "chain_id": vault.chain_id,
            "user": vault.user,
            "tp_token": vault.tp_token,
            "moc_bucket": vault.moc_bucket,
            "ac_balance": vault.ac_balance,
            "credit_units": vault.credit_units,
            "liquidating": vault.liquidating,
            "event_block": vault.event_block,
            "event_block_hash": vault.event_block_hash,
            "transaction_index": vault.transaction_index,
            "log_index": vault.log_index,
            "generation": vault.generation,
        }

    @serialized
    def apply(self, events, blocks, cursor_block, cursor_hash):
        changed = {}
        with self.db.atomic():
            for block in blocks:
                LendingBlock.insert(**block).on_conflict_replace().execute()
            for event in events:
                duplicate = LendingEvent.get_or_none(
                    LendingEvent.chain_id == self.chain_id,
                    LendingEvent.transaction_hash == event["transaction_hash"],
                    LendingEvent.log_index == event["log_index"],
                )
                if duplicate is not None:
                    continue
                current = LendingVault.get_or_none(self._vault_key(event))
                previous = self._state(current)
                state = {
                    "chain_id": self.chain_id,
                    "user": event["user"],
                    "tp_token": event["tp_token"],
                    "moc_bucket": event["moc_bucket"],
                    "ac_balance": str(event["ac_balance"]),
                    "credit_units": str(event["credit_units"]),
                    "liquidating": event["liquidating"],
                    "event_block": event["block_number"],
                    "event_block_hash": event["block_hash"],
                    "transaction_index": event["transaction_index"],
                    "log_index": event["log_index"],
                    "generation": 1 if current is None else current.generation + 1,
                }
                changed[(state["user"], state["tp_token"], state["moc_bucket"])] = state
                LendingEvent.create(
                    chain_id=self.chain_id,
                    transaction_hash=event["transaction_hash"],
                    log_index=event["log_index"],
                    block_number=event["block_number"],
                    block_hash=event["block_hash"],
                    user=event["user"],
                    tp_token=event["tp_token"],
                    moc_bucket=event["moc_bucket"],
                    previous_state=json.dumps(previous) if previous else None,
                    new_state=json.dumps(state),
                )
                LendingVault.insert(**state).on_conflict(
                    conflict_target=[
                        LendingVault.chain_id,
                        LendingVault.user,
                        LendingVault.tp_token,
                        LendingVault.moc_bucket,
                    ],
                    update=state,
                ).execute()
            LendingCursor.update(
                last_projected_block=cursor_block,
                last_projected_hash=cursor_hash,
            ).where(
                LendingCursor.chain_id == self.chain_id,
                LendingCursor.manager == self.manager,
            ).execute()

        for state in changed.values():
            self.risk.update(state)

    @serialized
    def retained_blocks(self, minimum):
        return list(
            LendingBlock.select()
            .where(
                LendingBlock.chain_id == self.chain_id,
                LendingBlock.block_number >= minimum,
            )
            .order_by(LendingBlock.block_number.desc())
        )

    @serialized
    def rollback_to(self, block_number, block_hash):
        with self.db.atomic():
            events = list(
                LendingEvent.select()
                .where(
                    LendingEvent.chain_id == self.chain_id,
                    LendingEvent.block_number > block_number,
                )
                .order_by(
                    LendingEvent.block_number.desc(), LendingEvent.log_index.desc()
                )
            )
            for event in events:
                if event.previous_state is None:
                    LendingVault.delete().where(
                        LendingVault.chain_id == self.chain_id,
                        LendingVault.user == event.user,
                        LendingVault.tp_token == event.tp_token,
                        LendingVault.moc_bucket == event.moc_bucket,
                    ).execute()
                else:
                    state = json.loads(event.previous_state)
                    LendingVault.insert(**state).on_conflict(
                        conflict_target=[
                            LendingVault.chain_id,
                            LendingVault.user,
                            LendingVault.tp_token,
                            LendingVault.moc_bucket,
                        ],
                        update=state,
                    ).execute()
                event.delete_instance()
            LendingBlock.delete().where(
                LendingBlock.chain_id == self.chain_id,
                LendingBlock.block_number > block_number,
            ).execute()
            LendingCursor.update(
                last_projected_block=block_number,
                last_projected_hash=block_hash,
            ).where(
                LendingCursor.chain_id == self.chain_id,
                LendingCursor.manager == self.manager,
            ).execute()

        self._rebuild_risk()

    @serialized
    def reset(self):
        with self.db.atomic():
            for model in (LendingVault, LendingEvent, LendingBlock):
                model.delete().where(model.chain_id == self.chain_id).execute()
            LendingCursor.update(
                last_projected_block=self.deployment_block - 1,
                last_projected_hash="",
            ).where(
                LendingCursor.chain_id == self.chain_id,
                LendingCursor.manager == self.manager,
            ).execute()

        self.risk = RiskIndex()

    @serialized
    def prune_history(self, minimum_block):
        with self.db.atomic():
            LendingEvent.delete().where(
                LendingEvent.chain_id == self.chain_id,
                LendingEvent.block_number < minimum_block,
            ).execute()
            LendingBlock.delete().where(
                LendingBlock.chain_id == self.chain_id,
                LendingBlock.block_number < minimum_block,
            ).execute()

    @serialized
    def top_vaults(self, tp_token, moc_bucket, limit):
        return self.risk.top(tp_token, moc_bucket, limit)

    @serialized
    def active_vault_count(self):
        return self.risk.count()
