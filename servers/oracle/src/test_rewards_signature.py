"""Tests for RewardsPublisher V3 148-byte signature and strict peer validation."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from eth_utils import keccak
from starlette.datastructures import Secret
from web3 import Web3

from common import crypto
from common.services.blockchain import BlockchainAccount
from common.services.oracle_dao import CoinPair, FullOracleRoundInfo, OracleBlockchainInfo
from oracle.src import oracle_settings
from oracle.src.oracle_publish_message import (
    PublishRewardsParams,
    REWARDS_MESSAGE_VERSION,
    compute_epoch_data_hash,
)
from oracle.src.request_validation import (
    DifferentLastPubBlock,
    InvalidSignature,
    RewardsRequestValidation,
    ValidationFailure,
)
from oracle.src.rewards.rpc_client import abi_encode
from oracle.src.rewards.types import CandidateResult, EpochData

# Deterministic test keys (not used on any live network)
KEY_A = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
KEY_B = "0xabcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
ADDR_A = crypto.addr_from_key(KEY_A)
ADDR_B = crypto.addr_from_key(KEY_B)
PUBLISHER_ADDR = "0x1234567890123456789012345678901234567890"
CHAIN_ID = 31


def _sample_epoch_data() -> EpochData:
    return EpochData(
        epoch=3,
        merkle_root="0x" + "ab" * 32,
        cid="bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku",
        snapshot_block=9418000,
        distributed_today=100 * 10**18,
    )


def _make_params(ed: EpochData, oracle_addr: str = ADDR_A, last_pub_block: int = 9417000, version: int = REWARDS_MESSAGE_VERSION):
    h = compute_epoch_data_hash(
        chain_id=CHAIN_ID,
        publisher_address=PUBLISHER_ADDR,
        epoch=ed.epoch,
        merkle_root=ed.merkle_root,
        cid=ed.cid,
        snapshot_block=ed.snapshot_block,
        distributed_today=ed.distributed_today,
    )
    return PublishRewardsParams(
        version=version,
        coin_pair=CoinPair("BPRO_REWARDS"),
        epoch=ed.epoch,
        merkle_root=ed.merkle_root,
        cid=ed.cid,
        snapshot_block=ed.snapshot_block,
        distributed_today=ed.distributed_today,
        epoch_data_hash=h,
        oracle_addr=oracle_addr,
        last_pub_block=last_pub_block,
    )


def _make_blockchain_info(last_pub_block: int = 9417000):
    oracles = [
        FullOracleRoundInfo(ADDR_A, "http://oracle-a:5556", 100, ADDR_A, 0, True, 1),
        FullOracleRoundInfo(ADDR_B, "http://oracle-b:5556", 100, ADDR_B, 0, True, 1),
    ]
    return OracleBlockchainInfo(
        coin_pair=CoinPair("BPRO_REWARDS"),
        selected_oracles=oracles,
        blockchain_price=0,
        block_num=9418050,
        last_pub_block=last_pub_block,
        last_pub_block_hash=b"\x01" * 32,
        valid_price_period_in_blocks=0,
    )


def test_epoch_data_hash_and_148_byte_envelope_match_solidity():
    ed = _sample_epoch_data()
    expected_hash = keccak(
        abi_encode(
            ["uint256", "address", "uint256", "bytes32", "bytes32", "uint256", "uint256"],
            [
                CHAIN_ID,
                Web3.toChecksumAddress(PUBLISHER_ADDR),
                ed.epoch,
                bytes.fromhex(ed.merkle_root[2:]),
                keccak(ed.cid.encode("utf-8")),
                ed.snapshot_block,
                ed.distributed_today,
            ],
        )
    )
    params = _make_params(ed)
    assert params.epoch_data_hash == expected_hash

    msg_hex = params.prepare_msg()
    raw_bytes = bytes.fromhex(msg_hex)
    assert len(raw_bytes) == 148

    acc_a = BlockchainAccount(ADDR_A, Secret(KEY_A))
    sig = crypto.sign_message(hexstr="0x" + msg_hex, account=acc_a)
    assert crypto.verify_signature(ADDR_A, msg_hex, sig)
    assert params.get_post() == "/sign-rewards/"
    post = params.to_post_data(sig)
    assert post["epoch"] == str(ed.epoch)
    assert post["cid"] == ed.cid
    assert post["merkle_root"] == ed.merkle_root
    assert post["snapshot_block"] == str(ed.snapshot_block)
    assert post["distributed_today"] == str(ed.distributed_today)


def test_rewards_validation_accepts_exact_match_and_signs(monkeypatch):
    acc_a = BlockchainAccount(ADDR_A, Secret(KEY_A))
    acc_b = BlockchainAccount(ADDR_B, Secret(KEY_B))
    monkeypatch.setattr(oracle_settings, "get_oracle_account", lambda: acc_b)

    ed = _sample_epoch_data()
    params = _make_params(ed, oracle_addr=ADDR_A)
    sig_a = crypto.sign_message(hexstr="0x" + params.prepare_msg(), account=acc_a)
    local_cand = CandidateResult(
        epoch_data=ed,
        snapshot_block_hash="0x" + "11" * 32,
        json_path="/tmp/ep.json",
        raw_bytes=b"{}",
    )
    turn = Mock()
    turn.validate_turn.return_value = (True, "ok")

    validator = RewardsRequestValidation(
        params=params,
        oracle_turn=turn,
        is_syncing=False,
        is_ready=True,
        last_block_when_available=9418020,
        local_candidate=local_cand,
        blockchain_info=_make_blockchain_info(),
        expected_epoch_data_hash=params.epoch_data_hash,
    )
    msg, sig_b = validator.validate_and_sign(sig_a.hex())
    assert crypto.verify_signature(ADDR_B, msg, sig_b)


@pytest.mark.parametrize(
    "field,mutated_value",
    [
        ("epoch", 4),
        ("merkle_root", "0x" + "cd" * 32),
        ("cid", "bafkreigaknpexyvxt76zgkitavbwx6ejgfheup5oybpm77f3pxzrvwpfdi"),
        ("snapshot_block", 9418001),
        ("distributed_today", 99 * 10**18),
    ],
)
def test_rewards_validation_rejects_any_mutated_epoch_field(field, mutated_value):
    local_ed = _sample_epoch_data()
    mutated_kwargs = {
        "epoch": local_ed.epoch,
        "merkle_root": local_ed.merkle_root,
        "cid": local_ed.cid,
        "snapshot_block": local_ed.snapshot_block,
        "distributed_today": local_ed.distributed_today,
    }
    mutated_kwargs[field] = mutated_value
    bad_params = _make_params(EpochData(**mutated_kwargs))
    local_cand = CandidateResult(
        epoch_data=local_ed,
        snapshot_block_hash="0x" + "11" * 32,
        json_path="/tmp/ep.json",
        raw_bytes=b"{}",
    )
    turn = Mock()
    turn.validate_turn.return_value = (True, "ok")

    validator = RewardsRequestValidation(
        params=bad_params,
        oracle_turn=turn,
        is_syncing=False,
        is_ready=True,
        last_block_when_available=9418020,
        local_candidate=local_cand,
        blockchain_info=_make_blockchain_info(),
    )
    with pytest.raises(ValidationFailure):
        validator.validate_params()


def test_rewards_validation_rejects_when_syncing_or_wrong_block_or_bad_sig():
    ed = _sample_epoch_data()
    params = _make_params(ed)
    local_cand = CandidateResult(
        epoch_data=ed,
        snapshot_block_hash="0x" + "11" * 32,
        json_path="/tmp/ep.json",
        raw_bytes=b"{}",
    )
    turn = Mock()
    turn.validate_turn.return_value = (True, "ok")

    # Syncing rejects
    v_sync = RewardsRequestValidation(
        params=params,
        oracle_turn=turn,
        is_syncing=True,
        is_ready=True,
        last_block_when_available=9418020,
        local_candidate=local_cand,
        blockchain_info=_make_blockchain_info(),
    )
    with pytest.raises(ValidationFailure, match="syncing"):
        v_sync.validate_params()

    # Different last_pub_block rejects
    v_blk = RewardsRequestValidation(
        params=_make_params(ed, last_pub_block=9999999),
        oracle_turn=turn,
        is_syncing=False,
        is_ready=True,
        last_block_when_available=9418020,
        local_candidate=local_cand,
        blockchain_info=_make_blockchain_info(last_pub_block=9417000),
    )
    with pytest.raises(DifferentLastPubBlock):
        v_blk.validate_params()

    # Invalid signature rejects
    v_sig = RewardsRequestValidation(
        params=params,
        oracle_turn=turn,
        is_syncing=False,
        is_ready=True,
        last_block_when_available=9418020,
        local_candidate=local_cand,
        blockchain_info=_make_blockchain_info(),
    )
    with pytest.raises(InvalidSignature):
        v_sig.validate_and_sign("0x" + "00" * 65)
