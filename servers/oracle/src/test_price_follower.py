from common.services.oracle_dao import PriceWithTimestamp
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
