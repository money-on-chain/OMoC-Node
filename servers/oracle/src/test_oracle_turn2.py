import pytest

from common.services.oracle_dao import CoinPair, PriceWithTimestamp, FullOracleRoundInfo
from oracle.src import oracle_settings
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfo
from oracle.src.oracle_configuration import OracleTurnConfiguration
from oracle.src.oracle_turn import OracleTurn

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
priceWithTS = PriceWithTimestamp

###############################################################################
# _is_oracle_turn_with_msg testing
###############################################################################

points = 0
current_round_num = 10

# 14 oracles. The last two are the same and only one has selectedInCurrentRound set to False.
# It should make both of them unable to be selected for a turn.
selected_oracles = [
    FullOracleRoundInfo('0xE11BA2b4D45Eaed5996Cd0823791E0C93114882d', 'http://127.0.0.1:24004',
                        14000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x22d491Bde2303f2f43325b2108D26f1eAbA1e32b', 'http://127.0.0.1:24002',
                        8000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x28a8746e75304c0780E011BEd21C72cD78cdC81A', 'http://127.0.0.1:24006',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x28a8746e75304c0780E011BEd21C72cD78cd8WDa', 'http://127.0.0.1:24008',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x28a8746e75304c0780E011BEd21C72cD78cdq8B8', 'http://127.0.0.1:24010',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x28a8746e75304c0780E011BEd21C72cD78cd9cQg', 'http://127.0.0.1:24012',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x28a8746e75304c0780E011BEd21C72cD78cd9CA2', 'http://127.0.0.1:24014',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x28a8746e75304c0780E011BEd21C72cD78cd0w2f', 'http://127.0.0.1:24016',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x28a8746e75304c0780E011BEd21C72cD78cdoe3q', 'http://127.0.0.1:24018',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x28a8746e75304c0780E011BEd21C72cD78cdxc90', 'http://127.0.0.1:24020',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x28a8746e75304c0780E011BEd21C72cD78cfj109', 'http://127.0.0.1:24022',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x28a8746e75304c0780E011BEd21C72cD78cpk3oD', 'http://127.0.0.1:24024',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x28a8746e75304c0780E011BEd21C72cD78cd535E', 'http://127.0.0.1:24000',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x28a8746e75304c0780E011BEd21C72cD78cd535E', 'http://127.0.0.1:24000',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, False,
                        current_round_num)
]


@pytest.fixture
def mock_select_next(monkeypatch):
    """select_next.select_next mocked to the selected_oracles order"""

    def mock(*args, **kwargs):
        return selected_oracles

    monkeypatch.setattr("oracle.src.select_next.select_next", mock)


def getOracleTurnForTurnTesting():
    return OracleTurn(oracleConf, "BTCUSD")


valid_price_period_in_blocks = 60


def oracleBCInfo2(os, block_num, last_pub_block, last_pub_block_hash, blockchain_price):
    return OracleBlockchainInfo(CoinPair('BTCUSD'), os, blockchain_price, block_num, last_pub_block,
                                last_pub_block_hash, valid_price_period_in_blocks)


def is_oracle_turn_aux(oracleTurn,
                       oracle_addr,
                       block_num,
                       blockchain_price_diff=0,
                       exchange_price_diff=0):
    last_pub_block = 1
    last_pub_block_hash = "0x0000000000000000000000000001"
    blockchain_price = 11.1 + blockchain_price_diff
    exchange_price = 11.1 + exchange_price_diff
    return oracleTurn.is_oracle_turn(oracleBCInfo2(selected_oracles,
                                                   block_num,
                                                   last_pub_block,
                                                   last_pub_block_hash,
                                                   blockchain_price),
                                     oracle_addr,
                                     priceWithTS(exchange_price, 0))


block_num_list = [12, 14, 16, 18]

# The last 2 oracles have selectedInCurrentRound set to False.
len_unselected_oracles = 2
selected_in_current_round_oracles_len = len(selected_oracles) - len_unselected_oracles


# Test oracle of index 12 is not selected because has selectedInCurrentRound set to False
def test_is_never_oracle_12_turn_because_is_not_selected(mock_select_next):
    oracleTurn = getOracleTurnForTurnTesting()
    assert is_oracle_turn_aux(oracleTurn,
                              selected_oracles[12].addr,
                              block_num_list[3],
                              oracleConf.oracle_turn_conf.price_delta_pct * .99) is False


# Test random oracle is not selected because is not in list of oracles with selectedInCurrentRound set to True
def test_an_address_that_is_not_selected(mock_select_next):
    oracleTurn = getOracleTurnForTurnTesting()
    assert is_oracle_turn_aux(oracleTurn,
                              "0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826",
                              block_num_list[3],
                              oracleConf.oracle_turn_conf.price_delta_pct * .99) is False


# Test that if the price doesn't change enough, it's no oracle's turn
def test_is_oracle_turn_no_price_change(mock_select_next):
    oracleTurn = getOracleTurnForTurnTesting()

    for i in range(len(selected_oracles)):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0]) is False

    for i in range(len(selected_oracles)):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[1]) is False

    for i in range(len(selected_oracles)):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[2],
                                  0,
                                  (11.1 * oracleConf.oracle_turn_conf.price_delta_pct) / 100 * .99) is False

    for i in range(len(selected_oracles)):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[3],
                                  (11.1 * oracleConf.oracle_turn_conf.price_delta_pct) / 100 * .99,
                                  0) is False


# Test the first oracle needs to wait ORACLE_PRICE_PUBLISH_BLOCKS blocks after price change to be selected.
def test_is_oracle_turn_it_needs_to_wait_publish_blocks(mock_select_next):
    oracleTurn = getOracleTurnForTurnTesting()

    # Price changes but it still needs to wait for ORACLE_PRICE_PUBLISH_BLOCKS blocks to pass.
    for i in range(selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0],
                                  0,
                                  3) is False

    # Price has changed ORACLE_PRICE_PUBLISH_BLOCKS blocks ago so it's the first oracle's turn only.
    assert is_oracle_turn_aux(oracleTurn,
                              selected_oracles[0].addr,
                              block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS,
                              0,
                              3) is True
    for i in range(1, selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS,
                                  0,
                                  3) is False


# Test that ORACLE_PRICE_PUBLISH_BLOCKS blocks after price change the chosen oracle and the fallbacks are selected
# at their respective blocks.
# Also test all fallbacks are selected by the end of the fallback sequence from the config.
def test_is_oracle_turn_price_change(mock_select_next):
    oracleTurn = getOracleTurnForTurnTesting()

    # No price change yet
    for i in range(selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0]) is False

    # Price changes but it still needs to wait for ORACLE_PRICE_PUBLISH_BLOCKS blocks to pass.
    for i in range(selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0],
                                  0,
                                  3) is False

    # Price has changed ORACLE_PRICE_PUBLISH_BLOCKS blocks ago so it's the FIRST oracle's turn only.
    assert is_oracle_turn_aux(oracleTurn,
                              selected_oracles[0].addr,
                              block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS,
                              0,
                              3) is True
    for i in range(1, selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS,
                                  0,
                                  3) is False

    # Price has changed (ORACLE_PRICE_PUBLISH_BLOCKS + 1) blocks ago so it's the first oracle's turn and the next TWO fallbacks' too.
    for i in range(3):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 1,
                                  0,
                                  3) is True

    for i in range(3, selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 1,
                                  0,
                                  3) is False

    # Price has changed (ORACLE_PRICE_PUBLISH_BLOCKS + 2) blocks ago so it's the first oracle's turn and the next FOUR fallbacks' too.
    for i in range(5):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 2,
                                  0,
                                  3) is True

    for i in range(5, selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 2,
                                  0,
                                  3) is False

    # Price has changed (ORACLE_PRICE_PUBLISH_BLOCKS + 3) blocks ago so it's the first oracle's turn and the next SIX fallbacks' too.
    for i in range(7):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 3,
                                  0,
                                  3) is True

    for i in range(7, selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 3,
                                  0,
                                  3) is False

    # Price has changed (ORACLE_PRICE_PUBLISH_BLOCKS + 4) blocks ago so it's the first oracle's turn and the next EIGHT fallbacks' too.
    for i in range(9):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 4,
                                  0,
                                  3) is True

    for i in range(9, selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 4,
                                  0,
                                  3) is False

    # Price has changed (ORACLE_PRICE_PUBLISH_BLOCKS + 5) blocks ago so it's the first oracle's turn and the next TEN fallbacks' too.
    for i in range(11):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 5,
                                  0,
                                  3) is True

    for i in range(11, selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 5,
                                  0,
                                  3) is False

    # Price has changed (ORACLE_PRICE_PUBLISH_BLOCKS + 6) blocks ago so it's ALL of the fallbacks' turn now.
    for i in range(12):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 6,
                                  0,
                                  3) is True

    # The rest of the oracles have selectedInCurrentRound set as False so they are not selected ever.
    for i in range(12, len(selected_oracles)):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 6,
                                  0,
                                  3) is False


# If price doesn't change, chosen oracle and fallback publish before price expiration
def test_is_oracle_turn_oracles_publish_before_price_expiration(mock_select_next):
    oracleTurn = getOracleTurnForTurnTesting()

    last_pub_block = 1
    start_block_pub_period_before_price_expires = last_pub_block + \
                                                  valid_price_period_in_blocks - \
                                                  oracleConf.oracle_turn_conf.trigger_valid_publication_blocks

    block_num_list_for_exp_period = [
        block_num_list[0],
        start_block_pub_period_before_price_expires - 1,
        start_block_pub_period_before_price_expires,
        start_block_pub_period_before_price_expires + 1,
        start_block_pub_period_before_price_expires + 2,
        start_block_pub_period_before_price_expires + 3,
        start_block_pub_period_before_price_expires + 4,
        start_block_pub_period_before_price_expires + 5,
        start_block_pub_period_before_price_expires + 6
    ]

    # No price change.
    for i in range(selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list_for_exp_period[0]) is False

    # Not yet the starting block of period before price expires.
    for i in range(selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list_for_exp_period[1]) is False

    # Reached the starting block of period before price expires.
    # It should only be the FIRST oracle's turn.
    assert is_oracle_turn_aux(oracleTurn,
                              selected_oracles[0].addr,
                              block_num_list_for_exp_period[2]) is True

    for i in range(1, selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list_for_exp_period[2]) is False

    # 1 block has passed since the starting block of period before price expires.
    # It should only be the first oracle's turn and the next TWO fallbacks'.
    for i in range(3):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list_for_exp_period[3]) is True

    for i in range(3, selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list_for_exp_period[3]) is False

    # 2 blocks have passed since the starting block of period before price expires.
    # It should only be the first oracle's turn and the next FOUR fallbacks'.
    for i in range(5):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list_for_exp_period[4]) is True

    for i in range(5, selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list_for_exp_period[4]) is False

    # 3 blocks have passed since the starting block of period before price expires.
    # It should only be the first oracle's turn and the next SIX fallbacks'.
    for i in range(7):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list_for_exp_period[5]) is True

    for i in range(7, selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list_for_exp_period[5]) is False

    # 4 blocks have passed since the starting block of period before price expires.
    # It should only be the first oracle's turn and the next EIGHT fallbacks'.
    for i in range(9):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list_for_exp_period[6]) is True

    for i in range(9, selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list_for_exp_period[6]) is False

    # 5 blocks have passed since the starting block of period before price expires.
    # It should only be the first oracle's turn and the next TEN fallbacks'.
    for i in range(11):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list_for_exp_period[7]) is True

    for i in range(11, selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list_for_exp_period[7]) is False

    # 6 blocks have passed since the starting block of period before price expires.
    # It should be all of the fallbacks' turn by now.
    for i in range(selected_in_current_round_oracles_len):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list_for_exp_period[8]) is True

    # The rest of the oracles have selectedInCurrentRound set as False so they are not selected ever.
    for i in range(selected_in_current_round_oracles_len, len(selected_oracles)):
        assert is_oracle_turn_aux(oracleTurn,
                                  selected_oracles[i].addr,
                                  block_num_list_for_exp_period[8]) is False
