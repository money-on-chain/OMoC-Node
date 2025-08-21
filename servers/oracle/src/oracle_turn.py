import logging
import typing

from common import helpers
from common.helpers import MyCfgdLogger
from common.services.blockchain import to_short
from common.services.conditional_publish import ConditionalPublishServiceBase
from common.services.oracle_dao import CoinPair, PriceWithTimestamp, FullOracleRoundInfo
from common import settings
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
            raise Exception("%r : Invalid block number" % self._coin_pair)

        # We already detected a price change before.
        if self.price_change_pub_block == block_chain_info.last_pub_block and self.price_change_block >= 0:
            diff = block_chain_info.block_num - self.price_change_block
            self.debug(f"Price changed {diff} blocks ago ({block_chain_info.block_num}-{self.price_change_block})")
            return diff

        delta = helpers.price_delta(block_chain_info.blockchain_price, exchange_price.price)
        threshold_delta = signal.get_price_delta(conf.price_delta_pct)
        if delta < threshold_delta:
            self.debug("We are not fall backs and/or the price didn't change enough %r < %r,"
                       " blockchain price %r exchange price %r" %
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

    # Called by coin_pair_price_loop
    def is_oracle_turn(self, vi: OracleBlockchainInfo, oracle_addr,
                       exchange_price: PriceWithTimestamp):
        
        oracle_addresses = select_next_addresses(vi.last_pub_block_hash,
                                                 vi.selected_oracles)

        (is_my_turn, msg) = self._is_oracle_turn_with_msg(vi, oracle_addr,
            exchange_price, oracle_addresses,
            only_chosen=settings.DISABLE_FALLBACKS)

        return is_my_turn, [str(x) for x in oracle_addresses]

    def _is_oracle_turn_with_msg(self,
                                 vi: OracleBlockchainInfo,
                                 oracle_addr,
                                 exchange_price: PriceWithTimestamp,
                                 oracle_addresses,
                                 only_chosen=False):
        if not self.is_oracle_selected_in_round(vi.selected_oracles, oracle_addr):
            return False, self.info(f"is not {oracle_addr} turn we are not in the current round selected oracles")

        conf = self._conf.get_oracle_turn_conf(self._coin_pair)
        
        # Log oracle order calculation (L2) for synchronization validation
        self.info(f"ORACLE_ORDER_L2: block_hash={vi.last_pub_block_hash[:10]}... "
                  f"selected_count={len(vi.selected_oracles)} "
                  f"calculated_order={[to_short(addr) for addr in oracle_addresses]} "
                  f"primary_oracle={to_short(oracle_addresses[0]) if oracle_addresses else 'None'}")
        
        entering_fallback_sequence = self.get_fallback_sequence(
            conf.entering_fallbacks_amounts, len(vi.selected_oracles))
        
        # Log configuration validation for cross-node comparison
        self.info(f"CONFIG_VALIDATION: entering_fallbacks_amounts={list(conf.entering_fallbacks_amounts)} "
                  f"price_publish_blocks={conf.price_publish_blocks} "
                  f"price_delta_pct={conf.price_delta_pct} "
                  f"trigger_valid_publication_blocks={conf.trigger_valid_publication_blocks} "
                  f"fallback_sequence={entering_fallback_sequence}")

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

        blocks_since_price_change = self.price_follower.price_changed_blocks(
            conf, vi, exchange_price, self._signal)

        start_block_pub_period_before_price_expires = (
            vi.last_pub_block
            - conf.trigger_valid_publication_blocks
            + self._signal.get_valid_price_period(
                vi.valid_price_period_in_blocks)
        )

        # If the last online or offline block is higher than the start block
        # of the publication period before the price expires, we set it to that
        # block number so that we can check if the oracle can publish before
        # the price expires.
        # This is to ensure that we are not trying to publish before the price
        # expires, which could lead to multiple oracles publishing without a price change.
        last_online_block = self._signal.last_online_block()
        last_offline_block = self._signal.last_offline_block()
        
        if last_online_block > start_block_pub_period_before_price_expires:
            start_block_pub_period_before_price_expires = last_online_block

        if last_offline_block > start_block_pub_period_before_price_expires:
            start_block_pub_period_before_price_expires = last_offline_block

        self.debug(f"block_num {vi.block_num}  "
                   f"start_block_pub_period_before_price_expires {start_block_pub_period_before_price_expires} "
                   f"trigger_valid_publication_blocks {conf.trigger_valid_publication_blocks}"
                   f"vi.valid_price_period_in_blocks {vi.valid_price_period_in_blocks} "
                   f"f={self._signal.get_valid_price_period(vi.valid_price_period_in_blocks)}")
        
        if vi.block_num >= start_block_pub_period_before_price_expires:
            
            can_I_publish = self.can_oracle_publish(
                vi.block_num - start_block_pub_period_before_price_expires,
                oracle_addr,
                oracle_addresses,
                entering_fallback_sequence,
                only_chosen=only_chosen
            )
            
            if can_I_publish:
                return True, self.debug(
                    f"I'm selected to publish before prices expires"
                )

        if blocks_since_price_change is None:
            return False, self.debug(f"{oracle_addr} Price didn't change enough.")

        if blocks_since_price_change < conf.price_publish_blocks:
            return False, self.warning("%s Price changed but still waiting to reach %r blocks to be allowed. %r < %r" %
                        (oracle_addr, conf.price_publish_blocks, blocks_since_price_change, conf.price_publish_blocks))

        can_I_publish = self.can_oracle_publish(blocks_since_price_change - conf.price_publish_blocks,
                                                oracle_addr, oracle_addresses, entering_fallback_sequence,
                                                only_chosen=only_chosen)
        if can_I_publish:
            return True, self.info(f"{oracle_addr} selected to pub after $ change. "
                                   f"Blocks since change: {blocks_since_price_change}  ({conf.price_publish_blocks})")
        return False, self.info(f" {oracle_addr} is NOT the chosen fallback {blocks_since_price_change} "
                                f" ({conf.price_publish_blocks})")

    @staticmethod
    def is_selected_oracle(oracle_addresses, oracle_addr):
        return oracle_addresses[0] == oracle_addr

    @staticmethod
    def get_fallback_sequence(entering_fallbacks_amounts, selected_oracles_len):
        """
        Calculate the fallback sequence that determines how many fallback oracles
        are enabled at each block since publication is allowed.
        
        The sequence works as follows:
        - Index 0 (0 blocks since allowed): Only 1 oracle enabled (primary)
        - Index 1 (1 block since allowed): entering_fallbacks_amounts[0] + 1 oracles enabled  
        - Index 2 (2 blocks since allowed): entering_fallbacks_amounts[1] + 1 oracles enabled
        - And so on...
        
        Args:
            entering_fallbacks_amounts: Configuration bytes defining fallback progression
            selected_oracles_len: Total number of selected oracles in the round
            
        Returns:
            list: Sequence where index=blocks_since_allowed, value=num_oracles_enabled
        """
        # x + 1 so that when it's being used as index for the addresses' list,
        # it can get the x addresses after the first one (the chosen oracle)
        entering_fallback_sequence = [x + 1 for x in entering_fallbacks_amounts]
        # Insert amount 1 at the beginning that it will be fetched by index 0 of 0 blocks since price change
        # so that 0 fallbacks are chosen. See selected_fallbacks variable assignment.
        entering_fallback_sequence.insert(0, 1)
        if len(entering_fallback_sequence) == 0 or entering_fallback_sequence[-1] < selected_oracles_len:
            entering_fallback_sequence.append(selected_oracles_len)
        return entering_fallback_sequence
    
    def get_fallback_debug_info(self, vi: OracleBlockchainInfo, oracle_addresses):
        """
        Generate detailed debug information about the current fallback state.
        This can be used for comparing fallback sequence state between oracles.
        
        Args:
            vi: Oracle blockchain information
            oracle_addresses: Ordered list of oracle addresses
            
        Returns:
            dict: Debug information including sequence, enabled oracles, etc.
        """
        conf = self._conf.get_oracle_turn_conf(self._coin_pair)
        entering_fallback_sequence = self.get_fallback_sequence(
            conf.entering_fallbacks_amounts, len(vi.selected_oracles))
        
        debug_info = {
            'block_hash': vi.last_pub_block_hash,
            'oracle_order_L2': [to_short(addr) for addr in oracle_addresses],
            'primary_oracle': to_short(oracle_addresses[0]) if oracle_addresses else None,
            'fallback_sequence': entering_fallback_sequence,
            'config': {
                'entering_fallbacks_amounts': list(conf.entering_fallbacks_amounts),
                'price_publish_blocks': conf.price_publish_blocks,
                'price_delta_pct': conf.price_delta_pct,
                'trigger_valid_publication_blocks': conf.trigger_valid_publication_blocks
            },
            'selected_oracles_count': len(vi.selected_oracles),
            'fallback_scenarios': []
        }
        
        # Calculate fallback states for different block scenarios
        for blocks_since in range(min(10, len(entering_fallback_sequence))):
            if blocks_since < len(entering_fallback_sequence):
                num_enabled = entering_fallback_sequence[blocks_since]
                enabled_oracles = oracle_addresses[:num_enabled]
            else:
                num_enabled = entering_fallback_sequence[-1]
                enabled_oracles = oracle_addresses[:num_enabled]
                
            debug_info['fallback_scenarios'].append({
                'blocks_since_allowed': blocks_since,
                'num_oracles_enabled': num_enabled,
                'enabled_oracles': [to_short(addr) for addr in enabled_oracles]
            })
        
        return debug_info
    
    def validate_configuration_consistency(self, expected_config=None):
        """
        Validate that configuration parameters are properly set and optionally
        compare against expected values for cross-node consistency checking.
        
        Args:
            expected_config: Optional dict with expected configuration values
            
        Returns:
            dict: Validation results with any inconsistencies or warnings
        """
        conf = self._conf.get_oracle_turn_conf(self._coin_pair)
        validation_results = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'config_values': {
                'entering_fallbacks_amounts': list(conf.entering_fallbacks_amounts),
                'price_publish_blocks': conf.price_publish_blocks,
                'price_delta_pct': conf.price_delta_pct,
                'trigger_valid_publication_blocks': conf.trigger_valid_publication_blocks
            }
        }
        
        # Basic validation
        if not conf.entering_fallbacks_amounts:
            validation_results['errors'].append("entering_fallbacks_amounts is empty")
            validation_results['valid'] = False
            
        if conf.price_publish_blocks < 0:
            validation_results['errors'].append("price_publish_blocks must be >= 0")
            validation_results['valid'] = False
            
        if conf.price_delta_pct <= 0:
            validation_results['errors'].append("price_delta_pct must be > 0")
            validation_results['valid'] = False
            
        # Check for potential configuration issues
        if conf.trigger_valid_publication_blocks <= len(conf.entering_fallbacks_amounts):
            validation_results['warnings'].append(
                f"trigger_valid_publication_blocks ({conf.trigger_valid_publication_blocks}) "
                f"may be too low compared to fallback sequence length ({len(conf.entering_fallbacks_amounts)})")
        
        # Compare with expected config if provided
        if expected_config:
            for key, expected_value in expected_config.items():
                actual_value = validation_results['config_values'].get(key)
                if actual_value != expected_value:
                    validation_results['errors'].append(
                        f"Config mismatch for {key}: expected {expected_value}, got {actual_value}")
                    validation_results['valid'] = False
        
        # Log validation results
        if validation_results['valid']:
            self.info(f"CONFIG_VALIDATION_PASSED: {validation_results['config_values']}")
        else:
            self.error(f"CONFIG_VALIDATION_FAILED: {validation_results}")
            
        for warning in validation_results['warnings']:
            self.warning(f"CONFIG_WARNING: {warning}")
            
        return validation_results

    def can_oracle_publish(self, blocks_since_pub_is_allowed, oracle_addr,
                           oracle_addresses, entering_fallback_sequence,
                           only_chosen=False):
        """
        Determines if an oracle can publish based on fallback sequence logic.
        
        Args:
            blocks_since_pub_is_allowed: Number of blocks since publication became allowed
            oracle_addr: Address of the oracle being checked
            oracle_addresses: Ordered list of oracle addresses (L2 order)
            entering_fallback_sequence: Sequence defining how many fallbacks are enabled per block
            only_chosen: If True, only allow the primary chosen oracle to publish
            
        Returns:
            bool: True if oracle can publish, False otherwise
        """
        # Log detailed fallback sequence state for debugging and synchronization validation
        self.info(f"FALLBACK_STATE_CHECK: oracle={to_short(oracle_addr)} "
                  f"blocks_since_allowed={blocks_since_pub_is_allowed} "
                  f"oracle_order={[to_short(addr) for addr in oracle_addresses]} "
                  f"sequence={entering_fallback_sequence} "
                  f"only_chosen={only_chosen}")

        if OracleTurn.is_selected_oracle(oracle_addresses, oracle_addr):
            self.info(f"PRIMARY_ORACLE_SELECTED: {to_short(oracle_addr)} is the chosen primary oracle")
            return True

        # Calculate fallback index based on blocks since publication is allowed
        # This uses blocks_since_pub_is_allowed as index into the fallback sequence
        # to determine how many fallback oracles are enabled
        condition = (
            (blocks_since_pub_is_allowed is not None) and
            (blocks_since_pub_is_allowed < len(entering_fallback_sequence))
        )

        if condition:
            entering_fallback_sequence_index = blocks_since_pub_is_allowed
        else:
            entering_fallback_sequence_index = len(entering_fallback_sequence) - 1

        # Calculate which oracles are enabled as fallbacks at this point
        num_fallbacks_enabled = entering_fallback_sequence[entering_fallback_sequence_index]
        selected_fallbacks = oracle_addresses[1:num_fallbacks_enabled]
        is_fallback = oracle_addr in selected_fallbacks        

        # Enhanced logging for fallback sequence validation
        self.info(f"FALLBACK_CALCULATION: blocks_since_allowed={blocks_since_pub_is_allowed} "
                  f"sequence_index={entering_fallback_sequence_index} "
                  f"fallbacks_enabled_count={num_fallbacks_enabled} "
                  f"enabled_fallbacks={[to_short(addr) for addr in selected_fallbacks]} "
                  f"oracle_is_enabled_fallback={is_fallback} "
                  f"index_condition_met={condition}")

        if not is_fallback:
            self.info(f"ORACLE_NOT_FALLBACK: {to_short(oracle_addr)} is not in enabled fallbacks at this time")
            return False
        
        if only_chosen:
            self.info(f"FALLBACKS_DISABLED: {to_short(oracle_addr)} is enabled fallback but fallbacks are disabled")
            return False

        self.info(f"FALLBACK_ORACLE_ENABLED: {to_short(oracle_addr)} is enabled as fallback oracle")
        return True

    @staticmethod
    def is_oracle_selected_in_round(selected_oracles: typing.List[FullOracleRoundInfo], oracle_addr):
        return len(selected_oracles) != 0 and \
               oracle_addr in [x.addr for x in selected_oracles] and \
               not any(x.addr == oracle_addr and not x.selectedInCurrentRound for x in selected_oracles)
