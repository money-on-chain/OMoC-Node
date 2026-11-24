"""Canonical minimal epoch JSON builder, serializer, and parser.

Produces byte-for-byte identical output to
`rewards-program/scripts/snapshot/epoch-json.ts` + `JSON.stringify(json, null, 2)`.
"""

import json
from typing import Iterable, List, Optional, Sequence, Tuple

from oracle.src.rewards.merkle import StandardMerkleTree, ZERO_ROOT
from oracle.src.rewards.types import BalanceEntry, EpochJson, HolderEntry


def build_epoch_json(
    epoch: int,
    snapshot_block: int,
    holders: Sequence[Tuple[str, int]],
    balances: Sequence[Tuple[str, int]],
    registered_contracts: Iterable[str],
    expected_total: int,
) -> EpochJson:
    """Build a canonical EpochJson with deterministic sorting and Merkle proofs."""
    norm_holders = sorted(
        [(addr.lower(), int(amount)) for addr, amount in holders],
        key=lambda item: item[0],
    )
    if len({addr for addr, _ in norm_holders}) != len(norm_holders):
        raise ValueError("Duplicate holder list")

    allocated_total = sum(amount for _, amount in norm_holders)
    if allocated_total != int(expected_total):
        raise ValueError(
            f"Merkle allocations total {allocated_total} does not match "
            f"declared historical total {expected_total}"
        )

    tree: Optional[StandardMerkleTree] = (
        StandardMerkleTree(norm_holders) if norm_holders else None
    )
    merkle_root = tree.root if tree is not None else ZERO_ROOT

    holder_entries: List[HolderEntry] = [
        HolderEntry(
            address=addr,
            cumulative_amount=amount,
            proof=tree.get_proof(idx) if tree is not None else [],
        )
        for idx, (addr, amount) in enumerate(norm_holders)
    ]

    norm_balances = sorted(
        [(addr.lower(), int(bal)) for addr, bal in balances],
        key=lambda item: item[0],
    )
    if len({addr for addr, _ in norm_balances}) != len(norm_balances):
        raise ValueError("Duplicate balance list")

    balance_entries: List[BalanceEntry] = [
        BalanceEntry(address=addr, balance=bal) for addr, bal in norm_balances
    ]

    norm_registered = sorted({addr.lower() for addr in registered_contracts})

    return EpochJson(
        epoch=int(epoch),
        snapshot_block=int(snapshot_block),
        merkle_root=merkle_root,
        holders=holder_entries,
        balances=balance_entries,
        registered_contracts=norm_registered,
    )


def serialize_epoch_json(epoch_json: EpochJson) -> bytes:
    """Serialize EpochJson to UTF-8 bytes identical to JS JSON.stringify(payload, null, 2)."""
    payload = {
        "epoch": int(epoch_json.epoch),
        "snapshotBlock": int(epoch_json.snapshot_block),
        "merkleRoot": epoch_json.merkle_root,
        "holders": [
            {
                "address": h.address.lower(),
                "cumulativeAmount": str(int(h.cumulative_amount)),
                "proof": list(h.proof),
            }
            for h in epoch_json.holders
        ],
        "balances": [
            {
                "address": b.address.lower(),
                "balance": str(int(b.balance)),
            }
            for b in epoch_json.balances
        ],
        "registeredContracts": [addr.lower() for addr in epoch_json.registered_contracts],
    }
    return json.dumps(payload, indent=2, separators=(",", ": "), ensure_ascii=False).encode("utf-8")


def parse_epoch_json(raw_bytes: bytes) -> EpochJson:
    """Parse and validate an EpochJson from raw UTF-8 JSON bytes."""
    data = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Epoch JSON root must be an object")

    for required in ("epoch", "snapshotBlock", "merkleRoot", "holders", "balances", "registeredContracts"):
        if required not in data:
            raise ValueError(f"Missing required field {required!r} in epoch JSON")

    if not isinstance(data["holders"], list):
        raise ValueError("Field 'holders' must be a list")
    if not isinstance(data["balances"], list):
        raise ValueError("Field 'balances' must be a list")
    if not isinstance(data["registeredContracts"], list):
        raise ValueError("Field 'registeredContracts' must be a list")

    holders: List[HolderEntry] = []
    seen_holders = set()
    for item in data["holders"]:
        addr = str(item["address"]).lower()
        if addr in seen_holders:
            raise ValueError(f"Duplicate holder address: {addr}")
        seen_holders.add(addr)
        amount = int(item["cumulativeAmount"])
        if amount < 0:
            raise ValueError(f"Negative cumulativeAmount for {addr}")
        proof = [str(p) for p in item.get("proof", [])]
        holders.append(HolderEntry(address=addr, cumulative_amount=amount, proof=proof))

    balances: List[BalanceEntry] = []
    seen_balances = set()
    for item in data["balances"]:
        addr = str(item["address"]).lower()
        if addr in seen_balances:
            raise ValueError(f"Duplicate balance address: {addr}")
        seen_balances.add(addr)
        bal = int(item["balance"])
        if bal < 0:
            raise ValueError(f"Negative balance for {addr}")
        balances.append(BalanceEntry(address=addr, balance=bal))

    registered = [str(addr).lower() for addr in data["registeredContracts"]]

    return EpochJson(
        epoch=int(data["epoch"]),
        snapshot_block=int(data["snapshotBlock"]),
        merkle_root=str(data["merkleRoot"]),
        holders=holders,
        balances=balances,
        registered_contracts=registered,
    )


def verify_epoch_json_merkle(epoch_json: EpochJson, expected_root: str) -> None:
    """Recompute the Merkle root from holders and assert exact match with expected_root."""
    if not epoch_json.holders:
        if expected_root.lower() != ZERO_ROOT:
            raise ValueError("Invalid empty Merkle tree")
        return
    entries = [(h.address.lower(), int(h.cumulative_amount)) for h in epoch_json.holders]
    if len({addr for addr, _ in entries}) != len(entries):
        raise ValueError("JSON contains duplicate holders")
    tree = StandardMerkleTree(entries)
    if tree.root.lower() != expected_root.lower():
        raise ValueError(
            f"JSON integrity check failed. Expected root: {expected_root}, computed: {tree.root}"
        )
