import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from hexbytes import HexBytes

from common import crypto


PRIVATE_KEY = bytes.fromhex("01".zfill(64))
MESSAGE = "01020304"


def signed_message():
    message = encode_defunct(hexstr=MESSAGE)
    return HexBytes(Account.sign_message(message, PRIVATE_KEY)["signature"])


def with_v(signature, v):
    return HexBytes(bytes(signature[:64]) + bytes((v,)))


def test_recover_accepts_contract_signature_v_encodings():
    signature = signed_message()
    expected_address = Account.from_key(PRIVATE_KEY).address
    canonical_v = signature[64]
    compact_v = canonical_v - 27

    assert canonical_v in (27, 28)
    assert crypto.recover(hexstr=MESSAGE, signature=signature) == expected_address
    assert (
        crypto.recover(hexstr=MESSAGE, signature=with_v(signature, compact_v))
        == expected_address
    )


def test_recover_rejects_eip155_v_before_eth_account_normalizes_it():
    signature = signed_message()
    eip155_v = signature[64] + 10

    assert eip155_v in (37, 38)
    with pytest.raises(ValueError, match="Invalid signature v value"):
        crypto.recover(hexstr=MESSAGE, signature=with_v(signature, eip155_v))


def test_recover_rejects_every_other_one_byte_v_value():
    signature = signed_message()
    rejected_values = set(range(256)) - crypto.CONTRACT_SIGNATURE_V_VALUES

    for v in rejected_values:
        with pytest.raises(ValueError, match="Invalid signature v value"):
            crypto.recover(hexstr=MESSAGE, signature=with_v(signature, v))


def test_verify_signature_returns_false_for_rejected_v():
    signature = signed_message()
    address = Account.from_key(PRIVATE_KEY).address

    assert not crypto.verify_signature(
        address,
        MESSAGE,
        with_v(signature, signature[64] + 10),
    )


def test_recover_rejects_non_65_byte_signature():
    with pytest.raises(ValueError, match="Invalid signature length"):
        crypto.recover(hexstr=MESSAGE, signature=b"\x00" * 64)
