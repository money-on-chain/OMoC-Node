import logging

from common import helpers
from common.services.oracle_dao import CoinPair, PriceWithTimestamp
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfo
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.select_next import select_next

logger = logging.getLogger(__name__)


class OracleTurn:

    def __init__(self, conf: OracleConfiguration, coin_pair: CoinPair):
        self._conf: OracleConfiguration = conf
        self._coin_pair: CoinPair = coin_pair
        self.price_change_block = -1
        self.price_change_pub_block = -1

    # Called by /sign endpoint
    def validate_turn(self, vi: OracleBlockchainInfo, oracle_addr, exchange_price: PriceWithTimestamp):
        ordered_oracle_selection = select_next(vi.last_pub_block_hash,
                                               vi.selected_oracles)
        oracle_addresses = [x.addr for x in ordered_oracle_selection]
        if oracle_addr == oracle_addresses[0]:
            msg = "%r : selected chosen %s" % (self._coin_pair, oracle_addr)
            logger.info(msg)
            return True, msg
        return self._is_oracle_turn_with_msg(vi, oracle_addr, exchange_price, oracle_addresses)

    # Called byt coin_pair_price_loop
    def is_oracle_turn(self, vi: OracleBlockchainInfo, oracle_addr, exchange_price: PriceWithTimestamp):
        ordered_oracle_selection = select_next(vi.last_pub_block_hash,
                                               vi.selected_oracles)
        oracle_addresses = [x.addr for x in ordered_oracle_selection]
        (is_my_turn, msg) = self._is_oracle_turn_with_msg(vi, oracle_addr, exchange_price, oracle_addresses)
        return is_my_turn

    # How many blocks since last publication in the blockchain and a price change
    def _price_changed_blocks(self, conf, block_chain: OracleBlockchainInfo, exchange_price: PriceWithTimestamp):
        if block_chain.last_pub_block < 0 or block_chain.block_num < 0:
            raise Exception("%r : Invalid block number", self._coin_pair)

        # We already detected a price change before.
        if self.price_change_pub_block == block_chain.last_pub_block and self.price_change_block >= 0:
            logger.info(
                "%r : Price changed %r blocks ago" % (self._coin_pair, block_chain.block_num - self.price_change_block))
            return block_chain.block_num - self.price_change_block

        delta = helpers.price_delta(block_chain.blockchain_price, exchange_price.price)
        if delta < conf.price_fallback_delta_pct:
            logger.info("%r : We are not fallbacks and/or the price didn't change enough %r < %r,"
                        " blockchain price %r exchange price %r" %
                        (self._coin_pair, delta, conf.price_fallback_delta_pct,
                         block_chain.blockchain_price, exchange_price.price))
            return None

        # The publication has changed
        if self.price_change_pub_block != block_chain.last_pub_block:
            logger.info(
                "%r : The publication block has changed: %r != %r" % (
                    self._coin_pair, self.price_change_pub_block, block_chain.last_pub_block))
            self.price_change_pub_block = block_chain.last_pub_block

        # We detected a price change in current publication but is the first change
        self.price_change_block = block_chain.block_num
        logger.info("%r : The price has changed, right now" % self._coin_pair)
        return 0

    @staticmethod
    def get_fallback_sequence(entering_fallbacks_amounts, selected_oracles_len):
        entering_fallback_sequence = [x for x in entering_fallbacks_amounts]
        if (len(entering_fallback_sequence) == 0 or entering_fallback_sequence[-1] < selected_oracles_len - 1):
            entering_fallback_sequence.append(selected_oracles_len)
        return entering_fallback_sequence

    @staticmethod
    def can_oracle_publish(blocks_since_pub_is_allowed, oracle_addr, oracle_addresses, entering_fallback_sequence):
        if oracle_addr == oracle_addresses[0]:
            return True
        # Gets blocks since publication is allowed from blocks_since_pub_is_allowed and uses it as index in the amount of entering fallbacks sequence.
        # Makes sure the index is within range of the list.
        entering_fallback_sequence_index = blocks_since_pub_is_allowed if blocks_since_pub_is_allowed is not None and blocks_since_pub_is_allowed < len(entering_fallback_sequence) \
                                                   else len(entering_fallback_sequence) - 1
        selected_fallbacks = oracle_addresses[1:entering_fallback_sequence[entering_fallback_sequence_index]]
        if oracle_addr in selected_fallbacks:
            return True
        return False

    def _is_oracle_turn_with_msg(self,
                                 vi: OracleBlockchainInfo,
                                 oracle_addr,
                                 exchange_price: PriceWithTimestamp,
                                 oracle_addresses):
        if len(vi.selected_oracles) == 0 or not \
                any(x.addr == oracle_addr and x.selectedInCurrentRound for x in vi.selected_oracles):
            msg = "%r : is not %s turn we are not in the current round selected oracles" % \
                  (self._coin_pair, oracle_addr)
            logger.info(msg)
            return False, msg

        conf = self._conf.oracle_turn_conf
        entering_fallback_sequence = self.get_fallback_sequence(conf.entering_fallbacks_amounts, len(vi.selected_oracles))

        # WARN if oracles won't get to publish before price expires
        ####################################
        if conf.trigger_valid_publication_blocks < len(entering_fallback_sequence) + 1:
            logger.warning("PRICE will EXPIRE before oracles get to publish. Check configuration.")
        ####################################

        start_block_pub_period_before_price_expires = vi.last_pub_block + \
                                                      vi.valid_price_period_in_blocks - \
                                                      conf.trigger_valid_publication_blocks

        if vi.block_num >= start_block_pub_period_before_price_expires:
            can_I_publish = self.can_oracle_publish(vi.block_num - start_block_pub_period_before_price_expires, oracle_addr, oracle_addresses, entering_fallback_sequence)
            if can_I_publish:
                msg = "%r : %s selected to publish before prices expires" % (self._coin_pair, oracle_addr)
                logger.info(msg)
                return True, msg
        
        blocks_since_price_change = self._price_changed_blocks(conf, vi, exchange_price)

        if blocks_since_price_change is None:
            msg = "%r : %s Price didn't change enough." % (self._coin_pair, oracle_addr)
            logger.info(msg)
            return False, msg

        if blocks_since_price_change <= conf.price_publish_blocks:
            msg = "%r : %s Price changed but still waiting to reach %r blocks to be allowed. %r < %r" % \
                  (self._coin_pair, oracle_addr, conf.price_publish_blocks, blocks_since_price_change, conf.price_publish_blocks)
            logger.warning(msg)
            return False, msg

        can_I_publish = self.can_oracle_publish(blocks_since_price_change - conf.price_publish_blocks, oracle_addr, oracle_addresses, entering_fallback_sequence)
        if can_I_publish:
            msg = "%r : %s selected to publish after price change. Blocks since price change: %s" % (self._coin_pair, oracle_addr, blocks_since_price_change)
            logger.info(msg)
            return True, msg

        msg = "%r : %s is NOT the chosen fallback %r" % (self._coin_pair, oracle_addr, blocks_since_price_change)
        logger.info(msg)
        return False, msg
