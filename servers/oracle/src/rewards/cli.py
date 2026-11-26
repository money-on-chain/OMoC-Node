"""Standalone single-operator CLI for scheduled rewards epoch cycles (e.g. AWS ECS Fargate).

Reuses the exact same `RewardsEngine`, `StandardMerkleTree`, canonical JSON, and
CIDv1 UnixFS engine as `OMoC-Node`'s multi-oracle `RewardsRunner`, so epochs
published in Stage 1 are already byte-for-byte compatible with Stage 2.

Usage:
    python -m oracle.src.rewards.cli [--dry-run] [--max-epochs 30] [--skip-ipfs]
"""

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from eth_account import Account
from web3 import Web3

from oracle.src.rewards.engine import RewardsEngine
from oracle.src.rewards.ipfs_pinner import (
    IpfsPinner,
    PinataPinner,
    fetch_from_ipfs_gateways,
)
from oracle.src.rewards.rpc_client import ArchiveRpcClient
from oracle.src.rewards.snapshot_block import verify_snapshot_block_hash
from oracle.src.rewards.state_store import RewardsStateStore
from oracle.src.rewards.types import CandidateResult, EpochData

logger = logging.getLogger(__name__)

DISTRIBUTOR_CLI_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "newEpoch", "type": "uint256"},
            {"internalType": "bytes32", "name": "newRoot", "type": "bytes32"},
            {"internalType": "string", "name": "newCid", "type": "string"},
            {"internalType": "uint256", "name": "snapshotBlock", "type": "uint256"},
            {"internalType": "uint256", "name": "distributedToday", "type": "uint256"},
        ],
        "name": "publishEpoch",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "startDistributionPeriod",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


@dataclass(frozen=True)
class CliConfig:
    rpc_url: str
    distributor_address: str
    state_dir: str
    operator_private_key: str = ""
    task_private_key: str = ""
    chain_id: Optional[int] = None
    snapshot_confirmations: int = 12
    log_chunk_size: int = 1000
    code_concurrency: int = 20
    token_start_block: int = 0
    ipfs_gateways: Tuple[str, ...] = ()
    ipfs_api_url: str = ""
    pinata_jwt: str = ""
    auto_start_period: bool = False
    min_gas: int = 0
    tx_timeout_secs: int = 180
    dry_run: bool = False
    skip_ipfs: bool = False
    max_epochs: int = 30


@dataclass(frozen=True)
class CycleResult:
    status: str  # "not_due" | "dry_run" | "published"
    published_epochs: List[int]
    last_epoch_data: Optional[EpochData] = None


def _parse_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def load_config_from_env(args: argparse.Namespace) -> CliConfig:
    rpc_url = (
        os.getenv("REWARDS_ARCHIVE_RPC_URL") or os.getenv("RPC_URL") or ""
    ).strip()
    distributor = (os.getenv("DISTRIBUTOR_ADDRESS") or "").strip()
    state_dir = (os.getenv("REWARDS_STATE_DIR") or "/tmp/rewards-state").strip()
    operator_key = (os.getenv("OPERATOR_PRIVATE_KEY") or "").strip()
    task_key = (os.getenv("TASK_PRIVATE_KEY") or "").strip()

    chain_id_raw = (os.getenv("CHAIN_ID") or "").strip()
    chain_id = int(chain_id_raw) if chain_id_raw else None

    gateways = tuple(
        gw.strip()
        for gw in (os.getenv("REWARDS_IPFS_GATEWAYS") or "").split(",")
        if gw.strip()
    )

    confirmations = (
        args.confirmations
        if args.confirmations is not None
        else int(os.getenv("REWARDS_SNAPSHOT_CONFIRMATIONS", "12"))
    )
    auto_start_period = args.auto_start_period or _parse_bool_env(
        "AUTO_START_PERIOD", False
    )

    if not rpc_url:
        raise ValueError("REWARDS_ARCHIVE_RPC_URL (or RPC_URL) must be set")
    if not distributor:
        raise ValueError("DISTRIBUTOR_ADDRESS must be set")
    if not args.dry_run and not operator_key:
        raise ValueError("OPERATOR_PRIVATE_KEY must be set (unless --dry-run is used)")
    if auto_start_period and not args.dry_run and not task_key:
        raise ValueError("TASK_PRIVATE_KEY must be set when AUTO_START_PERIOD is enabled")

    return CliConfig(
        rpc_url=rpc_url,
        distributor_address=distributor,
        state_dir=state_dir,
        operator_private_key=operator_key,
        task_private_key=task_key,
        chain_id=chain_id,
        snapshot_confirmations=confirmations,
        log_chunk_size=int(os.getenv("REWARDS_LOG_CHUNK_SIZE", "1000")),
        code_concurrency=int(os.getenv("REWARDS_CODE_CONCURRENCY", "20")),
        token_start_block=int(os.getenv("REWARDS_TOKEN_START_BLOCK", "0")),
        ipfs_gateways=gateways,
        ipfs_api_url=(os.getenv("REWARDS_IPFS_API_URL") or "").strip(),
        pinata_jwt=(os.getenv("PINATA_JWT") or "").strip(),
        auto_start_period=auto_start_period,
        min_gas=int(os.getenv("REWARDS_PUBLISHER_MIN_GAS", "0")),
        tx_timeout_secs=int(os.getenv("REWARDS_TX_TIMEOUT_SECS", "180")),
        dry_run=bool(args.dry_run),
        skip_ipfs=bool(args.skip_ipfs),
        max_epochs=int(args.max_epochs),
    )


class DistributorTxSender:
    """Signs and submits Distributor transactions via Web3 HTTPProvider."""

    def __init__(
        self,
        rpc_url: str,
        distributor_address: str,
        min_gas: int = 0,
        tx_timeout_secs: int = 180,
    ):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.distributor = Web3.toChecksumAddress(distributor_address)
        self.contract = self.w3.eth.contract(
            address=self.distributor, abi=DISTRIBUTOR_CLI_ABI
        )
        self.min_gas = int(min_gas)
        self.tx_timeout_secs = int(tx_timeout_secs)

    def _send_contract_call(self, fn_call, private_key: str) -> str:
        account = Account.from_key(private_key)
        sender = Web3.toChecksumAddress(account.address)

        get_nonce = getattr(
            self.w3.eth, "get_transaction_count", None
        ) or getattr(self.w3.eth, "getTransactionCount")
        nonce = get_nonce(sender, "pending")

        gas_price = getattr(self.w3.eth, "gas_price", None)
        if gas_price is None:
            gas_price = self.w3.eth.gasPrice

        chain_id = getattr(self.w3.eth, "chain_id", None)
        if chain_id is None:
            chain_id = self.w3.eth.chainId

        tx_params = {
            "from": sender,
            "nonce": nonce,
            "gasPrice": gas_price,
            "chainId": int(chain_id),
        }
        estimated = fn_call.estimateGas({"from": sender}) if hasattr(fn_call, "estimateGas") else fn_call.estimate_gas({"from": sender})
        gas_limit = max(int(estimated * 1.2), self.min_gas)
        tx_params["gas"] = gas_limit

        build_tx = getattr(fn_call, "build_transaction", None) or getattr(
            fn_call, "buildTransaction"
        )
        tx = build_tx(tx_params)

        signed = Account.sign_transaction(tx, private_key)
        raw_tx = getattr(signed, "rawTransaction", None) or getattr(
            signed, "raw_transaction"
        )

        send_raw = getattr(self.w3.eth, "send_raw_transaction", None) or getattr(
            self.w3.eth, "sendRawTransaction"
        )
        tx_hash = send_raw(raw_tx)

        wait_receipt = getattr(
            self.w3.eth, "wait_for_transaction_receipt", None
        ) or getattr(self.w3.eth, "waitForTransactionReceipt")
        receipt = wait_receipt(tx_hash, timeout=self.tx_timeout_secs)
        status = receipt["status"] if isinstance(receipt, dict) else receipt.status
        if int(status) != 1:
            raise RuntimeError(f"Transaction {tx_hash.hex()} reverted on-chain")
        return tx_hash.hex()

    async def publish_epoch(self, epoch_data: EpochData, operator_private_key: str) -> str:
        root_hex = (
            epoch_data.merkle_root[2:]
            if epoch_data.merkle_root.startswith("0x")
            else epoch_data.merkle_root
        )
        fn_call = self.contract.functions.publishEpoch(
            int(epoch_data.epoch),
            bytes.fromhex(root_hex),
            epoch_data.cid,
            int(epoch_data.snapshot_block),
            int(epoch_data.distributed_today),
        )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._send_contract_call, fn_call, operator_private_key
        )

    async def start_distribution_period(self, task_private_key: str) -> str:
        fn_call = self.contract.functions.startDistributionPeriod()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._send_contract_call, fn_call, task_private_key
        )


def _build_pinners(config: CliConfig) -> List[object]:
    pinners: List[object] = []
    if config.ipfs_api_url:
        pinners.append(IpfsPinner(config.ipfs_api_url))
    if config.pinata_jwt:
        pinners.append(PinataPinner(config.pinata_jwt))
    return pinners


async def _verify_on_gateways(
    cid: str,
    gateways: Sequence[str],
    retries: int = 4,
    delay_secs: float = 2.5,
) -> None:
    if not gateways:
        return
    for attempt in range(1, retries + 1):
        data = await fetch_from_ipfs_gateways(cid, gateways)
        if data is not None:
            return
        if attempt < retries:
            await asyncio.sleep(delay_secs)
    raise RuntimeError(f"Uploaded CID {cid} could not be verified via configured IPFS gateways")


async def _revalidate_candidate_before_publish(
    rpc,
    distributor: str,
    candidate: CandidateResult,
    operator_addr: Optional[str],
) -> None:
    """Re-verify on-chain Distributor state and snapshot block hash right before publishEpoch."""
    ed = candidate.epoch_data
    state = await rpc.read_distributor_state(distributor)
    if state["paused"] or not state["canPublishEpoch"]:
        raise RuntimeError(
            f"Distributor is no longer ready to publish epoch {ed.epoch} "
            f"(paused={state['paused']}, canPublishEpoch={state['canPublishEpoch']})"
        )
    if operator_addr is not None and state["operator"].lower() != operator_addr:
        raise RuntimeError(
            f"OPERATOR_PRIVATE_KEY address {operator_addr} does not match "
            f"Distributor.operator() {state['operator'].lower()}"
        )
    if state["currentEpoch"] + 1 != ed.epoch:
        raise RuntimeError(
            f"Target epoch changed during pinning (currentEpoch={state['currentEpoch']}, "
            f"candidate={ed.epoch})"
        )
    if (
        candidate.min_eligible_balance is not None
        and state["minEligibleBalance"] != candidate.min_eligible_balance
    ):
        raise RuntimeError(
            f"minEligibleBalance changed during pinning "
            f"({candidate.min_eligible_balance} -> {state['minEligibleBalance']}); aborting publish"
        )
    if (
        candidate.total_distributed_historical is not None
        and state["totalDistributedHistorical"] != candidate.total_distributed_historical
    ):
        raise RuntimeError(
            f"totalDistributedHistorical changed during pinning "
            f"({candidate.total_distributed_historical} -> "
            f"{state['totalDistributedHistorical']}); aborting publish"
        )
    if not await verify_snapshot_block_hash(
        rpc, ed.snapshot_block, candidate.snapshot_block_hash
    ):
        raise RuntimeError(
            f"Snapshot block {ed.snapshot_block} hash changed during pinning (reorg); "
            "aborting publish"
        )


async def run_epoch_cycle(
    config: CliConfig,
    rpc_client=None,
    tx_sender=None,
    pinners: Optional[Sequence[object]] = None,
) -> CycleResult:
    """Run an idempotent epoch cycle (sync -> optional period -> compute -> pin -> publish)."""
    owns_rpc = rpc_client is None
    rpc = rpc_client if rpc_client is not None else ArchiveRpcClient(config.rpc_url)
    store = RewardsStateStore(config.state_dir)
    engine = RewardsEngine(
        rpc_client=rpc,
        distributor_address=config.distributor_address,
        state_store=store,
        snapshot_confirmations=config.snapshot_confirmations,
        log_chunk_size=config.log_chunk_size,
        code_concurrency=config.code_concurrency,
        ipfs_gateways=config.ipfs_gateways,
        token_start_block=config.token_start_block,
    )
    sender = (
        tx_sender
        if tx_sender is not None
        else (
            None
            if config.dry_run
            else DistributorTxSender(
                rpc_url=config.rpc_url,
                distributor_address=config.distributor_address,
                min_gas=config.min_gas,
                tx_timeout_secs=config.tx_timeout_secs,
            )
        )
    )
    active_pinners = list(pinners) if pinners is not None else _build_pinners(config)

    try:
        if config.chain_id is not None:
            actual_chain_id = await rpc.get_chain_id()
            if actual_chain_id != config.chain_id:
                raise RuntimeError(
                    f"RPC chain_id {actual_chain_id} disagrees with CHAIN_ID={config.chain_id}"
                )

        if not config.dry_run and not config.skip_ipfs and not active_pinners:
            raise ValueError(
                "No IPFS pinner configured (set REWARDS_IPFS_API_URL or PINATA_JWT, "
                "or pass --skip-ipfs explicitly)"
            )

        operator_addr: Optional[str] = None
        if not config.dry_run:
            operator_addr = Account.from_key(config.operator_private_key).address.lower()

        sync_res = await engine.sync()
        logger.info(
            "Sync complete: source=%s epoch=%s snapshotBlock=%s",
            sync_res.source,
            sync_res.epoch,
            sync_res.snapshot_block,
        )

        published_epochs: List[int] = []
        last_epoch_data: Optional[EpochData] = None

        for _ in range(max(1, config.max_epochs)):
            if config.auto_start_period and not config.dry_run and sender is not None:
                (can_start,) = await rpc.eth_call(
                    engine.distributor, "canStartDistributionPeriod()", ["bool"]
                )
                if bool(can_start):
                    tx_hash = await sender.start_distribution_period(config.task_private_key)
                    logger.info("Started new distribution period: tx=%s", tx_hash)

            candidate = await engine.compute()
            if candidate is None:
                if not published_epochs:
                    logger.info("No epoch ready to publish yet; exiting cleanly.")
                    return CycleResult(status="not_due", published_epochs=[])
                logger.info(
                    "Caught up after publishing %d epoch(s): %s",
                    len(published_epochs),
                    published_epochs,
                )
                break

            ed = candidate.epoch_data
            logger.info(
                "Prepared epoch=%s snapshotBlock=%s root=%s cid=%s distributedToday=%s",
                ed.epoch,
                ed.snapshot_block,
                ed.merkle_root,
                ed.cid,
                ed.distributed_today,
            )

            if config.dry_run:
                return CycleResult(
                    status="dry_run",
                    published_epochs=[],
                    last_epoch_data=ed,
                )

            # Verify operator role before pinning/publishing
            state = await rpc.read_distributor_state(engine.distributor)
            if operator_addr is not None and state["operator"].lower() != operator_addr:
                raise RuntimeError(
                    f"OPERATOR_PRIVATE_KEY address {operator_addr} does not match "
                    f"Distributor.operator() {state['operator'].lower()}"
                )

            if not config.skip_ipfs:
                filename = f"epoch_{ed.epoch}.json"
                for pinner in active_pinners:
                    pinned_cid = await pinner.pin_bytes(candidate.raw_bytes, ed.cid, filename)
                    logger.info(
                        "Pinned %s via %s: cid=%s",
                        filename,
                        type(pinner).__name__,
                        pinned_cid,
                    )
                await _verify_on_gateways(ed.cid, config.ipfs_gateways)

            await _revalidate_candidate_before_publish(
                rpc, engine.distributor, candidate, operator_addr
            )

            tx_hash = await sender.publish_epoch(ed, config.operator_private_key)
            logger.info("Published epoch %s on-chain: tx=%s", ed.epoch, tx_hash)

            store.save_published(ed.epoch, candidate.raw_bytes)
            engine._last_synced_epoch = ed.epoch
            published_epochs.append(ed.epoch)
            last_epoch_data = ed

        return CycleResult(
            status="published" if published_epochs else "not_due",
            published_epochs=published_epochs,
            last_epoch_data=last_epoch_data,
        )
    finally:
        if owns_rpc and hasattr(rpc, "close"):
            await rpc.close()


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a single-operator Rewards Program epoch cycle (Python engine)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Sync and compute the next epoch candidate without pinning or publishing on-chain.",
    )
    parser.add_argument(
        "--max-epochs",
        type=int,
        default=30,
        help="Maximum overdue epochs to publish in a single run (default: 30).",
    )
    parser.add_argument(
        "--confirmations",
        type=int,
        default=None,
        help="Override REWARDS_SNAPSHOT_CONFIRMATIONS.",
    )
    parser.add_argument(
        "--skip-ipfs",
        action="store_true",
        help="Publish on-chain without pinning to Kubo/Pinata (testing only).",
    )
    parser.add_argument(
        "--auto-start-period",
        action="store_true",
        help="Call startDistributionPeriod() with TASK_PRIVATE_KEY when due.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = _parse_args(argv)
    config = load_config_from_env(args)
    result = asyncio.run(run_epoch_cycle(config))
    logger.info(
        "Rewards CLI finished: status=%s published_epochs=%s",
        result.status,
        result.published_epochs,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
