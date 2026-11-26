"""OpenZeppelin StandardMerkleTree implementation (byte-for-byte parity).

Matches `@openzeppelin/merkle-tree` v1.x and `Distributor._buildLeaf` /
OpenZeppelin `MerkleProof.verify` on-chain.
"""

from typing import Dict, List, Sequence, Tuple

import eth_abi
from eth_utils import keccak
from web3 import Web3

ZERO_ROOT = "0x" + "00" * 32


def _abi_encode(types: Sequence[str], values: Sequence[object]) -> bytes:
    if hasattr(eth_abi, "encode"):
        return eth_abi.encode(types, values)
    return eth_abi.encode_abi(types, values)


def hash_leaf(address: str, amount: int) -> bytes:
    """Compute keccak256(bytes.concat(keccak256(abi.encode(address, uint256))))."""
    if amount < 0:
        raise ValueError("Leaf amount cannot be negative")
    checksum = Web3.toChecksumAddress(address)
    inner = keccak(_abi_encode(["address", "uint256"], [checksum, int(amount)]))
    return keccak(inner)


def hash_pair(left: bytes, right: bytes) -> bytes:
    """Commutative pair hash matching OZ standardNodeHash / MerkleProof._hashPair."""
    if left <= right:
        return keccak(left + right)
    return keccak(right + left)


def verify_proof(leaf: bytes, proof: Sequence[str], expected_root: str) -> bool:
    """Verify a Merkle proof against an expected root."""
    computed = leaf
    for sibling_hex in proof:
        sibling = bytes.fromhex(sibling_hex[2:] if sibling_hex.startswith("0x") else sibling_hex)
        if len(sibling) != 32:
            return False
        computed = hash_pair(computed, sibling)
    return ("0x" + computed.hex()).lower() == expected_root.lower()


class StandardMerkleTree:
    """StandardMerkleTree compatible with @openzeppelin/merkle-tree."""

    def __init__(self, entries: Sequence[Tuple[str, int]]):
        if not entries:
            raise ValueError("Expected non-zero number of leaves")

        # Prepare hashed values sorted ascending by leaf hash bytes (stable on ties).
        hashed = [
            (idx, addr.lower(), int(amount), hash_leaf(addr, amount))
            for idx, (addr, amount) in enumerate(entries)
        ]
        hashed.sort(key=lambda item: item[3])

        n = len(hashed)
        tree_len = 2 * n - 1
        tree: List[bytes] = [b""] * tree_len

        # Place sorted leaves at the end of the tree in reverse order (matching OZ makeMerkleTree).
        value_index_to_tree_index: Dict[int, int] = {}
        for sorted_i, (orig_idx, _addr, _amount, leaf_hash) in enumerate(hashed):
            tree_idx = tree_len - 1 - sorted_i
            tree[tree_idx] = leaf_hash
            value_index_to_tree_index[orig_idx] = tree_idx

        # Compute internal nodes bottom-up.
        for i in range(n - 2, -1, -1):
            tree[i] = hash_pair(tree[2 * i + 1], tree[2 * i + 2])

        self._tree = tree
        self._value_index_to_tree_index = value_index_to_tree_index

    @property
    def root(self) -> str:
        return "0x" + self._tree[0].hex()

    def get_proof(self, value_index: int) -> List[str]:
        if value_index not in self._value_index_to_tree_index:
            raise IndexError(f"Invalid value index: {value_index}")
        idx = self._value_index_to_tree_index[value_index]
        proof: List[str] = []
        while idx > 0:
            sibling = idx + 1 if (idx % 2 == 1) else idx - 1
            proof.append("0x" + self._tree[sibling].hex())
            idx = (idx - 1) // 2
        return proof
