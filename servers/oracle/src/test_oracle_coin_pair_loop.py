import pytest
from pytest_httpserver import HTTPServer
from pytest_httpserver.pytest_plugin import Plugin

from starlette.datastructures import Secret

from common.services.oracle_dao import FullOracleRoundInfo, CoinPair, PriceWithTimestamp
from common import crypto
from oracle.src.oracle_coin_pair_loop import OracleCoinPairLoop, gather_signatures
from oracle.src import oracle_settings
from oracle.src.oracle_publish_message import PublishPriceParams
from common.services.blockchain import BlockchainAccount


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
    host, port = ("127.0.0.1", 5001)
    server = PluginHTTPServer(host=host, port=port)
    server.start()
    try:
        yield server
    finally:
        server.stop()

@pytest.fixture
def httpserver2():
    host, port = ("127.0.0.1", 5002)
    server = PluginHTTPServer(host=host, port=port)
    server.start()
    try:
        yield server
    finally:
        server.stop()

@pytest.fixture
def httpserver3():
    host, port = ("127.0.0.1", 5003)
    server = PluginHTTPServer(host=host, port=port)
    server.start()
    try:
        yield server
    finally:
        server.stop()

@pytest.fixture
def httpserver4():
    host, port = ("127.0.0.1", 5004)
    server = PluginHTTPServer(host=host, port=port)
    server.start()
    try:
        yield server
    finally:
        server.stop()

def get_oracle_account(oracle_addr, private_key) -> BlockchainAccount:
    secret = Secret(private_key)
    default_addr = crypto.addr_from_key(str(secret))
    address = oracle_addr
    if default_addr != address:
        raise ValueError("ORACLE_ADDR doesn't match ORACLE_PRIVATE_KEY, %s != %s" % (default_addr, address))
    return BlockchainAccount(address, secret)


@pytest.mark.asyncio
async def test_gather_signatures_gathers_just_needed_sigs(httpserver1: HTTPServer,
                                                          httpserver2: HTTPServer,
                                                          httpserver3: HTTPServer,
                                                          httpserver4: HTTPServer):
    message_version = 3
    coin_pair = CoinPair('BTCUSD')
    price = 19030550000000000000000
    ts_utc = 1606323345.214337
    exchange_price = PriceWithTimestamp(price, ts_utc)
    last_pub_block = 1234567

    oracle_account1 = get_oracle_account("0x610Bb1573d1046FCb8A70Bbbd395754cD57C2b60",
                                         "0x77c5495fbb039eed474fc940f29955ed0531693cc9212911efd35dff0373153f")
    oracle_account2 = get_oracle_account("0x855FA758c77D68a04990E992aA4dcdeF899F654A",
                                         "0xd99b5b29e6da2528bf458b26237a6cf8655a3e3276c1cdc0de1f98cefee81c01")
    oracle_account3 = get_oracle_account("0xfA2435Eacf10Ca62ae6787ba2fB044f8733Ee843",
                                         "0x9b9c613a36396172eab2d34d72331c8ca83a358781883a535d2941f66db07b24")
    oracle_account4 = get_oracle_account("0x64E078A8Aa15A41B85890265648e965De686bAE6",
                                         "0x0874049f95d55fb76916262dc70571701b5c4cc5900c0691af75f1a8a52c8268")
    oracle_account5 = get_oracle_account("0x2F560290FEF1B3Ada194b6aA9c40aa71f8e95598",
                                         "0x21d7212f3b4e5332fd465877b64926e3532653e2798a11255a46f533852dfe46")
    oracle_accounts = [oracle_account1, oracle_account2, oracle_account3, oracle_account4, oracle_account5]
    params = PublishPriceParams(message_version,
                                coin_pair,
                                exchange_price,
                                oracle_accounts[0].addr,
                                last_pub_block)
    message = params.prepare_price_msg()

    needed_sigs = (len(oracles) // 2) + 1
    signatures = []
    for oracle_account in oracle_accounts:
        signatures.append(crypto.sign_message(hexstr="0x" + message, account=oracle_account))

    sigs_requester_oracle = signatures.pop(0)

    responses = []
    for signature in signatures:
        responses.append({"message": message, "signature": signature})

    servers = [httpserver1, httpserver2, httpserver3, httpserver4]
    for (server, signature) in zip(servers, signatures):
        server.expect_request("/sign/").respond_with_json({
            "message": message,
            "signature": signature.hex()
        })

    sigs = await gather_signatures(oracles, params, message, sigs_requester_oracle)
    if not (len(sigs) == needed_sigs) and (sigs_requester_oracle in sigs):
        assert False
