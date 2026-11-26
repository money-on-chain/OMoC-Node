"""Tests for canonical EpochJson serialization and deterministic CIDv1 UnixFS."""

import json

from oracle.src.rewards.cid import CHUNK_SIZE, MAX_CHILDREN, compute_cid_v1
from oracle.src.rewards.epoch_json import (
    build_epoch_json,
    parse_epoch_json,
    serialize_epoch_json,
)


def test_cid_v1_known_kubo_single_block_vectors():
    # `printf '' | ipfs add --cid-version=1 --raw-leaves --chunker=size-262144 --only-hash -Q`
    assert compute_cid_v1(b"") == "bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"
    # `printf 'hello world\n' | ipfs add --cid-version=1 --raw-leaves --chunker=size-262144 --only-hash -Q`
    assert (
        compute_cid_v1(b"hello world\n")
        == "bafkreifjjcie6lypi6ny7amxnfftagclbuxndqonfipmb64f2km2devei4"
    )


def test_cid_v1_chunk_boundary_raw_vs_dag_pb():
    exact_chunk = b"a" * CHUNK_SIZE
    cid_exact = compute_cid_v1(exact_chunk)
    assert cid_exact.startswith("bafkrei")
    assert "=" not in cid_exact

    over_chunk = b"a" * (CHUNK_SIZE + 1)
    cid_over = compute_cid_v1(over_chunk)
    assert cid_over.startswith("bafybei")
    assert "=" not in cid_over
    assert cid_over != cid_exact


def test_cid_v1_multiblock_and_three_level_dag():
    # > 1 MiB (5 chunks, 2-level DAG)
    one_mib_plus = bytes(range(256)) * ((1024 * 1024 // 256) + 10)
    cid_1m = compute_cid_v1(one_mib_plus)
    assert cid_1m.startswith("bafybei")
    assert cid_1m == compute_cid_v1(one_mib_plus)

    # > 174 chunks (175 chunks = > 45 MiB, triggers 3-level balanced DAG with uniform leaf depth)
    big = b"\x42" * (CHUNK_SIZE * MAX_CHILDREN + 1)
    cid_big = compute_cid_v1(big)
    assert cid_big.startswith("bafybei")
    assert cid_big == compute_cid_v1(big)
    assert cid_big != compute_cid_v1(b"\x42" * (CHUNK_SIZE * MAX_CHILDREN))


def test_canonical_epoch_json_serialization_format_and_roundtrip():
    ep = build_epoch_json(
        epoch=2,
        snapshot_block=9418000,
        holders=[
            ("0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB", 200),
            ("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", 100),
        ],
        balances=[
            ("0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB", 500),
            ("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", 250),
        ],
        registered_contracts=[
            "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
            "0x0000000000000000000000000000000000000005",
            "0xcccccccccccccccccccccccccccccccccccccccc",
        ],
        expected_total=300,
    )
    raw = serialize_epoch_json(ep)
    text = raw.decode("utf-8")

    # No trailing newline and no BOM (matches JSON.stringify(payload, null, 2))
    assert not text.endswith("\n")
    assert not raw.startswith(b"\xef\xbb\xbf")

    parsed_dict = json.loads(text)
    assert list(parsed_dict.keys()) == [
        "epoch",
        "snapshotBlock",
        "merkleRoot",
        "holders",
        "balances",
        "registeredContracts",
    ]
    assert [h["address"] for h in parsed_dict["holders"]] == [
        "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    ]
    assert [h["cumulativeAmount"] for h in parsed_dict["holders"]] == ["100", "200"]
    assert parsed_dict["registeredContracts"] == [
        "0x0000000000000000000000000000000000000005",
        "0xcccccccccccccccccccccccccccccccccccccccc",
    ]

    reparsed = parse_epoch_json(raw)
    assert serialize_epoch_json(reparsed) == raw
    assert compute_cid_v1(raw).startswith("bafkrei")
