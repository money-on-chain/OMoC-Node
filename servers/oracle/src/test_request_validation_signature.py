import pytest
from starlette.datastructures import Secret

from common import crypto
from common.ganache_accounts import GANACHE_ACCOUNTS
from common.services.blockchain import BlockchainAccount
from common.services.oracle_dao import CoinPair, PriceWithTimestamp, FullOracleRoundInfo
from oracle.src import oracle_settings
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfo
from oracle.src.oracle_configuration import OracleTurnConfiguration
from oracle.src.oracle_publish_message import PublishPriceParams
from oracle.src.oracle_turn import OracleTurn
from oracle.src.request_validation import RequestValidation, ValidationFailure, InvalidTurn

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
starting_block_num = 10

conf = oracleConf.oracle_turn_conf

cp = CoinPair("BTCUSD")
price_ts_utc = 1
version = 1

accounts = [BlockchainAccount(x[0], Secret(x[1])) for x in GANACHE_ACCOUNTS]

selected_oracles = [
    FullOracleRoundInfo(accounts[0].addr, 'http://127.0.0.1:24000',
                        14000000000000000000,
                        '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True, 0),
    FullOracleRoundInfo(accounts[1].addr, 'http://127.0.0.1:24001',
                        8000000000000000000,
                        '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True, 0),
    FullOracleRoundInfo(accounts[2].addr, 'http://127.0.0.1:24002',
                        2000000000000000000,
                        '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True, 0),
    FullOracleRoundInfo(accounts[3].addr, 'http://127.0.0.1:24003',
                        8000000000000000000,
                        '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True, 0),
    FullOracleRoundInfo(accounts[4].addr, 'http://127.0.0.1:24004',
                        2000000000000000000,
                        '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True, 0),
    FullOracleRoundInfo(accounts[5].addr, 'http://127.0.0.1:24005',
                        8000000000000000000,
                        '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True, 0),
    FullOracleRoundInfo(accounts[6].addr, 'http://127.0.0.1:24006',
                        2000000000000000000,
                        '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True, 0),
    FullOracleRoundInfo(accounts[7].addr, 'http://127.0.0.1:24007',
                        8000000000000000000,
                        '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True, 0),
    FullOracleRoundInfo(accounts[8].addr, 'http://127.0.0.1:24008',
                        2000000000000000000,
                        '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True, 0)]



@pytest.fixture
def mock_select_next(monkeypatch):
    """select_next.select_next mocked to the selected_oracles order"""

    def mock(*args, **kwargs):
        return selected_oracles

    monkeypatch.setattr("oracle.src.select_next.select_next", mock)


def get_request_validation(oracle_turn, oracle_account, params):
    publish_price = 1023
    blockchain_price = publish_price
    exchange_price = blockchain_price * params["price_delta"]
    # print("price_delta")
    # print(params["price_delta"])
    # print("blockchain_price")
    # print(blockchain_price)
    # print("exchange_price")
    # print(exchange_price)
    publish_last_pub_block = 1
    oracle_price_reject_delta_pct = 50
    publish_price_params = PublishPriceParams(version,
                                              cp,
                                              PriceWithTimestamp(publish_price, price_ts_utc),
                                              oracle_account.addr,
                                              publish_last_pub_block)
    return RequestValidation(oracle_price_reject_delta_pct,
                             publish_price_params,
                             oracle_turn,
                             PriceWithTimestamp(exchange_price, price_ts_utc),
                             OracleBlockchainInfo(cp,
                                                  selected_oracles,
                                                  blockchain_price,
                                                  params["block_number"],
                                                  params["blockchain_last_pub_block"],
                                                  params["last_pub_block_hash"],
                                                  valid_price_period_in_blocks))


def can_validate_and_sign(oracle_turn, params, is_idx):
    for i in is_idx:
        request_validation = get_request_validation(oracle_turn, selected_oracles[i], params)
        msg, signtr = sign(accounts[i], request_validation)
        message, signature = request_validation.validate_and_sign(signtr)
        assert message == msg
        signature2 = crypto.sign_message(hexstr="0x" + msg,
                                         account=oracle_settings.get_oracle_account())
        assert signature == signature2
    is_not_idx = [x for x in range(len(selected_oracles)) if x not in is_idx]
    for i in is_not_idx:
        request_validation = get_request_validation(oracle_turn, selected_oracles[i], params)
        msg, signtr = sign(accounts[i], request_validation)
        with pytest.raises(InvalidTurn) as e:
            request_validation.validate_and_sign(signtr)


def sign(oracle_account, request_validation: RequestValidation):
    message = request_validation.params.prepare_price_msg()
    signature = crypto.sign_message(hexstr="0x" + message,
                                    account=oracle_account)
    return message, signature


def test_validate_sig_success(mock_select_next):
    oracle_turn = OracleTurn(oracleConf, cp)
    params = {
        "block_number": starting_block_num,
        "price_delta": 1,
        "blockchain_last_pub_block": 1,
        "last_pub_block_hash": "0x000000000000000000"
    }
    request_validation = get_request_validation(oracle_turn, accounts[3], params)
    msg, signature = sign(accounts[3], request_validation)
    request_validation.validate_signature(msg, signature)


def test_validate_sig_failure(mock_select_next):
    oracle_turn = OracleTurn(oracleConf, cp)
    params = {
        "block_number": starting_block_num,
        "price_delta": 1,
        "blockchain_last_pub_block": 1,
        "last_pub_block_hash": "0x000000000000000000"
    }
    request_validation = get_request_validation(oracle_turn, accounts[3], params)
    msg, signature = sign(accounts[0], request_validation)
    with pytest.raises(ValidationFailure) as e:
        request_validation.validate_signature(msg, signature)


def test_success_with_signature(mock_select_next):
    oracle_turn = OracleTurn(oracleConf, cp)
    params = {
        "block_number": starting_block_num,
        "price_delta": 1.5,
        "blockchain_last_pub_block": 1,
        "last_pub_block_hash": "0x000000000000000000"
    }
    request_validation = get_request_validation(oracle_turn, accounts[0], params)
    msg, signtr = sign(accounts[0], request_validation)

    request_validation.validate_params()
    request_validation.validate_turn()
    request_validation.validate_signature(msg, signtr)

    # this shouldn't throw
    message, signature = request_validation.validate_and_sign(signtr)
    assert message == msg

    signature2 = crypto.sign_message(hexstr="0x" + msg,
                                     account=oracle_settings.get_oracle_account())
    assert signature == signature2


# Test that with no price change the chosen oracle has his turn validated but not the fallbacks
def test_success_validate_and_sign_no_price_change(mock_select_next):
    oracleTurn = OracleTurn(oracleConf, cp)
    starting_block_num = 10
    params = {
        "block_number": starting_block_num,
        "price_delta": 1,
        "blockchain_last_pub_block": 1,
        "last_pub_block_hash": "0x000000000000000000"
    }

    # No price change. Only the CHOSEN oracle has its turn validated.
    can_validate_and_sign(oracleTurn, params, [0])

    # (ORACLE_PRICE_PUBLISH_BLOCKS + 1) blocks pass and still
    # only the CHOSEN oracle has its turn validated.
    params["block_number"] = starting_block_num + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 1
    can_validate_and_sign(oracleTurn, params, [0])


# Test after price change the chosen oracle and the fallbacks have their turn validated
# in their respective moments in terms of blocks
def test_success_validate_and_sign_on_price_change(mock_select_next):
    oracleTurn = OracleTurn(oracleConf, cp)
    starting_block_num = 10
    params = {
        "block_number": starting_block_num,
        "price_delta": 1,
        "blockchain_last_pub_block": 1,
        "last_pub_block_hash": "0x000000000000000000"
    }

    # No price change yet. Only the CHOSEN oracle has its turn validated.
    can_validate_and_sign(oracleTurn, params, [0])

    # Price changes but still only the CHOSEN oracle has its turn validated.
    params["price_delta"] = 1.000000001 + oracleConf.oracle_turn_conf.price_delta_pct / 100
    can_validate_and_sign(oracleTurn, params, [0])

    # ORACLE_PRICE_PUBLISH_BLOCKS blocks pass since price change and still
    # only the CHOSEN oracle has its turn validated.
    params["block_number"] = starting_block_num + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS
    can_validate_and_sign(oracleTurn, params, [0])

    # (ORACLE_PRICE_PUBLISH_BLOCKS + 1) blocks pass since price change so now
    # the CHOSEN oracle and the next TWO fallbacks have their turn validated.
    params["block_number"] = starting_block_num + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 1
    can_validate_and_sign(oracleTurn, params, [0, 1, 2])

    # (ORACLE_PRICE_PUBLISH_BLOCKS + 2) blocks pass since price change so now
    # the CHOSEN oracle and the next FOUR fallbacks have their turn validated.
    params["block_number"] = starting_block_num + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 2
    can_validate_and_sign(oracleTurn, params, [0, 1, 2, 3, 4])

    # (ORACLE_PRICE_PUBLISH_BLOCKS + 3) blocks pass since price change so now
    # the CHOSEN oracle and the next SIX fallbacks have their turn validated.
    params["block_number"] = starting_block_num + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 3
    can_validate_and_sign(oracleTurn, params, [0, 1, 2, 3, 4, 5, 6])

    # (ORACLE_PRICE_PUBLISH_BLOCKS + 4) blocks pass since price change so now
    # the CHOSEN oracle and the next EIGHT fallbacks have their turn validated.
    params["block_number"] = starting_block_num + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 4
    can_validate_and_sign(oracleTurn, params, [0, 1, 2, 3, 4, 5, 6, 7, 8])


# If price doesn't change, the chosen oracle and fallback 
# should have the oportunity to publish before price expires
def test_validate_and_sign_oracles_publish_before_price_expiration(mock_select_next):
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
    can_validate_and_sign(oracleTurn, params, [0])

    # Not yet the starting block of period before price expires.
    # Only the CHOSEN oracle has its turn validated.
    params["block_number"] = block_num_list_for_exp_period[0]
    can_validate_and_sign(oracleTurn, params, [0])

    # Reached the starting block of period before price expires.
    # Fallbacks don't have their turn validated yet.
    params["block_number"] = block_num_list_for_exp_period[1]
    can_validate_and_sign(oracleTurn, params, [0])

    # 1 block has passed since the starting block of period before price expires.
    # Only the first oracle and the next TWO fallbacks should have their turn validated.
    params["block_number"] = block_num_list_for_exp_period[2]
    can_validate_and_sign(oracleTurn, params, [0, 1, 2])

    # 2 blocks have passed since the starting block of period before price expires.
    # Only the first oracle and the next FOUR fallbacks should have their turn validated.
    params["block_number"] = block_num_list_for_exp_period[3]
    can_validate_and_sign(oracleTurn, params, [0, 1, 2, 3, 4])

    # 3 blocks have passed since the starting block of period before price expires.
    # Only the first oracle and the next SIX fallbacks should have their turn validated.
    params["block_number"] = block_num_list_for_exp_period[4]
    can_validate_and_sign(oracleTurn, params, [0, 1, 2, 3, 4, 5, 6])

    # 4 blocks have passed since the starting block of period before price expires.
    # Only the first oracle and the next EIGHT fallbacks should have their turn validated.
    params["block_number"] = block_num_list_for_exp_period[5]
    can_validate_and_sign(oracleTurn, params, [0, 1, 2, 3, 4, 5, 6, 7, 8])
