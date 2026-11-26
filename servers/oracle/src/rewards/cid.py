"""Deterministic local CIDv1 UnixFS computation without an IPFS daemon.

Matches Kubo / ipfs-unixfs-importer with fixed parameters:
    ipfs add --cid-version=1 --raw-leaves --chunker=size-262144 --only-hash -Q

Profile:
- CID version 1 (0x01), multibase base32 lowercase without '=' padding ('b' prefix)
- Multihash sha2-256 (0x12, 0x20 + 32-byte digest)
- Fixed chunker: CHUNK_SIZE = 262144 bytes (256 KiB)
- Raw leaves: codec raw (0x55)
- Balanced DAG with MAX_CHILDREN = 174 (dag-pb codec 0x70), no wrapping directory
"""

import base64
import hashlib
from typing import List, Tuple

CHUNK_SIZE = 262144
MAX_CHILDREN = 174

CID_V1_RAW_PREFIX = b"\x01\x55\x12\x20"
CID_V1_DAG_PB_PREFIX = b"\x01\x70\x12\x20"


def _encode_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("Varint cannot be negative")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            break
    return bytes(out)


def _pb_varint(field_number: int, value: int) -> bytes:
    tag = (field_number << 3) | 0
    return _encode_varint(tag) + _encode_varint(value)


def _pb_bytes(field_number: int, data: bytes) -> bytes:
    tag = (field_number << 3) | 2
    return _encode_varint(tag) + _encode_varint(len(data)) + data


def _encode_unixfs_file(filesize: int, blocksizes: List[int]) -> bytes:
    # UnixFS Data protobuf:
    #   field 1 (varint): Type = 2 (File)
    #   field 3 (varint): filesize
    #   field 4 (repeated varint): blocksizes
    parts = [
        _pb_varint(1, 2),
        _pb_varint(3, filesize),
    ]
    for size in blocksizes:
        parts.append(_pb_varint(4, size))
    return b"".join(parts)


def _encode_pb_link(cid_bytes: bytes, tsize: int) -> bytes:
    # PBLink protobuf (canonical dag-pb field order: 1 Hash, 2 Name, 3 Tsize):
    #   field 1 (bytes): Hash
    #   field 2 (string/bytes): Name = ""
    #   field 3 (varint): Tsize
    return b"".join(
        [
            _pb_bytes(1, cid_bytes),
            _pb_bytes(2, b""),
            _pb_varint(3, tsize),
        ]
    )


def _encode_pb_node(links: List[Tuple[bytes, int, int]], unixfs_data: bytes) -> bytes:
    # PBNode protobuf (canonical dag-pb wire order: Links (field 2) BEFORE Data (field 1)):
    #   field 2 (repeated PBLink): Links
    #   field 1 (bytes): Data
    parts = [
        _pb_bytes(2, _encode_pb_link(child_cid, child_cum_size))
        for child_cid, _child_filesize, child_cum_size in links
    ]
    parts.append(_pb_bytes(1, unixfs_data))
    return b"".join(parts)


def _cid_bytes_to_base32(cid_bytes: bytes) -> str:
    return "b" + base64.b32encode(cid_bytes).decode("ascii").lower().rstrip("=")


def compute_cid_v1(raw_bytes: bytes) -> str:
    """Compute the deterministic CIDv1 string for `raw_bytes`."""
    if len(raw_bytes) <= CHUNK_SIZE:
        digest = hashlib.sha256(raw_bytes).digest()
        return _cid_bytes_to_base32(CID_V1_RAW_PREFIX + digest)

    # Leaf tuples: (cid_bytes, filesize, cumulative_dag_size)
    nodes: List[Tuple[bytes, int, int]] = []
    for offset in range(0, len(raw_bytes), CHUNK_SIZE):
        chunk = raw_bytes[offset : offset + CHUNK_SIZE]
        cid_bytes = CID_V1_RAW_PREFIX + hashlib.sha256(chunk).digest()
        chunk_len = len(chunk)
        nodes.append((cid_bytes, chunk_len, chunk_len))

    # Build balanced DAG bottom-up with branching factor MAX_CHILDREN (174),
    # keeping every leaf at the same depth from the root (matching Boxo/Kubo).
    while len(nodes) > 1:
        next_level: List[Tuple[bytes, int, int]] = []
        for i in range(0, len(nodes), MAX_CHILDREN):
            group = nodes[i : i + MAX_CHILDREN]
            blocksizes = [item[1] for item in group]
            total_filesize = sum(blocksizes)
            unixfs_data = _encode_unixfs_file(total_filesize, blocksizes)
            pb_node = _encode_pb_node(group, unixfs_data)
            cid_bytes = CID_V1_DAG_PB_PREFIX + hashlib.sha256(pb_node).digest()
            cum_dag_size = len(pb_node) + sum(item[2] for item in group)
            next_level.append((cid_bytes, total_filesize, cum_dag_size))
        nodes = next_level

    return _cid_bytes_to_base32(nodes[0][0])
