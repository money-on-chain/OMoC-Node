from common.services.oracle_dao import CoinPair, PriceWithTimestamp, FullOracleRoundInfo
from oracle.src import oracle_settings
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfo
from oracle.src.oracle_configuration import OracleTurnConfiguration
from oracle.src.oracle_turn import OracleTurn
from oracle.src.select_next import select_next

oracle_settings.ORACLE_PRICE_PUBLISH_BLOCKS = 1
oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS = 3


def oracleBCInfo1(last_pub_block, block_num, blockchain_price):
    return OracleBlockchainInfo("BTCUSD", [], blockchain_price, block_num, last_pub_block, "", 3)


oracleTurnConf = OracleTurnConfiguration(0.05, 3, 1, b'\x02\x04\x06\x08\n', 30)
priceWithTS = PriceWithTimestamp


def test_no_price_change():
    oracleTurn = OracleTurn(None, "BTCUSD")
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 10, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 12, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 14, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(2, 16, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(2, 18, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(2, 20, 11.1), priceWithTS(11.1, 0))
    assert ret is None


def test_price_change():
    oracleTurn = OracleTurn(None, "BTCUSD")
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 10, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 12, 11.1), priceWithTS(22.2, 0))
    assert ret == 0
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 14, 11.1), priceWithTS(22.2, 0))
    assert ret == 2
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 16, 11.1), priceWithTS(22.2, 0))
    assert ret == 4
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 18, 11.1), priceWithTS(33.3, 0))
    assert ret == 6


def test_initial_price_change():
    oracleTurn = OracleTurn(None, "BTCUSD")
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 10, 11.1), priceWithTS(22.2, 0))
    assert ret == 0
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 12, 11.1), priceWithTS(22.2, 0))
    assert ret == 2
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 14, 11.1), priceWithTS(22.2, 0))
    assert ret == 4
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 16, 11.1), priceWithTS(22.2, 0))
    assert ret == 6
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 18, 11.1), priceWithTS(33.2, 0))
    assert ret == 8


def test_price_change_2():
    oracleTurn = OracleTurn(None, "BTCUSD")
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 10, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 12, 11.1), priceWithTS(22.2, 0))
    assert ret == 0
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 14, 11.1), priceWithTS(33.3, 0))
    assert ret == 2


def test_new_pub_no_price_change():
    oracleTurn = OracleTurn(None, "BTCUSD")
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 10, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 12, 11.1), priceWithTS(22.2, 0))
    assert ret == 0
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(2, 14, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(2, 16, 11.1), priceWithTS(11.1, 0))
    assert ret is None


def test_new_pub_price_change():
    oracleTurn = OracleTurn(None, "BTCUSD")
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 10, 11.1), priceWithTS(11.1, 0))
    assert ret is None
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 12, 11.1), priceWithTS(22.2, 0))
    assert ret == 0
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(2, 14, 11.1), priceWithTS(22.2, 0))
    assert ret == 0
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(2, 16, 11.1), priceWithTS(11.1, 0))
    assert ret == 2


def test_new_pub_initial_price_change():
    oracleTurn = OracleTurn(None, "BTCUSD")
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 10, 11.1), priceWithTS(22.2, 0))
    assert ret == 0
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 12, 11.1), priceWithTS(11.1, 0))
    assert ret == 2
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(1, 14, 11.1), priceWithTS(11.1, 0))
    assert ret == 4
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(2, 16, 11.1), priceWithTS(22.2, 0))
    assert ret == 0
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(2, 18, 11.1), priceWithTS(11.1, 0))
    assert ret == 2
    ret = oracleTurn._price_changed_blocks(oracleTurnConf, oracleBCInfo1(2, 20, 11.1), priceWithTS(11.1, 0))
    assert ret == 4


class Conf:
    @property
    def oracle_turn_conf(self):
        return OracleTurnConfiguration(0.05, 3, 1, b'\x02\x04\x06\x08\n', 30)


conf = Conf()

points = 0
current_round_num = 10
selected_oracles = [
    FullOracleRoundInfo('0xE11BA2b4D45Eaed5996Cd0823791E0C93114882d', 'http://127.0.0.1:24004',
                        14000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x22d491Bde2303f2f43325b2108D26f1eAbA1e32b', 'http://127.0.0.1:24002',
                        8000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x28a8746e75304c0780E011BEd21C72cD78cd535E', 'http://127.0.0.1:24000',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x28a8746e75304c0780E011BEd21C72cD78cd535E', 'http://127.0.0.1:24000',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, False,
                        current_round_num)]


def oracleBCInfo2(os, block_num, last_pub_block, last_pub_block_hash, blockchain_price):
    return OracleBlockchainInfo(CoinPair('BTCUSD'), os, blockchain_price, block_num, last_pub_block,
                                last_pub_block_hash, 300)


def is_oracle_turn(oracleTurn, vi, oracle_addr, exchange_price):
    ordered_oracle_selection = select_next(vi.last_pub_block_hash,
                                           vi.selected_oracles)
    oracle_addresses = [x.addr for x in ordered_oracle_selection]
    return oracleTurn._is_oracle_turn_with_msg(vi, oracle_addr, exchange_price, oracle_addresses)[0]


def test_is_never_oracle_3_turn_is_not_selected():
    oracleTurn = OracleTurn(conf, "BTCUSD")
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 18, 1, "0x00000000",
                                                    11.1 + conf.oracle_turn_conf.price_fallback_delta_pct * .99),
                          selected_oracles[3].addr, priceWithTS(11.1, 0)) is False


def test_an_address_that_is_not_selected():
    oracleTurn = OracleTurn(conf, "BTCUSD")
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 18, 1, "0x00000000",
                                                    11.1 + conf.oracle_turn_conf.price_fallback_delta_pct * .99),
                          "0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826", priceWithTS(11.1, 0)) is False


def test_is_oracle_turn_no_price_change():
    oracleTurn = OracleTurn(conf, "BTCUSD")
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000000", 11.1),
                          selected_oracles[0].addr,
                          priceWithTS(11.1, 0)) is False
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000000", 11.1),
                          selected_oracles[1].addr,
                          priceWithTS(11.1, 0)) is False

    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 14, 1, "0x00000000", 11.1),
                          selected_oracles[0].addr,
                          priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 14, 1, "0x00000000", 11.1),
                          selected_oracles[1].addr,
                          priceWithTS(11.1, 0)) is False
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 16, 1, "0x00000000", 11.1),
                          selected_oracles[0].addr,
                          priceWithTS(11.1 + conf.price_fallback_delta_pct * .99, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 16, 1, "0x00000000", 11.1),
                          selected_oracles[1].addr,
                          priceWithTS(11.1 + conf.price_fallback_delta_pct * .99, 0)) is False
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 18, 1, "0x00000000",
                                                    11.1 + conf.price_fallback_delta_pct * .99),
                          selected_oracles[0].addr, priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 18, 1, "0x00000000",
                                                    11.1 + conf.price_fallback_delta_pct * .99),
                          selected_oracles[0].addr, priceWithTS(11.1, 0)) is True


def test_is_oracle_turn_price_change():
    oracleTurn = OracleTurn(conf, "BTCUSD")
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000001", 11.1),
                          selected_oracles[0].addr,
                          priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000001", 11.1),
                          selected_oracles[1].addr,
                          priceWithTS(11.1, 0)) is False
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000001", 11.1),
                          selected_oracles[2].addr,
                          priceWithTS(11.1, 0)) is False

    # price change
    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 12, 1, "0x00000001", 11.1), selected_oracles[0].addr,
                          priceWithTS(14.1, 0)) is True
    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 12, 1, "0x00000001", 11.1), selected_oracles[1].addr,
                          priceWithTS(14.1, 0)) is False
    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 12, 1, "0x00000001", 11.1), selected_oracles[2].addr,
                          priceWithTS(14.1, 0)) is False

    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 13, 1, "0x00000001", 11.1), selected_oracles[0].addr,
                          priceWithTS(14.1, 0)) is True
    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 13, 1, "0x00000001", 11.1), selected_oracles[1].addr,
                          priceWithTS(14.1, 0)) is False
    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 13, 1, "0x00000001", 11.1), selected_oracles[2].addr,
                          priceWithTS(14.1, 0)) is False

    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 13 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS, 1,
                                        "0x00000001", 11.1), selected_oracles[0].addr, priceWithTS(14.1, 0)) is True
    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 13 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS, 1,
                                        "0x00000001", 11.1), selected_oracles[1].addr, priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 13 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS, 1,
                                        "0x00000001", 11.1), selected_oracles[2].addr, priceWithTS(11.1, 0)) is False

    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 14 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS, 1,
                                        "0x00000001", 11.1), selected_oracles[0].addr, priceWithTS(14.1, 0)) is True
    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 14 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS, 1,
                                        "0x00000001", 11.1), selected_oracles[1].addr, priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 14 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS, 1,
                                        "0x00000001", 11.1), selected_oracles[2].addr, priceWithTS(11.1, 0)) is False

    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 16 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS, 1,
                                        "0x00000001", 11.1), selected_oracles[0].addr, priceWithTS(14.1, 0)) is True
    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 16 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS, 1,
                                        "0x00000001", 11.1), selected_oracles[1].addr, priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 16 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS, 1,
                                        "0x00000001", 11.1), selected_oracles[2].addr, priceWithTS(11.1, 0)) is True

    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 18 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS, 1,
                                        "0x00000001", 11.1), selected_oracles[0].addr, priceWithTS(14.1, 0)) is True
    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 18 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS, 1,
                                        "0x00000001", 11.1), selected_oracles[1].addr, priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleBCInfo2(selected_oracles, 18 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS, 1,
                                        "0x00000001", 11.1), selected_oracles[2].addr, priceWithTS(11.1, 0)) is True


# Fallbacks enter price_fallback_blocks blocks after price change according to sequence block by block
def test_2_fallbacks_enter_at_their_turn_after_price_change():
    oracleTurn = OracleTurn(conf, "BTCUSD")
    # oracleBCInfo2(os, block_num, last_pub_block, last_pub_block_hash, blockchain_price)
    # is_oracle_turn(vi, oracle_addr, exchange_price)
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000001", 11.1),
                          selected_oracles[0].addr,
                          priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000001", 11.1),
                          selected_oracles[1].addr,
                          priceWithTS(11.1, 0)) is False
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000001", 11.1),
                          selected_oracles[2].addr,
                          priceWithTS(11.1, 0)) is False
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000001", 11.1),
                          selected_oracles[3].addr,
                          priceWithTS(11.1, 0)) is False

    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS,
                                                    1, "0x00000001", 11.1), selected_oracles[0].addr,
                          priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS,
                                                    1, "0x00000001", 11.1), selected_oracles[1].addr,
                          priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS,
                                                    1, "0x00000001", 11.1), selected_oracles[2].addr,
                          priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS,
                                                    1, "0x00000001", 11.1), selected_oracles[3].addr,
                          priceWithTS(11.1, 0)) is False

    assert is_oracle_turn(oracleTurn,
                          oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS + 1,
                                        1, "0x00000001", 11.1), selected_oracles[0].addr, priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn,
                          oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS + 1,
                                        1, "0x00000001", 11.1), selected_oracles[1].addr, priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn,
                          oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS + 1,
                                        1, "0x00000001", 11.1), selected_oracles[2].addr, priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn,
                          oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS + 1,
                                        1, "0x00000001", 11.1), selected_oracles[3].addr, priceWithTS(11.1, 0)) is True


# If price doesn't change, chosen oracle and fallback publish before price expiration
def test_oracles_publish_before_price_expiration():
    oracleTurn = OracleTurn(conf, "BTCUSD")

    # oracleBCInfo2(os, block_num, last_pub_block, last_pub_block_hash, blockchain_price)
    # is_oracle_turn(vi, oracle_addr, exchange_price)
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000001", 11.1),
                          selected_oracles[0].addr,
                          priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000001", 11.1),
                          selected_oracles[1].addr,
                          priceWithTS(11.1, 0)) is False
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000001", 11.1),
                          selected_oracles[2].addr,
                          priceWithTS(11.1, 0)) is False
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12, 1, "0x00000001", 11.1),
                          selected_oracles[3].addr,
                          priceWithTS(11.1, 0)) is False

    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS,
                                                    1, "0x00000001", 11.1), selected_oracles[0].addr,
                          priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS,
                                                    1, "0x00000001", 11.1), selected_oracles[1].addr,
                          priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS,
                                                    1, "0x00000001", 11.1), selected_oracles[2].addr,
                          priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn, oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS,
                                                    1, "0x00000001", 11.1), selected_oracles[3].addr,
                          priceWithTS(11.1, 0)) is False

    assert is_oracle_turn(oracleTurn,
                          oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS + 1,
                                        1, "0x00000001", 11.1), selected_oracles[0].addr, priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn,
                          oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS + 1,
                                        1, "0x00000001", 11.1), selected_oracles[1].addr, priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn,
                          oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS + 1,
                                        1, "0x00000001", 11.1), selected_oracles[2].addr, priceWithTS(11.1, 0)) is True
    assert is_oracle_turn(oracleTurn,
                          oracleBCInfo2(selected_oracles, 12 + oracle_settings.ORACLE_PRICE_FALLBACK_BLOCKS + 1,
                                        1, "0x00000001", 11.1), selected_oracles[3].addr, priceWithTS(11.1, 0)) is True
