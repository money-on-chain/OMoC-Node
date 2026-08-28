import logging

from eth_account import Account
from eth_account.messages import encode_defunct
from hexbytes import HexBytes

from common.services.blockchain import BlockchainAccount

logger = logging.getLogger(__name__)

CONTRACT_SIGNATURE_V_VALUES = frozenset((0, 1, 27, 28))


def addr_from_key(key):
    return Account.from_key(key).address


def _sign_msghash(msghash, key):
    return Account.sign_message(msghash, key)


def sign_message(text=None, hexstr=None, account: BlockchainAccount = None):
    msghash = encode_defunct(text=text, hexstr=hexstr)
    result = _sign_msghash(msghash, str(account.key))
    return result["signature"]


def sign_message_hex(text=None, hexstr=None, account: BlockchainAccount = None):
    s = sign_message(text, hexstr, account)
    return HexBytes(s.hex())


def recover(text=None, hexstr=None, signature=None):
    signature = HexBytes(signature)
    if len(signature) != 65:
        raise ValueError(
            "Invalid signature length: expected 65 bytes, got %d" % len(signature)
        )

    v = signature[64]
    if v not in CONTRACT_SIGNATURE_V_VALUES:
        raise ValueError(
            "Invalid signature v value: %d; expected 0, 1, 27, or 28" % v
        )

    msg = encode_defunct(text=text, hexstr=hexstr)
    return Account.recover_message(msg, signature=signature)


def verify_signature(address, message, signature):
    try:
        recovered_address = recover(hexstr=message, signature=signature)
    except (TypeError, ValueError) as err:
        logger.error("Invalid signature from %s: %s", address, err)
        return False

    ret = (address == recovered_address)
    if not ret:
        logger.error("Invalid signature from: %s" % address)
    return ret
