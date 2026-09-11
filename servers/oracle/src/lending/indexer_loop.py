import logging

from common.bg_task_executor import BgTaskExecutor
from common.services.blockchain import is_error, run_in_executor

from oracle.src.lending.event_scanner import LendingEventScanner

logger = logging.getLogger(__name__)


def _hex(value):
    return value.hex() if hasattr(value, "hex") else str(value)


class LendingIndexerLoop(BgTaskExecutor):
    def __init__(self, blockchain, repository, settings):
        if settings.LENDING_GET_LOGS_BLOCK_RANGE <= 0:
            raise ValueError("LENDING_GET_LOGS_BLOCK_RANGE must be positive")
        if settings.LENDING_CONFIRMATIONS < 0:
            raise ValueError("LENDING_CONFIRMATIONS cannot be negative")
        self.blockchain = blockchain
        self.repository = repository
        self.settings = settings
        self.scanner = LendingEventScanner(blockchain, settings.LENDING_MANAGER_ADDRESS)
        self.chain_head = None
        self.safe_head = None
        self.last_error = None
        self.reorg_count = 0
        self.last_projected_block = None
        self.last_projected_hash = None
        self.active_vaults = 0
        self._initialized = False
        super().__init__(name="LendingIndexerLoop", main=self.run)

    async def _block(self, number):
        block = await self.blockchain.get_block_by_number(number)
        if is_error(block):
            raise RuntimeError(block.error)
        return block

    async def _ensure_canonical(self, cursor):
        if cursor.last_projected_block < cursor.deployment_block:
            return
        canonical = await self._block(cursor.last_projected_block)
        if _hex(canonical["hash"]).lower() == cursor.last_projected_hash.lower():
            return
        minimum = max(
            cursor.deployment_block,
            cursor.last_projected_block - self.settings.LENDING_REORG_RETENTION_BLOCKS,
        )
        retained = await run_in_executor(
            lambda: self.repository.retained_blocks(minimum)
        )
        for saved in retained:
            block = await self._block(saved.block_number)
            if _hex(block["hash"]).lower() == saved.block_hash.lower():
                await run_in_executor(
                    lambda: self.repository.rollback_to(
                        saved.block_number, saved.block_hash
                    )
                )
                self.reorg_count += 1
                return
        await run_in_executor(self.repository.reset)
        self.reorg_count += 1

    async def run(self):
        try:
            if not self._initialized:
                await run_in_executor(self.repository.initialize)
                self._initialized = True
            head = await self.blockchain.get_last_block()
            if is_error(head):
                raise RuntimeError(head.error)
            self.chain_head = head
            self.safe_head = max(0, head - self.settings.LENDING_CONFIRMATIONS)
            cursor = await run_in_executor(self.repository.cursor)
            await self._ensure_canonical(cursor)
            cursor = await run_in_executor(self.repository.cursor)
            self.last_projected_block = cursor.last_projected_block
            self.last_projected_hash = cursor.last_projected_hash
            start = max(cursor.last_projected_block + 1, cursor.deployment_block)
            if start > self.safe_head:
                self.active_vaults = await run_in_executor(
                    self.repository.active_vault_count
                )
                self.last_error = None
                return self.settings.LENDING_INDEX_INTERVAL
            end = min(
                self.safe_head,
                start + self.settings.LENDING_GET_LOGS_BLOCK_RANGE - 1,
            )
            # Anchor even empty log ranges before reading them. Otherwise a reorg
            # can mix the old projection with a cursor from the replacement branch.
            anchor = await self._block(end)
            anchor_hash = _hex(anchor["hash"]).lower()
            events = await self.scanner.scan(start, end)
            block_numbers = {event["block_number"] for event in events}
            block_numbers.add(end)
            blocks = []
            for number in sorted(block_numbers):
                block = await self._block(number)
                blocks.append(
                    {
                        "chain_id": self.repository.chain_id,
                        "block_number": number,
                        "block_hash": _hex(block["hash"]),
                        "parent_hash": _hex(block["parentHash"]),
                    }
                )
            end_hash = next(
                block["block_hash"] for block in blocks if block["block_number"] == end
            )
            canonical_hashes = {
                block["block_number"]: block["block_hash"].lower()
                for block in blocks
            }
            for event in events:
                if (
                    event["block_hash"].lower()
                    != canonical_hashes[event["block_number"]]
                ):
                    raise RuntimeError("chain reorganized while scanning lending logs")
                event["chain_id"] = self.repository.chain_id
            if end_hash.lower() != anchor_hash:
                raise RuntimeError("chain reorganized while scanning lending logs")
            if cursor.last_projected_block >= cursor.deployment_block:
                previous = await self._block(cursor.last_projected_block)
                if _hex(previous["hash"]).lower() != cursor.last_projected_hash.lower():
                    raise RuntimeError("chain reorganized at lending cursor")
            final = await self._block(end)
            if _hex(final["hash"]).lower() != anchor_hash:
                raise RuntimeError("chain reorganized before lending commit")
            await run_in_executor(
                lambda: self.repository.apply(events, blocks, end, end_hash)
            )
            minimum_retained = max(
                self.repository.deployment_block,
                end - self.settings.LENDING_REORG_RETENTION_BLOCKS,
            )
            await run_in_executor(
                lambda: self.repository.prune_history(minimum_retained)
            )
            self.last_projected_block = end
            self.last_projected_hash = end_hash
            self.active_vaults = await run_in_executor(
                self.repository.active_vault_count
            )
            self.last_error = None
            return 0.1 if end < self.safe_head else self.settings.LENDING_INDEX_INTERVAL
        except Exception as err:
            self.last_error = str(err)
            logger.warning("Lending indexer failed: %s", err)
            if self.repository.is_corruption(err):
                self._initialized = False
                self.last_projected_block = None
                self.last_projected_hash = None
                try:
                    await run_in_executor(self.repository.recover)
                    self._initialized = True
                except Exception as recovery_error:
                    logger.warning("Lending index recovery failed: %s", recovery_error)
            return self.settings.LENDING_INDEX_INTERVAL

    def status(self):
        projected = self.last_projected_block
        lag = (
            None
            if self.safe_head is None or projected is None
            else self.safe_head - projected
        )
        ready = (
            self.last_error is None
            and lag is not None
            and lag <= self.settings.LENDING_MAX_LAG_BLOCKS
        )
        return {
            "status": "ready" if ready else "syncing",
            "chainHead": self.chain_head,
            "safeHead": self.safe_head,
            "lastProjectedBlock": projected,
            "lastProjectedBlockHash": self.last_projected_hash,
            "lagBlocks": lag,
            "activeVaults": self.active_vaults,
            "reorgCount": self.reorg_count,
            "resyncCount": self.repository.resync_count,
            "lastError": self.last_error,
        }
