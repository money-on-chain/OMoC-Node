import logging
import typing

from common import helpers
from common.services.oracle_dao import CoinPair, PriceWithTimestamp

logger = logging.getLogger(__name__)

LEGACY_PRICE_MESSAGE_VERSION = 3
EXPIRING_PRICE_MESSAGE_VERSION = 4


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
