"""Async JSON-RPC client for archive node queries (Distributor + ERC20 + eth_getCode)."""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import aiohttp
import eth_abi
from eth_utils import keccak
from web3 import Web3

logger = logging.getLogger(__name__)

HEX_BYTES_RE = re.compile(r"^0x(?:[0-9a-fA-F]{2})*$")


def abi_encode(types: Sequence[str], values: Sequence[Any]) -> bytes:
    if hasattr(eth_abi, "encode"):
        return eth_abi.encode(types, values)
    return eth_abi.encode_abi(types, values)


def abi_decode(types: Sequence[str], data: bytes) -> Tuple[Any, ...]:
    if hasattr(eth_abi, "decode"):
        return tuple(eth_abi.decode(types, data))
    return tuple(eth_abi.decode_abi(types, data))


def event_topic(signature: str) -> str:
    return "0x" + keccak(signature.encode("utf-8")).hex()


def function_selector(signature: str) -> bytes:
    return keccak(signature.encode("utf-8"))[:4]


def to_block_tag(block_number: Union[int, str]) -> str:
    if isinstance(block_number, str):
        return block_number
    return hex(int(block_number))


class ArchiveRpcError(RuntimeError):
    """Raised when an archive RPC call fails or returns invalid data."""


class ArchiveRpcClient:
    """Minimal async JSON-RPC client over aiohttp for archive queries.

    Strict failure semantics: timeouts, RPC errors, or malformed responses
    always raise ArchiveRpcError (never silently default to empty results).
    """

    def __init__(
        self,
        rpc_url: str,
        timeout_secs: float = 30.0,
        retries: int = 3,
        retry_delay_secs: float = 1.0,
    ):
        if not rpc_url:
            raise ValueError("REWARDS_ARCHIVE_RPC_URL must be configured")
        self.rpc_url = rpc_url
        self.timeout_secs = timeout_secs
        self.retries = retries
        self.retry_delay_secs = retry_delay_secs
        self._req_id = 0
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_secs)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    async def rpc_call(self, method: str, params: Sequence[Any]) -> Any:
        self._req_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._req_id,
            "method": method,
            "params": list(params),
        }
        last_err: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            try:
                session = await self._get_session()
                async with session.post(self.rpc_url, json=payload) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise ArchiveRpcError(
                            f"RPC HTTP {resp.status} for {method}: {text[:200]}"
                        )
                    body = await resp.json()
                if not isinstance(body, dict):
                    raise ArchiveRpcError(f"Malformed RPC response for {method}: {body!r}")
                if "error" in body and body["error"] is not None:
                    raise ArchiveRpcError(f"RPC error for {method}: {body['error']!r}")
                if "result" not in body:
                    raise ArchiveRpcError(f"Missing result in RPC response for {method}")
                return body["result"]
            except (asyncio.CancelledError,):
                raise
            except Exception as err:
                last_err = err
                if attempt < self.retries:
                    await asyncio.sleep(self.retry_delay_secs * attempt)
        raise ArchiveRpcError(f"RPC {method} failed after {self.retries} attempts: {last_err}")

    async def get_chain_id(self) -> int:
        res = await self.rpc_call("eth_chainId", [])
        return int(res, 16)

    async def get_block_number(self) -> int:
        res = await self.rpc_call("eth_blockNumber", [])
        return int(res, 16)

    async def get_block(self, block_number: int) -> Dict[str, Any]:
        res = await self.rpc_call("eth_getBlockByNumber", [to_block_tag(block_number), False])
        if not isinstance(res, dict) or not res.get("hash") or res.get("timestamp") is None:
            raise ArchiveRpcError(f"Block {block_number} not found or incomplete: {res!r}")
        return {
            "number": int(res["number"], 16),
            "hash": str(res["hash"]).lower(),
            "timestamp": int(res["timestamp"], 16),
        }

    async def get_code(self, address: str, block_number: int) -> str:
        checksum = Web3.toChecksumAddress(address)
        res = await self.rpc_call("eth_getCode", [checksum, to_block_tag(block_number)])
        if not isinstance(res, str) or not HEX_BYTES_RE.match(res):
            raise ArchiveRpcError(
                f"Invalid historical eth_getCode response for {address} at {block_number}: {res!r}"
            )
        return res

    async def get_logs(
        self,
        address: str,
        topics: Sequence[Optional[str]],
        from_block: int,
        to_block: int,
    ) -> List[Dict[str, Any]]:
        params = {
            "address": Web3.toChecksumAddress(address),
            "topics": list(topics),
            "fromBlock": to_block_tag(from_block),
            "toBlock": to_block_tag(to_block),
        }
        res = await self.rpc_call("eth_getLogs", [params])
        if not isinstance(res, list):
            raise ArchiveRpcError(f"Invalid eth_getLogs response: {res!r}")
        return res

    async def eth_call(
        self,
        address: str,
        signature: str,
        output_types: Sequence[str],
        arg_types: Sequence[str] = (),
        arg_values: Sequence[Any] = (),
        block_number: Union[int, str] = "latest",
    ) -> Tuple[Any, ...]:
        calldata = function_selector(signature)
        if arg_types:
            calldata += abi_encode(arg_types, arg_values)
        params = [
            {
                "to": Web3.toChecksumAddress(address),
                "data": "0x" + calldata.hex(),
            },
            to_block_tag(block_number),
        ]
        res = await self.rpc_call("eth_call", params)
        if not isinstance(res, str) or not HEX_BYTES_RE.match(res):
            raise ArchiveRpcError(f"Invalid eth_call result for {signature}: {res!r}")
        raw = bytes.fromhex(res[2:])
        if not raw:
            raise ArchiveRpcError(f"Empty eth_call result for {signature} at {address}")
        return abi_decode(output_types, raw)

    async def read_distributor_state(
        self, distributor: str, block_number: Union[int, str] = "latest"
    ) -> Dict[str, Any]:
        """Read all Distributor state needed for snapshot/sync at a pinned block."""
        calls = [
            self.eth_call(distributor, "currentEpoch()", ["uint256"], block_number=block_number),
            self.eth_call(distributor, "currentRoot()", ["bytes32"], block_number=block_number),
            self.eth_call(distributor, "currentIpfsCid()", ["string"], block_number=block_number),
            self.eth_call(
                distributor, "currentSnapshotBlock()", ["uint256"], block_number=block_number
            ),
            self.eth_call(distributor, "nextEpochTime()", ["uint256"], block_number=block_number),
            self.eth_call(distributor, "canPublishEpoch()", ["bool"], block_number=block_number),
            self.eth_call(
                distributor, "minEligibleBalance()", ["uint256"], block_number=block_number
            ),
            self.eth_call(
                distributor,
                "totalDistributedHistorical()",
                ["uint256"],
                block_number=block_number,
            ),
            self.eth_call(
                distributor, "initializationBlock()", ["uint256"], block_number=block_number
            ),
            self.eth_call(distributor, "holdingsToken()", ["address"], block_number=block_number),
            self.eth_call(
                distributor, "openedPeriodCount()", ["uint256"], block_number=block_number
            ),
            self.eth_call(distributor, "operator()", ["address"], block_number=block_number),
            self.eth_call(distributor, "paused()", ["bool"], block_number=block_number),
            self.eth_call(
                distributor, "distributionStartTime()", ["uint256"], block_number=block_number
            ),
            self.eth_call(distributor, "epochInterval()", ["uint256"], block_number=block_number),
        ]
        results = await asyncio.gather(*calls)
        state = {
            "currentEpoch": int(results[0][0]),
            "currentRoot": "0x" + bytes(results[1][0]).hex(),
            "currentIpfsCid": str(results[2][0]),
            "currentSnapshotBlock": int(results[3][0]),
            "nextEpochTime": int(results[4][0]),
            "canPublishEpoch": bool(results[5][0]),
            "minEligibleBalance": int(results[6][0]),
            "totalDistributedHistorical": int(results[7][0]),
            "initializationBlock": int(results[8][0]),
            "holdingsToken": Web3.toChecksumAddress(results[9][0]).lower(),
            "openedPeriodCount": int(results[10][0]),
            "operator": Web3.toChecksumAddress(results[11][0]).lower(),
            "paused": bool(results[12][0]),
            "distributionStartTime": int(results[13][0]),
            "epochInterval": int(results[14][0]),
        }
        return state

    async def read_next_epoch_budget(
        self, distributor: str, block_number: Union[int, str] = "latest"
    ) -> int:
        res = await self.eth_call(
            distributor, "nextEpochBudget()", ["uint256"], block_number=block_number
        )
        return int(res[0])

    async def read_migration_state(
        self, distributor: str, block_number: Union[int, str] = "latest"
    ) -> Tuple[int, int, bool]:
        init_res, total_res, fin_res = await asyncio.gather(
            self.eth_call(
                distributor, "initializationBlock()", ["uint256"], block_number=block_number
            ),
            self.eth_call(distributor, "totalMigrated()", ["uint256"], block_number=block_number),
            self.eth_call(distributor, "migrationFinished()", ["bool"], block_number=block_number),
        )
        return int(init_res[0]), int(total_res[0]), bool(fin_res[0])
