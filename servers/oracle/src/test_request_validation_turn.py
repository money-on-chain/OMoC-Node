import pytest
from starlette.datastructures import Secret

from common.ganache_accounts import GANACHE_ACCOUNTS
from common.services.blockchain import BlockchainAccount
from common.services.oracle_dao import CoinPair, PriceWithTimestamp, FullOracleRoundInfo
from oracle.src import oracle_settings
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfo
from oracle.src.oracle_configuration import OracleTurnConfiguration
from oracle.src.oracle_publish_message import PublishPriceParams
from oracle.src.oracle_turn import OracleTurn
from oracle.src.request_validation import RequestValidation, InvalidTurn

oracle_settings.ORACLE_PRICE_DELTA_PCT = 0.05
oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS = 1
oracle_settings.ORACLE_ENTERING_FALLBACKS_AMOUNTS = b'\x02\x04\x06\x08\n'
oracle_settings.ORACLE_TRIGGER_VALID_PUBLICATION_BLOCKS = 30


class OracleConf:
    @property
    def oracle_turn_conf(self):
        return OracleTurnConfiguration(oracle_settings.ORACLE_PRICE_DELTA_PCT,
                                       oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS,
                                       oracle_settings.ORACLE_ENTERING_FALLBACKS_AMOUNTS,
                                       oracle_settings.ORACLE_TRIGGER_VALID_PUBLICATION_BLOCKS)


oracleConf = OracleConf()

valid_price_period_in_blocks = 60

cp = CoinPair("BTCUSD")
price_ts_utc = 1
version = 1

accounts = [BlockchainAccount(x[0], Secret(x[1])) for x in GANACHE_ACCOUNTS]

selected_oracles = [
    (accounts[1], 'http://127.0.0.1:24001', 14000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0),
    (accounts[2], 'http://127.0.0.1:24002', 14000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0),
    (accounts[3], 'http://127.0.0.1:24003', 14000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0),
    (accounts[4], 'http://127.0.0.1:24004', 8000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0),
    (accounts[5], 'http://127.0.0.1:24005', 2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0),
    (accounts[6], 'http://127.0.0.1:24006', 8000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0),
    (accounts[7], 'http://127.0.0.1:24007', 14000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0),
    (accounts[8], 'http://127.0.0.1:24008', 8000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0),
    (accounts[9], 'http://127.0.0.1:24009', 2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0)]


def rv(oracle_turn, running_oracle, params):
    publish_price = 124123
    # Validated elsewhere
    publish_last_pub_block = 3231213
    blockchain_price = 1023
    oracle_price_reject_delta_pct = 0.05
    exchange_price = blockchain_price * params["price_delta"]
    return RequestValidation(oracle_price_reject_delta_pct,
                             PublishPriceParams(version,
                                                cp,
                                                PriceWithTimestamp(publish_price, price_ts_utc),
                                                running_oracle[0].addr,
                                                publish_last_pub_block),
                             oracle_turn,
                             PriceWithTimestamp(exchange_price, price_ts_utc),
                             OracleBlockchainInfo(cp,
                                                  [FullOracleRoundInfo(x[0].addr, *x[1:]) for x in selected_oracles],
                                                  blockchain_price,
                                                  params["block_number"],
                                                  params["blockchain_last_pub_block"],
                                                  params["last_pub_block_hash"],
                                                  valid_price_period_in_blocks))


def can_publish(oracleTurn, params, is_idx):
    for i in is_idx:
        v = rv(oracleTurn, selected_oracles[i], params)
        v.validate_turn()
    is_not_idx = [x for x in range(len(selected_oracles)) if x not in is_idx]
    for i in is_not_idx:
        v = rv(oracleTurn, selected_oracles[i], params)
        with pytest.raises(InvalidTurn) as e:
            v.validate_turn()


# Test that with no price change the chosen oracle has his turn validated but not the fallbacks
def test_success_oracle_turn_no_price_change():
    oracleTurn = OracleTurn(oracleConf, cp)
    starting_block_num = 10
    params = {
        "block_number": starting_block_num,
        "price_delta": 1,
        "blockchain_last_pub_block": 1,
        "last_pub_block_hash": "0x000000000000000000"
    }

    # No price change. Only the CHOSEN oracle has its turn validated.
    can_publish(oracleTurn, params, [0])

    # (ORACLE_PRICE_PUBLISH_BLOCKS + 1) blocks pass and still
    # only the CHOSEN oracle has its turn validated.
    params["block_number"] = starting_block_num + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 1
    can_publish(oracleTurn, params, [0])


# Test after price change the chosen oracle and the fallbacks have their turn validated
# in their respective moments in terms of blocks
def test_success_oracle_turn_on_price_change():
    oracleTurn = OracleTurn(oracleConf, cp)
    starting_block_num = 10
    params = {
        "block_number": starting_block_num,
        "price_delta": 1,
        "blockchain_last_pub_block": 1,
        "last_pub_block_hash": "0x000000000000000000"
    }

    # Account zero is not in selected group
    v = rv(oracleTurn, (accounts[0],), params)
    with pytest.raises(InvalidTurn) as e:
        v.validate_turn()

    # No price change yet. Only the CHOSEN oracle has its turn validated.
    can_publish(oracleTurn, params, [0])

    # Price changes but still only the CHOSEN oracle has its turn validated.
    params["price_delta"] = 1.000000001 * oracleConf.oracle_turn_conf.price_delta_pct / 100
    can_publish(oracleTurn, params, [0])

    # ORACLE_PRICE_PUBLISH_BLOCKS blocks pass since price change and still
    # only the CHOSEN oracle has its turn validated.
    params["block_number"] = starting_block_num + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS
    can_publish(oracleTurn, params, [0])

    # (ORACLE_PRICE_PUBLISH_BLOCKS + 1) blocks pass since price change so now
    # the CHOSEN oracle and the next TWO fallbacks have their turn validated.
    params["block_number"] = starting_block_num + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 1
    can_publish(oracleTurn, params, [0, 1, 2])

    # (ORACLE_PRICE_PUBLISH_BLOCKS + 2) blocks pass since price change so now
    # the CHOSEN oracle and the next FOUR fallbacks have their turn validated.
    params["block_number"] = starting_block_num + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 2
    can_publish(oracleTurn, params, [0, 1, 2, 3, 4])

    # (ORACLE_PRICE_PUBLISH_BLOCKS + 3) blocks pass since price change so now
    # the CHOSEN oracle and the next SIX fallbacks have their turn validated.
    params["block_number"] = starting_block_num + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 3
    can_publish(oracleTurn, params, [0, 1, 2, 3, 4, 5, 6])

    # (ORACLE_PRICE_PUBLISH_BLOCKS + 4) blocks pass since price change so now
    # the CHOSEN oracle and the next EIGHT fallbacks have their turn validated.
    params["block_number"] = starting_block_num + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 4
    can_publish(oracleTurn, params, [0, 1, 2, 3, 4, 5, 6, 7, 8])


# If price doesn't change, the chosen oracle and fallback 
# should have the oportunity to publish before price expires
def test_is_oracle_turn_oracles_publish_before_price_expiration():
    oracleTurn = OracleTurn(oracleConf, cp)

    starting_block_num = 10
    params = {
        "block_number": starting_block_num,
        "price_delta": 1,
        "blockchain_last_pub_block": 1,
        "last_pub_block_hash": "0x000000000000000000"
    }

    last_pub_block = 1
    start_block_pub_period_before_price_expires = last_pub_block + \
                                                  valid_price_period_in_blocks - \
                                                  oracleConf.oracle_turn_conf.trigger_valid_publication_blocks

    block_num_list_for_exp_period = [
        start_block_pub_period_before_price_expires - 1,
        start_block_pub_period_before_price_expires,
        start_block_pub_period_before_price_expires + 1,
        start_block_pub_period_before_price_expires + 2,
        start_block_pub_period_before_price_expires + 3,
        start_block_pub_period_before_price_expires + 4,
        start_block_pub_period_before_price_expires + 5,
        start_block_pub_period_before_price_expires + 6
    ]

    # No price change. Only the CHOSEN oracle has its turn validated.
    can_publish(oracleTurn, params, [0])

    # Not yet the starting block of period before price expires.
    # Only the CHOSEN oracle has its turn validated.
    params["block_number"] = block_num_list_for_exp_period[0]
    can_publish(oracleTurn, params, [0])

    # Reached the starting block of period before price expires.
    # Fallbacks don't have their turn validated yet.
    params["block_number"] = block_num_list_for_exp_period[1]
    can_publish(oracleTurn, params, [0])

    # 1 block has passed since the starting block of period before price expires.
    # Only the first oracle and the next TWO fallbacks should have their turn validated.
    params["block_number"] = block_num_list_for_exp_period[2]
    can_publish(oracleTurn, params, [0, 1, 2])

    # 2 blocks have passed since the starting block of period before price expires.
    # Only the first oracle and the next FOUR fallbacks should have their turn validated.
    params["block_number"] = block_num_list_for_exp_period[3]
    can_publish(oracleTurn, params, [0, 1, 2, 3, 4])

    # 3 blocks have passed since the starting block of period before price expires.
    # Only the first oracle and the next SIX fallbacks should have their turn validated.
    params["block_number"] = block_num_list_for_exp_period[4]
    can_publish(oracleTurn, params, [0, 1, 2, 3, 4, 5, 6])

    # 4 blocks have passed since the starting block of period before price expires.
    # Only the first oracle and the next EIGHT fallbacks should have their turn validated.
    params["block_number"] = block_num_list_for_exp_period[5]
    can_publish(oracleTurn, params, [0, 1, 2, 3, 4, 5, 6, 7, 8])


def test_fail_if_invalid_price():
    # This class monitors the publication block an the price change block
    # if we don't change any of those, the internal state doesn't change
    oracleTurn = OracleTurn(oracleConf, cp)
    params = {
        "block_number": 1,
        "price_delta": 1,
        "blockchain_last_pub_block": 10,
        "last_pub_block_hash": "0x000000000000000000"}
    can_publish(oracleTurn, params, [0])
    params["blockchain_price"] = 12
    can_publish(oracleTurn, params, [0])
