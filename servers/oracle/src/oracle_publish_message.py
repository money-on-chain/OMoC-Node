import logging
import typing

from common import helpers
from common.services.oracle_dao import CoinPair, PriceWithTimestamp

logger = logging.getLogger(__name__)


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
    ):
        return super(PublishPriceParams, cls).__new__(
            cls,
            version,
            coin_pair,
            price.price,
            price.ts_utc,
            oracle_addr,
            last_pub_block,
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
        # encVersion = enc_uint256(version)
        # encPrice = enc_uint256(price)
        # encOracle = enc_address(cfg.address)
        # encBlockNum = enc_uint256(blocknr)
        # header = bytes(MSG_HEADER, "ascii").hex()
        full_msg = "".join(f(x) for f, x in zip(fs, parameters))  ## header +
        logger.debug("msg: " + full_msg)
        return full_msg

    def get_post(self):
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
        return post_data
    
    def log_data(self):
        return "price: %r" % self.price


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


class PoolLiquidations(
    typing.NamedTuple(
        "PoolLiquidations",
        [("pool_id", str), ("users", typing.Tuple[str, ...])],
    )
):

    def __new__(cls, pool_id, users):
        if not isinstance(pool_id, str) or not pool_id.startswith("0x") or len(pool_id) != 66:
            raise ValueError("invalid liquidation pool id")
        try:
            int(pool_id[2:], 16)
        except ValueError as err:
            raise ValueError("invalid liquidation pool id") from err
        normalized_users = []
        for user in users:
            if not isinstance(user, str) or not user.startswith("0x") or len(user) != 42:
                raise ValueError("invalid liquidation user address")
            try:
                if int(user[2:], 16) == 0:
                    raise ValueError("liquidation user cannot be the zero address")
            except ValueError as err:
                raise ValueError("invalid liquidation user address") from err
            normalized_users.append(user)
        return super(PoolLiquidations, cls).__new__(cls, pool_id, tuple(normalized_users))

class PublishLiquidationParams(
    typing.NamedTuple(
        "PublishLiquidationParams",
        [
            ("version", int),
            ("coin_pair", CoinPair),
            ("liquidations", typing.Tuple[PoolLiquidations, ...]),
            ("oracle_addr", str),
            ("last_pub_block", int),
        ],
    )
):
    """LiquidationEngine authorization plus the publisher's local batch.

    The contract's 116-byte signed message intentionally excludes the batch.
    Consequently, peers receive and sign only the publisher authorization;
    the batch stays local until the publisher submits the transaction.
    """

    def __new__(
        cls,
        version,
        coin_pair,
        liquidations,
        oracle_addr,
        last_pub_block,
    ):
        batches = tuple(
            item if isinstance(item, PoolLiquidations) else PoolLiquidations(*item)
            for item in liquidations
        )
        return super(PublishLiquidationParams, cls).__new__(
            cls,
            version,
            coin_pair,
            batches,
            oracle_addr,
            last_pub_block,
        )

    @classmethod
    def from_post_data(
        cls,
        version,
        coin_pair,
        oracle_addr,
        last_pub_block,
    ):
        return cls(
            int(version),
            CoinPair(coin_pair),
            [],
            oracle_addr,
            int(last_pub_block),
        )

    def prepare_msg(self):
        parameters = [
            self.version,
            self.coin_pair.longer(),
            helpers.addr_to_number(self.oracle_addr),
            self.last_pub_block,
        ]
        encoders = [
            helpers.enc_uint256,
            helpers.enc_byte32,
            helpers.enc_packed_address,
            helpers.enc_uint256,
        ]
        full_msg = "".join(f(value) for f, value in zip(encoders, parameters))
        logger.debug("Liquidation authorization msg: %s", full_msg)
        return full_msg

    def get_post(self):
        return "/sign-liquidation/"

    def to_post_data(self, my_signature):
        return {
            "version": str(self.version),
            "coin_pair": str(self.coin_pair),
            "oracle_addr": self.oracle_addr,
            "last_pub_block": str(self.last_pub_block),
            "signature": my_signature.hex(),
        }

    def as_contract_liquidations(self):
        return [(item.pool_id, list(item.users)) for item in self.liquidations]

    def log_data(self):
        total = sum(len(item.users) for item in self.liquidations)
        return "liquidations: %d in %d pools" % (total, len(self.liquidations))
