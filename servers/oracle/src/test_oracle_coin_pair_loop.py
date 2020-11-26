import pytest
from pytest_httpserver import HTTPServer
from pytest_httpserver.pytest_plugin import Plugin

from common.services.oracle_dao import FullOracleRoundInfo, CoinPair, PriceWithTimestamp
from common import crypto
from oracle.src.oracle_coin_pair_loop import OracleCoinPairLoop, gather_signatures
from oracle.src import oracle_settings
from oracle.src.oracle_publish_message import PublishPriceParams


points = 0
current_round_num = 10

oracles = [
    FullOracleRoundInfo('0x610Bb1573d1046FCb8A70Bbbd395754cD57C2b60', 'http://127.0.0.1:5000',
                        14000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x855FA758c77D68a04990E992aA4dcdeF899F654A', 'http://127.0.0.1:5001',
                        8000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0xfA2435Eacf10Ca62ae6787ba2fB044f8733Ee843', 'http://127.0.0.1:5002',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x64E078A8Aa15A41B85890265648e965De686bAE6', 'http://127.0.0.1:5003',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num),
    FullOracleRoundInfo('0x2F560290FEF1B3Ada194b6aA9c40aa71f8e95598', 'http://127.0.0.1:5004',
                        2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', points, True,
                        current_round_num)
]


class PluginHTTPServer(HTTPServer):
    def start(self):
        super().start()
    def stop(self):
        super().stop()

@pytest.fixture
def httpserver1():
    host, port = ("127.0.0.1", 5000)
    server = PluginHTTPServer(host=host, port=port)
    server.start()
    try:
        yield server
    finally:
        server.stop()

@pytest.fixture
def httpserver2():
    host, port = ("127.0.0.1", 5001)
    server = PluginHTTPServer(host=host, port=port)
    server.start()
    try:
        yield server
    finally:
        server.stop()

@pytest.fixture
def httpserver3():
    host, port = ("127.0.0.1", 5002)
    server = PluginHTTPServer(host=host, port=port)
    server.start()
    try:
        yield server
    finally:
        server.stop()

@pytest.fixture
def httpserver4():
    host, port = ("127.0.0.1", 5003)
    server = PluginHTTPServer(host=host, port=port)
    server.start()
    try:
        yield server
    finally:
        server.stop()

@pytest.fixture
def httpserver5():
    host, port = ("127.0.0.1", 5004)
    server = PluginHTTPServer(host=host, port=port)
    server.start()
    try:
        yield server
    finally:
        server.stop()



@pytest.mark.asyncio
async def test_gather_signatures_gathers_just_needed_sigs(httpserver1: HTTPServer,
                                                          httpserver2: HTTPServer,
                                                          httpserver3: HTTPServer,
                                                          httpserver4: HTTPServer,
                                                          httpserver5: HTTPServer):
    message_version = 3
    coin_pair = CoinPair('BTCUSD')
    price = 19030550000000000000000
    ts_utc = 1606323345.214337
    exchange_price = PriceWithTimestamp(price, ts_utc)
    oracle_account = oracle_settings.get_oracle_account()
    last_pub_block = 1234567
    params = PublishPriceParams(message_version,
                                coin_pair,
                                exchange_price,
                                oracle_account.addr,
                                last_pub_block)
    message = params.prepare_price_msg()
    signature = crypto.sign_message(hexstr="0x" + message, account=oracle_account)
    httpserver1.expect_request("/sign").respond_with_json({
            "message": message,
            "signature": signature.hex()
        })
    httpserver2.expect_request("/sign").respond_with_json({
            "message": message,
            "signature": signature.hex()
        })
    httpserver3.expect_request("/sign").respond_with_json({
            "message": message,
            "signature": signature.hex()
        })
    httpserver4.expect_request("/sign").respond_with_json({
            "message": message,
            "signature": signature.hex()
        })
    httpserver5.expect_request("/sign").respond_with_json({
            "message": message,
            "signature": signature.hex()
        })
    sigs = await gather_signatures(oracles, params, message, signature)
    print(sigs)
    assert False