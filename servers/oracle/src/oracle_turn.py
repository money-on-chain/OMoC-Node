import logging
import typing

from common import helpers
from common.helpers import MyCfgdLogger
from common.services.blockchain import to_med
from common.services.conditional_publish import ConditionalPublishServiceBase
from common.services.oracle_dao import CoinPair, PriceWithTimestamp, FullOracleRoundInfo
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfo
from oracle.src.oracle_configuration import OracleConfiguration, OracleTurnConfiguration
from oracle.src.oracle_settings import get_oracle_account
from oracle.src.select_next import select_next_addresses

logger = logging.getLogger(__name__)


class PriceFollower(MyCfgdLogger):
    def __init__(self, coin_pair):
        self._coin_pair = coin_pair
        self.price_change_block = -1
        self.price_change_pub_block = -1
        super().__init__(" : ", coin_pair)

    def price_changed_blocks(self, conf: OracleTurnConfiguration, block_chain_info: OracleBlockchainInfo,
                             exchange_price: PriceWithTimestamp, signal: ConditionalPublishServiceBase):
        """How many blocks since last publication in the blockchain and a price change"""
        if block_chain_info.last_pub_block < 0 or block_chain_info.block_num < 0:
            raise Exception("%r : Invalid block number", self._coin_pair)

        # We already detected a price change before.
        if self.price_change_pub_block == block_chain_info.last_pub_block and self.price_change_block >= 0:
            diff = block_chain_info.block_num - self.price_change_block
            self.debug(f"Price changed {diff} blocks ago ({block_chain_info.block_num}-{self.price_change_block}")
            return diff

        delta = helpers.price_delta(block_chain_info.blockchain_price, exchange_price.price)
        threshold_delta = signal.get_price_delta(conf.price_delta_pct)
        if delta < threshold_delta:
            self.debug("We are not fall backs and/or the price didn't change enough %r < %r,"
                       " block chain price %r exchange price %r" %
                       (delta, threshold_delta,
                        block_chain_info.blockchain_price, exchange_price.price))
            return

        # The publication has changed
        if self.price_change_pub_block != block_chain_info.last_pub_block:
            self.info(f"The publication block has changed: "
                      f"{self.price_change_pub_block} != {block_chain_info.last_pub_block}")
            self.price_change_pub_block = block_chain_info.last_pub_block

        # We detected a price change in current publication but is the first change
        self.price_change_block = block_chain_info.block_num
        self.info("The price has changed, right now")
        return 0


class OracleTurn(MyCfgdLogger):
    def __init__(self, conf: OracleConfiguration, coin_pair: CoinPair, signal):
        self._conf: OracleConfiguration = conf
        self._coin_pair: CoinPair = coin_pair
        self.price_follower = PriceFollower(coin_pair)
        self._signal = signal
        super().__init__(None, coin_pair, get_oracle_account().short)

    # Called by /sign endpoint
    def validate_turn(self, vi: OracleBlockchainInfo, oracle_addr, exchange_price: PriceWithTimestamp):
        oracle_addresses = select_next_addresses(vi.last_pub_block_hash, vi.selected_oracles)
        if self.is_selected_oracle(oracle_addresses, oracle_addr):
            return True, self.info("selected chosen " + oracle_addr)
        return self._is_oracle_turn_with_msg(vi, oracle_addr, exchange_price, oracle_addresses)

    # Called byt coin_pair_price_loop
    def is_oracle_turn(self, vi: OracleBlockchainInfo, oracle_addr, exchange_price: PriceWithTimestamp):
        oracle_addresses = select_next_addresses(vi.last_pub_block_hash, vi.selected_oracles)
        self.debug(f" -fallbacks: {[to_med(str(x)) for x in oracle_addresses]} / {[to_med(x.addr) for x in vi.selected_oracles]}")
        (is_my_turn, msg) = self._is_oracle_turn_with_msg(vi, oracle_addr, exchange_price, oracle_addresses)
        return is_my_turn, [str(x) for x in oracle_addresses]

    def _is_oracle_turn_with_msg(self,
                                 vi: OracleBlockchainInfo,
                                 oracle_addr,
                                 exchange_price: PriceWithTimestamp,
                                 oracle_addresses):
        if not self.is_oracle_selected_in_round(vi.selected_oracles, oracle_addr):
            return False, self.info(f"is not {oracle_addr} turn we are not in the current round selected oracles")

        conf = self._conf.oracle_turn_conf
        entering_fallback_sequence = self.get_fallback_sequence(conf.entering_fallbacks_amounts,
                                                                len(vi.selected_oracles))

        self.debug("1 ---> %r" % (vi,))
        self.debug("1 ---> %r %r" % (oracle_addr, exchange_price))
        self.debug("1 ---> %r %r" % (oracle_addresses, entering_fallback_sequence))

        # WARN if oracles won't get to publish before price expires
        ####################################
        if conf.trigger_valid_publication_blocks < len(entering_fallback_sequence) + 1:
            self.debug("PRICE will EXPIRE before oracles get to publish. Check configuration.")
        ####################################

        # WARN if valid_price_period_in_blocks < trigger_valid_publication_blocks and return False
        # as it may allow many oracles to publish without a price change
        ####################################
        if vi.valid_price_period_in_blocks < conf.trigger_valid_publication_blocks:
            return False, self.error("valid_price_period_in_blocks should be higher than trigger_valid_publication_blocks \
                   %r < %r. Fix in configuration." % (vi.valid_price_period_in_blocks,
                                                      conf.trigger_valid_publication_blocks))
        ####################################
        last_pub_block = self._signal.max_pub_block(vi.last_pub_block)
        start_block_pub_period_before_price_expires = (last_pub_block - conf.trigger_valid_publication_blocks +
                                                   self._signal.get_valid_price_period(vi.valid_price_period_in_blocks))

        self.debug(f"block_num {vi.block_num}  "
                   f"start_block_pub_period_before_price_expires {start_block_pub_period_before_price_expires} "
                   f"vi.valid_price_period_in_blocks {vi.valid_price_period_in_blocks}")
        if vi.block_num >= start_block_pub_period_before_price_expires:
            can_I_publish = self.can_oracle_publish(vi.block_num - start_block_pub_period_before_price_expires,
                                                    oracle_addr, oracle_addresses, entering_fallback_sequence)
            if can_I_publish:
                return True, self.debug(f"I'm selected to publish before prices expires")

        blocks_since_price_change = self.price_follower.price_changed_blocks(conf, vi, exchange_price, self._signal)

        if blocks_since_price_change is None:
            return False, self.debug(f"{oracle_addr} Price didn't change enough.")

        if blocks_since_price_change < conf.price_publish_blocks:
            return False, self.warning("%s Price changed but still waiting to reach %r blocks to be allowed. %r < %r" %
                        (oracle_addr, conf.price_publish_blocks, blocks_since_price_change, conf.price_publish_blocks))

        self.debug("2 ---> %r %r %r %r %r" % (blocks_since_price_change, conf.price_publish_blocks, oracle_addr,
                                              oracle_addresses, entering_fallback_sequence))
        can_I_publish = self.can_oracle_publish(blocks_since_price_change - conf.price_publish_blocks,
                                                oracle_addr, oracle_addresses, entering_fallback_sequence)
        if can_I_publish:
            return True, self.debug(f"{oracle_addr} selected to publish after price change. "
                                   f"Blocks since price change: {blocks_since_price_change}")
        return False, self.debug(f" {oracle_addr} is NOT the chosen fallback {blocks_since_price_change}")

    @staticmethod
    def is_selected_oracle(oracle_addresses, oracle_addr):
        return oracle_addresses[0] == oracle_addr

    @staticmethod
    def get_fallback_sequence(entering_fallbacks_amounts, selected_oracles_len):
        # x + 1 so that when it's being used as index for the addresses' list,
        # it can get the x addresses after the first one (the chosen oracle)
        entering_fallback_sequence = [x + 1 for x in entering_fallbacks_amounts]
        # Insert amount 1 at the beginning that it will be fetched by index 0 of 0 blocks since price change
        # so that 0 fallbacks are chosen. See selected_fallbacks variable assignment.
        entering_fallback_sequence.insert(0, 1)
        if len(entering_fallback_sequence) == 0 or entering_fallback_sequence[-1] < selected_oracles_len - 1:
            entering_fallback_sequence.append(selected_oracles_len)
        return entering_fallback_sequence

    @staticmethod
    def can_oracle_publish(blocks_since_pub_is_allowed, oracle_addr, oracle_addresses, entering_fallback_sequence):
        if OracleTurn.is_selected_oracle(oracle_addresses, oracle_addr):
            return True
        # Gets blocks since publication is allowed from blocks_since_pub_is_allowed and uses it as index in the amount
        # of entering fall backs sequence.
        # Also makes sure the index is within range of the list.
        # XXX /// here TENUKI
        entering_fallback_sequence_index = blocks_since_pub_is_allowed \
            if blocks_since_pub_is_allowed is not None \
               and blocks_since_pub_is_allowed < len(entering_fallback_sequence) \
            else len(entering_fallback_sequence) - 1
        selected_fallbacks = oracle_addresses[1:entering_fallback_sequence[entering_fallback_sequence_index]]
        return oracle_addr in selected_fallbacks

    @staticmethod
    def is_oracle_selected_in_round(selected_oracles: typing.List[FullOracleRoundInfo], oracle_addr):
        return len(selected_oracles) != 0 and \
               oracle_addr in [x.addr for x in selected_oracles] and \
               not any(x.addr == oracle_addr and not x.selectedInCurrentRound for x in selected_oracles)
