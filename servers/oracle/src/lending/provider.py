import json
import logging

from common import settings
from common.services.blockchain import is_error, run_in_executor
from web3 import Web3

from oracle.src.oracle_publish_message import PoolLiquidations

logger = logging.getLogger(__name__)


class LendingMarket:
    def __init__(self, tp_token, moc_bucket):
        self.tp_token = Web3.toChecksumAddress(tp_token)
        self.moc_bucket = Web3.toChecksumAddress(moc_bucket)


class LendingLiquidationProvider:
    def __init__(
        self,
        service,
        repository=None,
        indexer=None,
        markets=None,
        multicall_addr=None,
    ):
        self.service = service
        self.repository = repository
        self.indexer = indexer
        self.markets = markets if markets is not None else self._configured_markets()
        self.multicall_addr = multicall_addr

    @staticmethod
    def _configured_markets():
        try:
            raw = json.loads(settings.LENDING_LIQUIDATION_MARKETS)
            if not isinstance(raw, list):
                raise ValueError("expected a JSON array")
            return [
                LendingMarket(item["tpToken"], item["mocBucket"])
                for item in raw
            ]
        except (KeyError, TypeError, ValueError) as err:
            logger.error("Invalid LENDING_LIQUIDATION_MARKETS: %s", err)
            return []

    def is_ready(self):
        if self.repository is None or self.indexer is None or not self.markets:
            return False
        return self.indexer.status()["status"] == "ready"

    @staticmethod
    def _pool_id_hex(pool_id):
        value = pool_id.hex() if hasattr(pool_id, "hex") else str(pool_id)
        return value if value.startswith("0x") else "0x" + value

    async def _get_enabled_pool(self, market):
        pool_id = await self.service.get_liquidation_pool_id(
            market.tp_token, market.moc_bucket
        )
        if is_error(pool_id):
            return None, None
        pool = await self.service.get_liquidation_pool(pool_id)
        if is_error(pool) or len(pool) != 3 or not pool[2]:
            return None, None
        if (
            pool[0].lower() != market.tp_token.lower()
            or pool[1].lower() != market.moc_bucket.lower()
        ):
            return None, None
        return self._pool_id_hex(pool_id), pool

    async def build_liquidations(self, limit):
        if not self.is_ready() or limit <= 0:
            return []
        selected = []
        total = 0
        seen = set()
        for market in self.markets:
            if total >= limit:
                break
            pool_id, _ = await self._get_enabled_pool(market)
            if pool_id is None:
                continue
            vaults = await run_in_executor(
                lambda market=market: self.repository.top_vaults(
                    market.tp_token,
                    market.moc_bucket,
                    settings.LENDING_TOP_K_PER_MARKET,
                )
            )
            batch_size = max(1, limit - total)
            for offset in range(0, len(vaults), batch_size):
                if total >= limit:
                    break
                chunk = []
                for vault in vaults[offset : offset + batch_size]:
                    key = (pool_id.lower(), vault.user.lower())
                    if key not in seen:
                        seen.add(key)
                        chunk.append(vault)
                if not chunk:
                    continue
                results = await self.service.simulate_liquidations(
                    [
                        (vault.user, market.tp_token, market.moc_bucket)
                        for vault in chunk
                    ],
                    self.multicall_addr,
                )
                if is_error(results) or len(results) != len(chunk):
                    continue
                for vault, available in zip(chunk, results):
                    if available:
                        selected.append(
                            (
                                pool_id,
                                vault.user,
                                market.tp_token,
                                market.moc_bucket,
                            )
                        )
                        total += 1

        if not selected:
            return []
        final_results = await self.service.simulate_liquidations(
            [(user, tp_token, moc_bucket) for _, user, tp_token, moc_bucket in selected],
            self.multicall_addr,
        )
        if is_error(final_results) or len(final_results) != len(selected):
            return []

        pools = {}
        for (pool_id, user, _, _), available in zip(selected, final_results):
            if available:
                pools.setdefault(pool_id, []).append(user)
        return [
            PoolLiquidations(pool_id, users)
            for pool_id, users in pools.items()
            if users
        ]

    async def risk_vaults(self, tp_token, moc_bucket, limit):
        if self.repository is None:
            return []
        return await run_in_executor(
            lambda: self.repository.top_vaults(tp_token, moc_bucket, limit)
        )
