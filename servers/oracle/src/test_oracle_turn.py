from common.services.oracle_dao import CoinPair, PriceWithTimestamp, FullOracleRoundInfo
from oracle.src import oracle_settings
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfo
from oracle.src.oracle_configuration import OracleTurnConfiguration
from oracle.src.oracle_turn import OracleTurn
from oracle.src.select_next import select_next_addresses

oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS = 1
oracle_settings.ORACLE_ENTERING_FALLBACKS_AMOUNTS = b'\x02\x04\x06\x08\n'


###############################################################################
# price_changed_blocks testing
###############################################################################

def getOracleTurnForPriceTesting():
    return OracleTurn(None, "BTCUSD")

priceWithTS = PriceWithTimestamp
def oracleBCInfo1(last_pub_block, block_num, blockchain_price):
    return OracleBlockchainInfo("BTCUSD", [], blockchain_price, block_num, last_pub_block, "", 300)


def test_no_price_change():
    oracleTurn = getOracleTurnForPriceTesting()
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 10, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 12, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 14, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(2, 16, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(2, 18, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(2, 20, 11.1), priceWithTS(11.1, 0))
    assert ret is None


def test_price_change():
    oracleTurn = getOracleTurnForPriceTesting()
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 10, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 12, 11.1), priceWithTS(22.2, 0))
    assert ret == 0
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 14, 11.1), priceWithTS(22.2, 0))
    assert ret == 2
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 16, 11.1), priceWithTS(22.2, 0))
    assert ret == 4
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 18, 11.1), priceWithTS(33.3, 0))
    assert ret == 6


def test_initial_price_change():
    oracleTurn = getOracleTurnForPriceTesting()
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 10, 11.1), priceWithTS(22.2, 0))
    assert ret == 0
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 12, 11.1), priceWithTS(22.2, 0))
    assert ret == 2
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 14, 11.1), priceWithTS(22.2, 0))
    assert ret == 4
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 16, 11.1), priceWithTS(22.2, 0))
    assert ret == 6
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 18, 11.1), priceWithTS(33.2, 0))
    assert ret == 8


def test_price_change_2():
    oracleTurn = getOracleTurnForPriceTesting()
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 10, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 12, 11.1), priceWithTS(22.2, 0))
    assert ret == 0
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 14, 11.1), priceWithTS(33.3, 0))
    assert ret == 2


def test_new_pub_no_price_change():
    oracleTurn = getOracleTurnForPriceTesting()
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 10, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 12, 11.1), priceWithTS(22.2, 0))
    assert ret == 0
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(2, 14, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(2, 16, 11.1), priceWithTS(11.1, 0))
    assert ret is None


def test_new_pub_price_change():
    oracleTurn = getOracleTurnForPriceTesting()
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 10, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 12, 11.1), priceWithTS(22.2, 0))
    assert ret == 0
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(2, 14, 11.1), priceWithTS(22.2, 0))
    assert ret == 0
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(2, 16, 11.1), priceWithTS(11.1, 0))
    assert ret == 2


def test_new_pub_initial_price_change():
    oracleTurn = getOracleTurnForPriceTesting()
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 10, 11.1), priceWithTS(22.2, 0))
    assert ret == 0
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 12, 11.1), priceWithTS(11.1, 0))
    assert ret == 2
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(1, 14, 11.1), priceWithTS(11.1, 0))
    assert ret == 4
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(2, 16, 11.1), priceWithTS(22.2, 0))
    assert ret == 0
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(2, 18, 11.1), priceWithTS(11.1, 0))
    assert ret == 2
    ret = oracleTurn.price_follower.price_changed_blocks(oracleConf.oracle_turn_conf, oracleBCInfo1(2, 20, 11.1), priceWithTS(11.1, 0))
    assert ret == 4

###############################################################################
# is_oracle_turn testing
###############################################################################

points = 0
current_round_num = 10
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
    FullOracleRoundInfo('0x28a8746e75304c0780E011BEd21C72cD78cd535E', 'http://127.0.0.1:24000',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x28a8746e75304c0780E011BEd21C72cD78cd535E', 'http://127.0.0.1:24000',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, False,
                        current_round_num)
                        ]

class OracleConf:
    @property
    def oracle_turn_conf(self):
        return OracleTurnConfiguration(0.05,
                                       oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS,
                                       oracle_settings.ORACLE_ENTERING_FALLBACKS_AMOUNTS,
                                       30)
oracleConf = OracleConf()

def getOracleTurnForTurnTesting():
    return OracleTurn(oracleConf, "BTCUSD")

def oracleBCInfo2(os, block_num, last_pub_block, last_pub_block_hash, blockchain_price):
    return OracleBlockchainInfo(CoinPair('BTCUSD'), os, blockchain_price, block_num, last_pub_block,
                                last_pub_block_hash, 300)


def is_oracle_turn(oracleTurn, vi, oracle_addr, exchange_price):
    oracle_addresses = select_next_addresses(vi.last_pub_block_hash,
                                             vi.selected_oracles)
    return oracleTurn._is_oracle_turn_with_msg(vi, oracle_addr, exchange_price, oracle_addresses)[0]

# Test oracle of index 8 is not selected because has selectedInCurrentRound set to False
def test_is_never_oracle_8_turn_because_is_not_selected():
    oracleTurn = getOracleTurnForTurnTesting()
    assert is_oracle_turn(oracleTurn,
                          oracleBCInfo2(selected_oracles,
                                        18,
                                        1,
                                        "0x00000000000000000000",
                                        11.1 + oracleConf.oracle_turn_conf.price_delta_pct * .99),
                          selected_oracles[8].addr,
                          priceWithTS(11.1, 0)) is False

# Test random oracle is not selected because is not in list of oracles with selectedInCurrentRound set to True
def test_an_address_that_is_not_selected():
    oracleTurn = getOracleTurnForTurnTesting()
    assert is_oracle_turn(oracleTurn,
                          oracleBCInfo2(selected_oracles,
                                        18,
                                        1,
                                        "0x00000000000000000000",
                                        11.1 + oracleConf.oracle_turn_conf.price_delta_pct * .99),
                          "0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826",
                          priceWithTS(11.1, 0)) is False

# Test that if the price doesn't change enough, it's no oracle's turn
def test_is_oracle_turn_no_price_change():
    oracleTurn = getOracleTurnForTurnTesting()
    def is_oracle_turn_no_price_change(oracle_addr,
                                       block_num,
                                       blockchain_price_diff=0,
                                       exchange_price_diff=0):
        last_pub_block = 1
        last_pub_block_hash = "0x00000000000000000000"
        blockchain_price = 11.1 + blockchain_price_diff
        exchange_price = 11.1 + exchange_price_diff
        return is_oracle_turn(oracleTurn,
                              oracleBCInfo2(selected_oracles,
                                            block_num,
                                            last_pub_block,
                                            last_pub_block_hash,
                                            blockchain_price),
                          oracle_addr,
                          priceWithTS(exchange_price, 0))

    block_num_list = [12,14,16,18]

    for i in range(len(selected_oracles)):
        assert is_oracle_turn_no_price_change(selected_oracles[i].addr,
                                              block_num_list[0]) is False

    for i in range(len(selected_oracles)):
        assert is_oracle_turn_no_price_change(selected_oracles[i].addr,
                                              block_num_list[1]) is False

    for i in range(len(selected_oracles)):
        assert is_oracle_turn_no_price_change(selected_oracles[i].addr,
                                              block_num_list[2],
                                              0,
                                              (11.1 * oracleConf.oracle_turn_conf.price_delta_pct) / 100 * .99) is False

    for i in range(len(selected_oracles)):
        assert is_oracle_turn_no_price_change(selected_oracles[i].addr,
                                              block_num_list[3],
                                              (11.1 * oracleConf.oracle_turn_conf.price_delta_pct) / 100 * .99,
                                              0) is False

# Test the first oracle needs to wait ORACLE_PRICE_PUBLISH_BLOCKS blocks after price change to be selected.
def test_is_oracle_turn_it_needs_to_wait_publish_blocks():
    oracleTurn = getOracleTurnForTurnTesting()
    def is_oracle_turn_it_needs_to_wait_publish_blocks(oracle_addr,
                                                       block_num,
                                                       blockchain_price_diff=0,
                                                       exchange_price_diff=0):
        last_pub_block = 1
        last_pub_block_hash = "0x00000000000000000001"
        blockchain_price = 11.1 + blockchain_price_diff
        exchange_price = 11.1 + exchange_price_diff
        return is_oracle_turn(oracleTurn,
                              oracleBCInfo2(selected_oracles,
                                            block_num,
                                            last_pub_block,
                                            last_pub_block_hash,
                                            blockchain_price),
                          oracle_addr,
                          priceWithTS(exchange_price, 0))

    block_num_list = [12,14,16,18]

    # Price changes but it still needs to wait for ORACLE_PRICE_PUBLISH_BLOCKS blocks to pass.
    for i in range(8):
        assert is_oracle_turn_it_needs_to_wait_publish_blocks(selected_oracles[i].addr,
                                                              block_num_list[0],
                                                              0,
                                                              3) is False

    # Price has changed ORACLE_PRICE_PUBLISH_BLOCKS blocks ago so it's the first oracle's turn only.
    assert is_oracle_turn_it_needs_to_wait_publish_blocks(selected_oracles[0].addr,
                                                          block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS,
                                                          0,
                                                          3) is True
    for i in range(1,8):
        assert is_oracle_turn_it_needs_to_wait_publish_blocks(selected_oracles[i].addr,
                                                              block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS,
                                                              0,
                                                              3) is False

    # Price has changed (ORACLE_PRICE_PUBLISH_BLOCKS + 1) blocks ago so it's the first oracle's turn and the next two fallbacks' too.
    for i in range(3):
        assert is_oracle_turn_it_needs_to_wait_publish_blocks(selected_oracles[i].addr,
                                                              block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 1,
                                                              0,
                                                              3) is True

    for i in range(3,8):
        assert is_oracle_turn_it_needs_to_wait_publish_blocks(selected_oracles[i].addr,
                                                              block_num_list[0] + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 1,
                                                              0,
                                                              3) is False


def test_is_oracle_turn_price_change():
    oracleTurn = getOracleTurnForTurnTesting()
    def is_oracle_turn_price_change(oracle_addr,
                                       block_num,
                                       blockchain_price_diff=0,
                                       exchange_price_diff=0):
        last_pub_block = 1
        last_pub_block_hash = "0x00000000000000000001"
        blockchain_price = 11.1 + blockchain_price_diff
        exchange_price = 11.1 + exchange_price_diff
        return is_oracle_turn(oracleTurn,
                              oracleBCInfo2(selected_oracles,
                                            block_num,
                                            last_pub_block,
                                            last_pub_block_hash,
                                            blockchain_price),
                          oracle_addr,
                          priceWithTS(exchange_price, 0))

    block_num_list = [12,14,16,18]

    # No price change yet
    for i in range(3):
        assert is_oracle_turn_price_change(selected_oracles[i].addr,
                                           block_num_list[0]) is False

    # Price changes
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000000000000000001", 11.1), selected_oracles[0].addr,
                          priceWithTS(14.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000000000000000001", 11.1), selected_oracles[1].addr,
                          priceWithTS(14.1, 0)) is False
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000000000000000001", 11.1), selected_oracles[2].addr,
                          priceWithTS(14.1, 0)) is False

    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 13, 1, "0x00000000000000000001", 11.1), selected_oracles[0].addr,
                          priceWithTS(14.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 13, 1, "0x00000000000000000001", 11.1), selected_oracles[1].addr,
                          priceWithTS(14.1, 0)) is False
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 13, 1, "0x00000000000000000001", 11.1), selected_oracles[2].addr,
                          priceWithTS(14.1, 0)) is False

    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 13 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS, 1,
                                        "0x00000000000000000001", 11.1), selected_oracles[0].addr, priceWithTS(14.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 13 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS, 1,
                                        "0x00000000000000000001", 11.1), selected_oracles[1].addr, priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 13 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS, 1,
                                        "0x00000000000000000001", 11.1), selected_oracles[2].addr, priceWithTS(11.1, 0)) is False

    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 14 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS, 1,
                                        "0x00000000000000000001", 11.1), selected_oracles[0].addr, priceWithTS(14.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 14 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS, 1,
                                        "0x00000000000000000001", 11.1), selected_oracles[1].addr, priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 14 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS, 1,
                                        "0x00000000000000000001", 11.1), selected_oracles[2].addr, priceWithTS(11.1, 0)) is False

    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 16 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS, 1,
                                        "0x00000000000000000001", 11.1), selected_oracles[0].addr, priceWithTS(14.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 16 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS, 1,
                                        "0x00000000000000000001", 11.1), selected_oracles[1].addr, priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 16 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS, 1,
                                        "0x00000000000000000001", 11.1), selected_oracles[2].addr, priceWithTS(11.1, 0)) is True

    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 18 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS, 1,
                                        "0x00000000000000000001", 11.1), selected_oracles[0].addr, priceWithTS(14.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 18 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS, 1,
                                        "0x00000000000000000001", 11.1), selected_oracles[1].addr, priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 18 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS, 1,
                                        "0x00000000000000000001", 11.1), selected_oracles[2].addr, priceWithTS(11.1, 0)) is True


# Fallbacks enter price_fallback_blocks blocks after price change according to sequence block by block
#def test_fallbacks_enter_at_their_turn_after_price_change():
#    oracleTurn = getOracleTurnForTurnTesting()
#    
#    # oracleBCInfo2(os, block_num, last_pub_block, last_pub_block_hash, blockchain_price)
#    # is_oracle_turn(oracleTurn, vi, oracle_addr, exchange_price)
#
#    # It's no oracle's turn because the price hasn't changed
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000000000000000001", 11.1),
#                          selected_oracles[0].addr,
#                          priceWithTS(11.1, 0)) is False
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000000000000000001", 11.1),
#                          selected_oracles[1].addr,
#                          priceWithTS(11.1, 0)) is False
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000000000000000001", 11.1),
#                          selected_oracles[2].addr,
#                          priceWithTS(11.1, 0)) is False
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000000000000000001", 11.1),
#                          selected_oracles[3].addr,
#                          priceWithTS(11.1, 0)) is False
#
#    # It's no oracle's turn because even if ORACLE_PRICE_PUBLISH_BLOCKS blocks have passed, the price hasn't changed.
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS,
#                          1, "0x00000000000000000001", 11.1), selected_oracles[0].addr,
#                          priceWithTS(11.1, 0)) is False
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS,
#                          1, "0x00000000000000000001", 11.1), selected_oracles[1].addr,
#                          priceWithTS(11.1, 0)) is False
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS,
#                          1, "0x00000000000000000001", 11.1), selected_oracles[2].addr,
#                          priceWithTS(11.1, 0)) is False
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS,
#                          1, "0x00000000000000000001", 11.1), selected_oracles[3].addr,
#                          priceWithTS(11.1, 0)) is False
#
#    # It's no oracle's turn because no blocks passed since publication and the price hasn't changed.
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 1,
#                          1, "0x00000000000000000001", 11.1), selected_oracles[0].addr,
#                          priceWithTS(11.1, 0)) is False
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 1,
#                          1, "0x00000000000000000001", 11.1), selected_oracles[1].addr,
#                          priceWithTS(11.1, 0)) is False
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 1,
#                          1, "0x00000000000000000001", 11.1), selected_oracles[2].addr,
#                          priceWithTS(11.1, 0)) is False
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 1,
#                          1, "0x00000000000000000001", 11.1), selected_oracles[3].addr,
#                          priceWithTS(11.1, 0)) is False
#
#    # It's no oracle's turn because the price has changed but no blocks passed since publication.
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 1,
#                          1, "0x00000000000000000001", 11.1), selected_oracles[0].addr,
#                          priceWithTS(14.1, 0)) is False
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 1,
#                          1, "0x00000000000000000001", 11.1), selected_oracles[1].addr,
#                          priceWithTS(14.1, 0)) is False
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 1,
#                          1, "0x00000000000000000001", 11.1), selected_oracles[2].addr,
#                          priceWithTS(14.1, 0)) is False
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 1,
#                          1, "0x00000000000000000001", 11.1), selected_oracles[3].addr,
#                          priceWithTS(14.1, 0)) is False
#
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 1,
#                          1, "0x00000000000000000001", 11.1), selected_oracles[0].addr, priceWithTS(11.1, 0)) is True
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 1,
#                          1, "0x00000000000000000001", 11.1), selected_oracles[1].addr, priceWithTS(11.1, 0)) is True
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 1,
#                          1, "0x00000000000000000001", 11.1), selected_oracles[2].addr, priceWithTS(11.1, 0)) is True
#    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS + 1,
#                          1, "0x00000000000000000001", 11.1), selected_oracles[3].addr, priceWithTS(11.1, 0)) is True


# If price doesn't change, chosen oracle and fallback publish before price expiration
#def test_oracles_publish_before_price_expiration():
    #oracleTurn = getOracleTurnForTurnTesting()
    #
    ## oracleBCInfo2(os, block_num, last_pub_block, last_pub_block_hash, blockchain_price)
    ## is_oracle_turn(vi, oracle_addr, exchange_price)
    #assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000000000000000001", 11.1),
    #                      selected_oracles[0].addr,
    #                      priceWithTS(11.1, 0)) is True
    #assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000000000000000001", 11.1),
    #                      selected_oracles[1].addr,
    #                      priceWithTS(11.1, 0)) is False
    #assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000000000000000001", 11.1),
    #                      selected_oracles[2].addr,
    #                      priceWithTS(11.1, 0)) is False
    #assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000000000000000001", 11.1),
    #                      selected_oracles[3].addr,
    #                      priceWithTS(11.1, 0)) is False

    # assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS,
    #                                                 1, "0x00000001", 11.1), selected_oracles[0].addr,
    #                       priceWithTS(11.1, 0)) is True
    # assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS,
    #                                                 1, "0x00000001", 11.1), selected_oracles[1].addr,
    #                       priceWithTS(11.1, 0)) is True
    # assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS,
    #                                                 1, "0x00000001", 11.1), selected_oracles[2].addr,
    #                       priceWithTS(11.1, 0)) is True
    # assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS,
    #                                                 1, "0x00000001", 11.1), selected_oracles[3].addr,
    #                       priceWithTS(11.1, 0)) is False
    #
    # assert is_oracle_turn(oracleTurn,
    #                       oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS + 1,
    #                                     1, "0x00000001", 11.1), selected_oracles[0].addr, priceWithTS(11.1, 0)) is True
    # assert is_oracle_turn(oracleTurn,
    #                       oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS + 1,
    #                                     1, "0x00000001", 11.1), selected_oracles[1].addr, priceWithTS(11.1, 0)) is True
    # assert is_oracle_turn(oracleTurn,
    #                       oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS + 1,
    #                                     1, "0x00000001", 11.1), selected_oracles[2].addr, priceWithTS(11.1, 0)) is True
    # assert is_oracle_turn(oracleTurn,
    #                       oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS + 1,
    #                                     1, "0x00000001", 11.1), selected_oracles[3].addr, priceWithTS(11.1, 0)) is True
