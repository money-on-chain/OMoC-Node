import logging
import typing

import eth_abi
from eth_utils import keccak
from web3 import Web3

from common import helpers
from common.services.oracle_dao import CoinPair, PriceWithTimestamp

logger = logging.getLogger(__name__)

LEGACY_PRICE_MESSAGE_VERSION = 3
EXPIRING_PRICE_MESSAGE_VERSION = 4
REWARDS_MESSAGE_VERSION = 3


def compute_epoch_data_hash(
    chain_id: int,
    publisher_address: str,
    epoch: int,
    merkle_root: str,
    cid: str,
    snapshot_block: int,
    distributed_today: int,
) -> bytes:
    """Compute RewardsPublisher.getEpochDataHash(_data) as 32 bytes."""
    root_hex = merkle_root[2:] if merkle_root.startswith("0x") else merkle_root
    root_bytes = bytes.fromhex(root_hex)
    if len(root_bytes) != 32:
        raise ValueError("merkle_root must be 32 bytes")
    cid_hash = keccak(cid.encode("utf-8"))
    types = [
        "uint256",
        "address",
        "uint256",
        "bytes32",
        "bytes32",
        "uint256",
        "uint256",
    ]
    values = [
        int(chain_id),
        Web3.toChecksumAddress(publisher_address),
        int(epoch),
        root_bytes,
        cid_hash,
        int(snapshot_block),
        int(distributed_today),
    ]
    if hasattr(eth_abi, "encode"):
        encoded = eth_abi.encode(types, values)
    else:
        encoded = eth_abi.encode_abi(types, values)
    return keccak(encoded)


class PublishPriceParams(
    typing.NamedTuple(
        "PublishPriceParams",
        [
            ("version", int),
            ("coin_pair", CoinPair),
            ("price", int),
            ("price_ts_utc", int),
            ("oracle_addr", str),
            ("last_pub_block", int),
            ("expiration", typing.Optional[int]),
        ],
    )
):
    def __new__(
        cls,
        version: int,
        coin_pair: CoinPair,
        price: PriceWithTimestamp,
        oracle_addr: str,
        last_pub_block: int,
        expiration: typing.Optional[int] = None,
    ):
        return super(PublishPriceParams, cls).__new__(
            cls,
            version,
            coin_pair,
            price.price,
            price.ts_utc,
            oracle_addr,
            last_pub_block,
            expiration,
        )

    def prepare_msg(self):
        parameters = [
            self.version,
            self.coin_pair.longer(),
            self.price,
            helpers.addr_to_number(self.oracle_addr),
            self.last_pub_block,
        ]
        fs = [
            helpers.enc_uint256,
            helpers.enc_byte32,
            helpers.enc_uint256,
            helpers.enc_packed_address,
            helpers.enc_uint256,
        ]
        if self.expiration is not None:
            parameters.append(self.expiration)
            fs.append(helpers.enc_uint256)
        # encVersion = enc_uint256(version)
        # encPrice = enc_uint256(price)
        # encOracle = enc_address(cfg.address)
        # encBlockNum = enc_uint256(blocknr)
        # header = bytes(MSG_HEADER, "ascii").hex()
        full_msg = "".join(f(x) for f, x in zip(fs, parameters))  ## header +
        logger.debug("msg: " + full_msg)
        return full_msg

    def get_post(self):
        if self.expiration is not None:
            return "/sign-price-v4/"
        return "/sign/"

    def to_post_data(self, my_signature):
        post_data = {
            "version": str(self.version),
            "coin_pair": str(self.coin_pair),
            "price": str(self.price),
            "price_timestamp": str(self.price_ts_utc),
            "oracle_addr": self.oracle_addr,
            "last_pub_block": str(self.last_pub_block),
            "signature": my_signature.hex()
        }
        if self.expiration is not None:
            post_data["expiration"] = str(self.expiration)
        return post_data
    
    def log_data(self):
        expiration = (
            "" if self.expiration is None else ", expiration: %r" % self.expiration
        )
        return "price: %r%s" % (self.price, expiration)

    def as_legacy(self):
        return PublishPriceParams(
            LEGACY_PRICE_MESSAGE_VERSION,
            self.coin_pair,
            PriceWithTimestamp(self.price, self.price_ts_utc),
            self.oracle_addr,
            self.last_pub_block,
        )


class PublishTaskParams(
    typing.NamedTuple(
        "PublishTaskParams",
        [
            ("version", int),
            ("coin_pair", CoinPair),
            ("tasks_flags", int),
            ("oracle_addr", str),
            ("last_pub_block", int),
        ],
    )

    
):
    def __new__(
        cls, version: int, coin_pair: CoinPair, tasks_flags: int, oracle_addr: str, last_pub_block: int
    ):
        return super(PublishTaskParams, cls).__new__(
            cls, version, coin_pair, tasks_flags, oracle_addr, last_pub_block
        )

    def prepare_msg(self):
        parameters = [
            self.version,
            self.coin_pair.longer(),
            self.tasks_flags,
            helpers.addr_to_number(self.oracle_addr),
            self.last_pub_block,
        ]
        fs = [
            helpers.enc_uint256,
            helpers.enc_byte32,
            helpers.enc_uint256,
            helpers.enc_packed_address,
            helpers.enc_uint256,
        ]
        # encVersion = enc_uint256(version)
        # encOracle = enc_address(cfg.address)
        # encBlockNum = enc_uint256(blocknr)
        # header = bytes(MSG_HEADER, "ascii").hex()
        full_msg = "".join(f(x) for f, x in zip(fs, parameters))  ## header +
        logger.debug("msg: " + full_msg)
        return full_msg

    def get_post(self):
        return "/sign-task/"

    def to_post_data(self, my_signature):
        post_data = {
            "version": str(self.version),
            "coin_pair": str(self.coin_pair),
            "tasks_flags": str(self.tasks_flags),
            "oracle_addr": self.oracle_addr,
            "last_pub_block": str(self.last_pub_block),
            "signature": my_signature.hex()
        }
        return post_data
    
    def log_data(self):
        return ""


class PublishRewardsParams(
    typing.NamedTuple(
        "PublishRewardsParams",
        [
            ("version", int),
            ("coin_pair", CoinPair),
            ("epoch", int),
            ("merkle_root", str),
            ("cid", str),
            ("snapshot_block", int),
            ("distributed_today", int),
            ("epoch_data_hash", bytes),
            ("oracle_addr", str),
            ("last_pub_block", int),
        ],
    )
):
    def __new__(
        cls,
        version: int,
        coin_pair: CoinPair,
        epoch: int,
        merkle_root: str,
        cid: str,
        snapshot_block: int,
        distributed_today: int,
        epoch_data_hash: typing.Optional[bytes],
        oracle_addr: str,
        last_pub_block: int,
    ):
        if epoch_data_hash is not None:
            if isinstance(epoch_data_hash, str):
                clean = epoch_data_hash[2:] if epoch_data_hash.startswith("0x") else epoch_data_hash
                epoch_data_hash = bytes.fromhex(clean)
            if len(epoch_data_hash) != 32:
                raise ValueError("epoch_data_hash must be 32 bytes")
        return super(PublishRewardsParams, cls).__new__(
            cls,
            int(version),
            coin_pair,
            int(epoch),
            merkle_root,
            cid,
            int(snapshot_block),
            int(distributed_today),
            epoch_data_hash,
            oracle_addr,
            int(last_pub_block),
        )

    def prepare_msg(self):
        if self.epoch_data_hash is None:
            raise ValueError("epoch_data_hash must be set before preparing message")
        parameters = [
            self.version,
            self.coin_pair.longer(),
            self.epoch_data_hash,
            helpers.addr_to_number(self.oracle_addr),
            self.last_pub_block,
        ]
        fs = [
            helpers.enc_uint256,
            helpers.enc_byte32,
            helpers.enc_byte32,
            helpers.enc_packed_address,
            helpers.enc_uint256,
        ]
        full_msg = "".join(f(x) for f, x in zip(fs, parameters))
        logger.debug("rewards msg: " + full_msg)
        return full_msg

    def get_post(self):
        return "/sign-rewards/"

    def to_post_data(self, my_signature):
        return {
            "version": str(self.version),
            "coin_pair": str(self.coin_pair),
            "epoch": str(self.epoch),
            "merkle_root": self.merkle_root,
            "cid": self.cid,
            "snapshot_block": str(self.snapshot_block),
            "distributed_today": str(self.distributed_today),
            "oracle_addr": self.oracle_addr,
            "last_pub_block": str(self.last_pub_block),
            "signature": my_signature.hex(),
        }

    def log_data(self):
        return (
            f"epoch: {self.epoch}, snapshotBlock: {self.snapshot_block}, "
            f"root: {self.merkle_root[:10]}..., cid: {self.cid}, "
            f"distributedToday: {self.distributed_today}"
        )
