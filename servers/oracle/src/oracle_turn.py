import logging

from common import helpers
from common.services.oracle_dao import CoinPair, PriceWithTimestamp
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfo
from oracle.src.oracle_configuration import OracleTurnConfiguration
from oracle.src.select_next import select_next

logger = logging.getLogger(__name__)


class OracleTurn:

    def __init__(self, conf: OracleTurnConfiguration, coin_pair: CoinPair):
        self._conf: OracleTurnConfiguration = conf
        self._coin_pair: CoinPair = coin_pair
        self.price_change_block = -1
        self.price_change_pub_block = -1

    # Called by /sign endpoint
    def validate_turn(self, vi: OracleBlockchainInfo, oracle_addr, exchange_price: PriceWithTimestamp):
        return self._is_oracle_turn_with_msg(vi, oracle_addr, exchange_price)

    # Called byt coin_pair_price_loop
    def is_oracle_turn(self, vi: OracleBlockchainInfo, oracle_addr, exchange_price: PriceWithTimestamp):
        (is_my_turn, msg) = self._is_oracle_turn_with_msg(vi, oracle_addr, exchange_price)
        return is_my_turn

    def _price_changed_blocks(self, block_chain: OracleBlockchainInfo, exchange_price: PriceWithTimestamp):
        if block_chain.last_pub_block < 0 or block_chain.block_num < 0:
            raise Exception("%r : Invalid block number", self._coin_pair)

        # We already detected a price change before.
        if self.price_change_pub_block == block_chain.last_pub_block and self.price_change_block >= 0:
            logger.info(
                "%r : Price changed %r blocks ago" % (self._coin_pair, block_chain.block_num - self.price_change_block))
            return block_chain.block_num - self.price_change_block

        delta = helpers.price_delta(block_chain.blockchain_price, exchange_price.price)
        if delta < self._conf.price_fallback_delta_pct:
            logger.info("%r : We are not fallbacks and/or the price didn't change enough %r < %r,"
                        " blockchain price %r exchange price %r" %
                        (self._coin_pair, delta, self._conf.price_fallback_delta_pct,
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

    def _is_oracle_turn_with_msg(self, vi: OracleBlockchainInfo, oracle_addr, exchange_price: PriceWithTimestamp):
        if len(vi.selected_oracles) == 0 or not \
                any(x.addr == oracle_addr and x.selectedInCurrentRound for x in vi.selected_oracles):
            msg = "%r : is not %s turn we are not in the current round selected oracles" % \
                  (self._coin_pair, oracle_addr)
            logger.info(msg)
            return False, msg

        ordered_oracle_selection = select_next(self._conf.stake_limit_multiplicator,
                                               vi.last_pub_block_hash,
                                               vi.selected_oracles)
        oracle_addrs = [x.addr for x in ordered_oracle_selection]

        selected_oracle = oracle_addrs[0]

        f_block = self._price_changed_blocks(vi, exchange_price)

        entering_fallback_sequence = [x for x in self._conf.entering_fallbacks_amounts]

        # Gets blocks since price changed from f_block and uses it as index in the amount of entering fallbacks sequence.
        # Makes sure the index is within range of the list.
        entering_fallback_sequence_index = f_block if f_block < len(entering_fallback_sequence) else len(entering_fallback_sequence) - 1
        selected_fallbacks = oracle_addrs[1:entering_fallback_sequence[entering_fallback_sequence_index]]

        if oracle_addr == selected_oracle:
            if f_block is not None and f_block < self._conf.price_publish_blocks:
                msg = "%r : %s I'm selected but still waiting for %r blocks to pass to be allowed. %r < %r" % \
                      (self._coin_pair, oracle_addr, self._conf.price_publish_blocks, f_block, self._conf.price_publish_blocks)
                logger.warning(msg)
                return False, msg
            elif f_block is None:
                msg = "%r : %s I'm selected but still waiting for price change blocks" % \
                      (self._coin_pair, oracle_addr)
                logger.warning(msg)
                is_my_turn_before_price_expiration = self.is_selected_turn_before_price_expiration(oracle_addr,
                                                                                                   vi,
                                                                                                   oracle_addrs,
                                                                                                   entering_fallback_sequence)
                msg_on_price_expiration = ("%r : %s I'm selected without a price change before it expires" % \
                                          (self._coin_pair, oracle_addr)) if is_my_turn_before_price_expiration else ("%r : %s I'm NOT selected without a price change before it expires" % \
                                          (self._coin_pair, oracle_addr))
                logger.warning(msg_on_price_expiration)
                return is_my_turn_before_price_expiration, msg_on_price_expiration
            else:
                msg = "%r : %s is the selected oracle" % (self._coin_pair, oracle_addr)
                logger.info(msg)
                return True, msg
        elif oracle_addr in selected_fallbacks:
            if f_block is not None and f_block < self._conf.price_fallback_blocks:
                msg = "%r : it's not fallback %s turn, as the price changed %r blocks ago, this is less than %r" % \
                      (self._coin_pair, oracle_addr, f_block, self._conf.price_fallback_blocks)
                logger.info(msg)
                return False, msg
            elif f_block is None:
                msg = "%r : %s I'm a selected fallback but still waiting for price change blocks" % \
                      (self._coin_pair, oracle_addr)
                logger.warning(msg)
                is_my_turn_before_price_expiration = self.is_selected_turn_before_price_expiration(oracle_addr,
                                                                                                   vi,
                                                                                                   oracle_addrs,
                                                                                                   entering_fallback_sequence)
                msg_on_price_expiration = ("%r : %s I'm selected without a price change before it expires" % \
                                          (self._coin_pair, oracle_addr)) if is_my_turn_before_price_expiration else ("%r : %s I'm NOT selected without a price change before it expires" % \
                                          (self._coin_pair, oracle_addr))
                logger.warning(msg_on_price_expiration)
                return is_my_turn_before_price_expiration, msg_on_price_expiration
            else:
                msg = "%r : %s is the chosen fallback %r" % (self._coin_pair, oracle_addr, f_block)
                logger.info(msg)
                return True, msg
        else:
            msg = "%r : %s is NOT the chosen fallback %r" % (self._coin_pair, oracle_addr, f_block)
            logger.info(msg)
            return False, msg

    def is_selected_turn_before_price_expiration(self,
                                                 oracle_address,
                                                 vi: OracleBlockchainInfo,
                                                 oracle_addrs,
                                                 entering_oracles_sequence):
        # Appends the chosen oracle to the beginning of sequence
        entering_oracles_sequence.insert(0, 1)
        
        # Warn if trigger_valid_publication_blocks param is lower than period it takes for oracles to definitely publish.
        ######################################
        total_oracle_amount = len(oracle_addrs)
        oracles_accumulated = 0
        block_count = 0

        for i in entering_oracles_sequence:
            if (oracles_accumulated >= total_oracle_amount):
                minimum_successful_publication_period_blocks = block_count
                break
            oracles_accumulated += i
            block_count += 1

        if (vi.trigger_valid_publication_blocks < minimum_successful_publication_period_blocks):
            logger.warning("trigger_valid_publication_blocks parameter SHOULD BE HIGHER than period it takes for chosen and fallback oracles to publish")
        #######################################

        is_selected_turn = False

        start_block_pub_period_before_price_expires = self.price_change_pub_block + vi.valid_price_period_in_blocks - self._conf.trigger_valid_publication_blocks

        current_block_in_blocks_after_pub_period_start = vi.block_num - start_block_pub_period_before_price_expires

        # If current block isn't in valid publication period, it is not the oracle's turn
        if (current_block_in_blocks_after_pub_period_start < 0):
            logger.info("It's NOT my turn because valid publication period hasn't arrived yet.")
            return is_selected_turn
        else:
            for i in range(current_block_in_blocks_after_pub_period_start):
                if (i < len(entering_oracles_sequence)):
                    accumulated_oracles += entering_oracles_sequence[i]
                else:
                    break
            if (oracle_address in oracle_addrs[:accumulated_oracles]):
                is_selected_turn = True
        
        return is_selected_turn
