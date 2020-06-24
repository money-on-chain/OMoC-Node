import pytest
import asyncio
import json
from aiohttp import ClientConnectorError, InvalidURL, ClientResponseError
from common import helpers, crypto
from oracle.src.oracle_publish_message import PublishPriceParams
from oracle.src.oracle_coin_pair_service import FullOracleRoundInfo
from starlette.datastructures import Secret
from common.ganache_accounts import GANACHE_ACCOUNTS
from common.services.blockchain import BlockchainAccount
from oracle.src.request_validation import InvalidTurn
from common.services.oracle_dao import CoinPair, PriceWithTimestamp
from oracle.src import oracle_settings

accounts = [BlockchainAccount(x[0], Secret(x[1])) for x in GANACHE_ACCOUNTS]

selected_oracles = [
    (accounts[1], 'http://127.0.0.1:24000', 14000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0),
    (accounts[2], 'http://127.0.0.1:24001', 14000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0),
    (accounts[3], 'http://127.0.0.1:24002', 14000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0),
    (accounts[4], 'http://127.0.0.1:24003', 8000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0),
    (accounts[5], 'http://127.0.0.1:24004', 2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0),
    (accounts[6], 'http://127.0.0.1:24005', 8000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0),
    (accounts[7], 'http://127.0.0.1:24006', 14000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0),
    (accounts[8], 'http://127.0.0.1:24007', 8000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0),
    (accounts[9], 'http://127.0.0.1:24008', 2000000000000000000, '0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826', 0, True,
     0)]

async def make_sign_request(oracle: FullOracleRoundInfo, params: PublishPriceParams, my_signature, timeout=10):
    target_uri = oracle.internetName + "/sign/"
    try:
        post_data = {
                  "version": str(params.version),
                  "coin_pair": str(params.coin_pair),
                  "price": str(params.price),
                  "price_timestamp": str(params.price_ts_utc),
                  "oracle_addr": params.oracle_addr,
                  "last_pub_block": str(params.last_pub_block),
                  "signature": my_signature.hex()
                  }
        raise_for_status = True
        response, status = await helpers.request_post(target_uri,
                                                      post_data,
                                                      timeout=timeout,
                                                      raise_for_status=raise_for_status)
        print("response")
        print(response)
        print("status")
        print(status)
        return response
    except asyncio.CancelledError as e:
        raise e
    except asyncio.TimeoutError as e:
        print("%s : Timeout from: %s, %s" % (params.coin_pair, oracle.addr, oracle.internetName))
        return
    except ClientResponseError as err:
        print("%s : Invalid response from: %s, %s -> %r" % (
            params.coin_pair, oracle.addr, oracle.internetName, err.message))
        return
    except ClientConnectorError:
        print("%s : Error connecting to: %s, %s" % (params.coin_pair, oracle.addr, oracle.internetName))
        return
    except InvalidURL:
        print("%s : The oracle %s, %s is registered with a wrong url!!!" % (
            params.coin_pair, oracle.addr, oracle.internetName))
        return
    except Exception as err:
        print(
            "%s : Unexpected exception from %s,%s: %r" % (
                params.coin_pair, oracle.addr, oracle.internetName, err))
        return


async def gets_signature_validated(is_idx):
    version = 1
    exchange_price = PriceWithTimestamp(11, 1)
    last_pub_block = 10
    for i in is_idx:
        publish_params = PublishPriceParams(version,
                                            CoinPair('BTCUSD'),
                                            exchange_price,
                                            selected_oracles[i][0].addr,
                                            last_pub_block)
        message = publish_params.prepare_price_msg()
        signature = crypto.sign_message(hexstr="0x" + message, account=oracle_settings.get_oracle_account())
        success = await make_sign_request(FullOracleRoundInfo(selected_oracles[i][0].addr, *selected_oracles[i][1:]),
                                    publish_params,
                                    signature)
        assert success
    #is_not_idx = [x for x in range(len(selected_oracles)) if x not in is_idx]
    #for i in is_not_idx:
    #    publish_params = PublishPriceParams(version,
    #                                        CoinPair('BTCUSD'),
    #                                        exchange_price,
    #                                        selected_oracles[i][0].addr,
    #                                        last_pub_block)
    #    message = publish_params.prepare_price_msg()
    #    signature = crypto.sign_message(hexstr="0x" + message, account=oracle_settings.get_oracle_account())
    #    success = await make_sign_request(FullOracleRoundInfo(selected_oracles[i][0].addr, *selected_oracles[i][1:]),
    #                                publish_params,
    #                                signature)
    #    assert not success

# Test that with no price change the chosen oracle has his turn validated but not the fallbacks
@pytest.mark.asyncio
async def test_success_oracle_turn_no_price_change():
    result = await gets_signature_validated([0])
    assert result