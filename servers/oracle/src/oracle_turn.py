import logging

from common import helpers
from common.services.oracle_dao import CoinPair, PriceWithTimestamp
from oracle.src import oracle_settings
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfo
from oracle.src.select_next import select_next

logger = logging.getLogger(__name__)


class OracleTurn:

    def __init__(self, coin_pair: CoinPair):
        self._price_fallback_delta = oracle_settings.ORACLE_PRICE_FALLBACK_DELTA_PCT
        self._price_fallback_blocks = oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS
        self._coin_pair = coin_pair
        self.price_change_block = -1
        self.price_change_pub_block = -1

    def price_changed_blocks(self, block_chain: OracleBlockchainInfo, exchange_price: PriceWithTimestamp):
        if block_chain.last_pub_block < 0 or block_chain.block_num < 0:
            raise Exception("%r : Invalid block number", self._coin_pair)

        # We already detected a price change before.
        if self.price_change_pub_block == block_chain.last_pub_block and self.price_change_block >= 0:
            logger.info(
                "%r : Price changed %r blocks ago" % (self._coin_pair, block_chain.block_num - self.price_change_block))
            return block_chain.block_num - self.price_change_block

        delta = helpers.price_delta(block_chain.blockchain_price, exchange_price.price)
        if delta < self._price_fallback_delta:
            logger.info("%r : We are not fallbacks and the price didn't change enough %r < %r,"
                        " blockchain price %r exchange price %r" %
                        (self._coin_pair, delta, self._price_fallback_delta,
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

    def is_oracle_turn(self, vi: OracleBlockchainInfo, oracle_addr, exchange_price: PriceWithTimestamp):
        return self.is_oracle_turn_with_msg(vi, oracle_addr, exchange_price)[0]

    def is_oracle_turn_with_msg(self, vi: OracleBlockchainInfo, oracle_addr, exchange_price: PriceWithTimestamp):
        if len(vi.selected_oracles) == 0 or not \
                any(x.addr == oracle_addr and x.selectedInCurrentRound for x in vi.selected_oracles):
            msg = "%r : is not %s turn we are not in the current round selected oracles" % \
                  (self._coin_pair, oracle_addr)
            logger.info(msg)
            return False, msg

        selection = select_next(vi.last_pub_block_hash, vi.selected_oracles)
        addrs = [x.addr for x in selection]
        selected = addrs.pop(0)
        # selected oracle can publish from f_block == 0
        if oracle_addr == selected:
            msg = "%r : selected chosen %s" % (self._coin_pair, oracle_addr)
            logger.info(msg)
            return True, msg

        f_block = self.price_changed_blocks(vi, exchange_price)
        if f_block is None:
            msg = "%r : is not %s turn there was no price change" % (self._coin_pair, oracle_addr)
            logger.info(msg)
            return False, msg

        # fallback oracles need to wait  self._price_fallback_blocks
        f_num = f_block - self._price_fallback_blocks
        if f_num < 0:
            msg = "%r : is not %s turn it is not a fallback and price changed %r blocks ago, this is less than %r" % \
                  (self._coin_pair, oracle_addr, f_block, self._price_fallback_blocks,)
            logger.info(msg)
            return False, msg

        try:
            f_idx = addrs.index(oracle_addr)
        except ValueError:
            msg = "%r : %s is not in the selected list for this round" % (self._coin_pair, oracle_addr)
            logger.info(msg)
            return False, msg

        if (f_idx * 3) > f_num:
            msg = "%r : is not %s turn it is not a secondary fallback %r %r %r" % \
                  (self._coin_pair, oracle_addr, f_block, f_num, f_idx)
            logger.info(msg)
            return False, msg

        logger.info("%r : fallback chosen %s  %r %r %r" % (self._coin_pair, oracle_addr, f_block, f_num, f_idx))
        return True, None