import asyncio
import contextlib
import decimal
import json
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import aiohttp
import requests

from oracle.src import monitor
from oracle.src.oracle_configuration import OracleConfiguration


logger = logging.getLogger(__name__)

decimal.getcontext().prec = 28


def get_utc_time(timestamp_str):
    return datetime.fromtimestamp(int(timestamp_str), timezone.utc)


def get_utc_time_ms(timestamp_str):
    return datetime.fromtimestamp(int(timestamp_str) / 1000, timezone.utc)


def weighted_median(values, weights):
    idx = weighted_median_idx(values, weights)
    return values[idx]


def weighted_median_idx(values, weights):
    """Compute the weighted median of values list. The weighted median is computed as follows:
    1- sort both lists (values and weights) based on values.
    2- select the 0.5 point from the weights and return the corresponding values as results
    e.g. values = [1, 3, 0] and weights=[0.1, 0.3, 0.6] assuming weights are probabilities.
    sorted values = [0, 1, 3] and corresponding sorted weights = [0.6, 0.1, 0.3] the 0.5 point on
    weight corresponds to the first item which is 0. so the weighted median is 0."""

    # convert the weights into probabilities
    sum_weights = sum(weights)
    weights = [w / sum_weights for w in weights]
    # sort values and weights based on values
    sorted_tuples = sorted(zip(values, weights, range(len(values))))

    # select the median point
    cumulative_probability = 0
    for i in range(len(sorted_tuples)):
        cumulative_probability += sorted_tuples[i][1]
        if cumulative_probability > 0.5:
            return sorted_tuples[i][2]
        elif cumulative_probability == 0.5:
            # if i + 1 >= len(sorted_tuples):
            return sorted_tuples[i][2]
            # return (sorted_tuples[i][2] + sorted_tuples[i + 1][2]) / 2
    return sorted_tuples[-1][2]


@contextlib.contextmanager
def closing(thing):
    try:
        yield thing
    finally:
        asyncio.create_task(thing.close())


class PriceEngineBase(object):
    name = "base_engine"
    description = "Base Engine"
    uri = None
    convert = "BTC_USD"

    def __init__(self, conf: OracleConfiguration, log, timeout=10, uri=None):
        self._conf = conf
        self.log = log
        self.timeout = timeout
        if uri:
            self.uri = uri

    def send_alarm(self, message, level=0):
        self.log.error(message)

    async def fetch(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.uri, timeout=self.timeout) as response:
                    # print("Status:", response.status)
                    # print("Content-type:", response.headers['content-type'])
                    age = int(response.headers.get('age', '0'))
                    response.raise_for_status()
                    if not response:
                        err_msg = "Error! No response from server on get price. Engine: {0}".format(self.name)
                        self.send_alarm(err_msg)
                        return None, None, err_msg

                    if response.status != 200:
                        err_msg = "Error! Error response from server on get price. Engine: {0}".format(self.name)
                        self.send_alarm(err_msg)
                        return None, None, err_msg
                    jsonTxt = await response.json(loads=lambda x: json.loads(x, parse_float=Decimal))
                    return jsonTxt, age, ""
        except asyncio.CancelledError as e:
            raise e
        except requests.exceptions.HTTPError as http_err:
            err_msg = "Error! Error response from server on get price. Engine: {0}. {1}".format(self.name, http_err)
            self.send_alarm(err_msg)
            return None, None, err_msg
        except Exception as err:
            err_msg = "Error. Error response from server on get price. Engine: {0}. {1}".format(self.name, err)
            self.send_alarm(err_msg)
            return None, None, err_msg

    async def get_price(self):
        response_json, age, err_msg = await self.fetch()
        if not response_json:
            return None, err_msg
        try:
            d_price_info = self.map(response_json, age)
        except asyncio.CancelledError as e:
            raise e
        except Exception as err:
            err_msg = "Error. Error response from server on get price. Engine: {0}. {1}".format(self.name, err)
            self.send_alarm(err_msg)
            return None, err_msg

        if (datetime.now(timezone.utc)-d_price_info["timestamp"]
            )>timedelta(seconds=self._conf.ORACLE_PRICE_RECEIVE_MAX_AGE):
            d_price_info["price"] = Decimal("NAN")
            d_price_info["timestamp"] = datetime.now(timezone.utc)
        return d_price_info, None

    def map(self, response_json, age):
        return {'timestamp': datetime.now(timezone.utc) - timedelta(seconds=age)}


class BitstampBTCUSD(PriceEngineBase):
    name = "bitstamp_btc_usd"
    description = "Bitstamp"
    uri = "https://www.bitstamp.net/api/v2/ticker/btcusd/"
    convert = "BTC_USD"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json['last'])
        d_price_info['volume'] = Decimal(response_json['volume'])
        d_price_info['timestamp'] = get_utc_time(response_json['timestamp'])
        return d_price_info


class CoinBaseBTCUSD(PriceEngineBase):
    name = "coinbase_btc_usd"
    description = "Coinbase"
    uri = "https://api.coinbase.com/v2/prices/spot?currency=USD"
    convert = "BTC_USD"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json['data']['amount'])
        d_price_info['volume'] = 0.0
        return d_price_info


class BitGOBTCUSD(PriceEngineBase):
    name = "bitgo_btc_usd"
    description = "BitGO"
    uri = "https://www.bitgo.com/api/v1/market/latest"
    convert = "BTC_USD"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json['latest']['currencies']['USD']['last'])
        d_price_info['volume'] = Decimal(response_json['latest']['currencies']['USD']['total_vol'])
        d_price_info['timestamp'] = get_utc_time(response_json['latest']['currencies']['USD']['timestamp'])
        return d_price_info


class BitfinexBTCUSD(PriceEngineBase):
    name = "bitfinex_btc_usd"
    description = "Bitfinex"
    uri = "https://api-pub.bitfinex.com/v2/ticker/tBTCUSD"
    convert = "BTC_USD"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json[6])
        d_price_info['volume'] = Decimal(response_json[7])
        return d_price_info


class BlockchainBTCUSD(PriceEngineBase):
    name = "blockchain_btc_usd"
    description = "Blockchain"
    uri = "https://blockchain.info/ticker"
    convert = "BTC_USD"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json['USD']['last'])
        d_price_info['volume'] = 0.0
        return d_price_info


class BinanceBTCUSD(PriceEngineBase):
    name = "binance_btc_usd"
    description = "Binance"
    uri = "https://api.binance.com/api/v1/ticker/24hr?symbol=BTCUSDT"
    convert = "BTC_USD"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json['lastPrice'])
        d_price_info['volume'] = Decimal(response_json['volume'])
        return d_price_info


class BinanceRIFBTC(PriceEngineBase):
    name = "binance_rif_btc"
    description = "Binance RIF"
    uri = "https://api.binance.com/api/v3/ticker/24hr?symbol=RIFBTC"
    convert = "RIF_BTC"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json['lastPrice'])
        d_price_info['volume'] = Decimal(response_json['volume'])
        d_price_info['timestamp'] = datetime.fromtimestamp(
                                        int(response_json["closeTime"])/1000,
                                        tz=timezone.utc)
        return d_price_info


class MxcRIFBTC(PriceEngineBase):
    name = "mxc_rif_btc"
    description = "MXC RIF"
    uri = "https://www.mxc.com/open/api/v2/market/ticker?symbol=RIF_BTC"
    convert = "RIF_BTC"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json['last'])
        d_price_info['volume'] = Decimal(response_json['volume'])
        #d_price_info['timestamp'] = datetime.fromtimestamp(
        #                                int(response_json["closeTime"])/1000,
        #                                tz=timezone.utc)
        return d_price_info


class KucoinBTCUSD(PriceEngineBase):
    name = "kucoin_btc_usd"
    description = "Kucoin"
    uri = "https://api.kucoin.com/api/v1/market/stats?symbol=BTC-USDT"
    convert = "BTC_USD"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json['data']['last'])
        d_price_info['volume'] = Decimal(response_json['data']['vol'])
        return d_price_info


class KrakenBTCUSD(PriceEngineBase):
    name = "kraken_btc_usd"
    description = "Kraken"
    uri = "https://api.kraken.com/0/public/Ticker?pair=XXBTZUSD"
    convert = "BTC_USD"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json['result']['XXBTZUSD']['c'][0])
        d_price_info['volume'] = Decimal(response_json['result']['XXBTZUSD']['v'][1])
        return d_price_info


class BittrexBTCUSD(PriceEngineBase):
    name = "bittrex_btc_usd"
    description = "Bittrex"
    uri = "https://api.bittrex.com/api/v1.1/public/getticker?market=USD-BTC"
    convert = "BTC_USD"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json['result']['Last'])
        d_price_info['volume'] = 0.0
        return d_price_info


class GeminiBTCUSD(PriceEngineBase):
    name = "gemini_btc_usd"
    description = "Gemini"
    uri = "https://api.gemini.com/v1/pubticker/BTCUSD"
    convert = "BTC_USD"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json['last'])
        d_price_info['volume'] = 0.0
        return d_price_info


class OkCoinBTCUSD(PriceEngineBase):
    name = "okcoin_btc_usd"
    description = "OkCoin"
    uri = "https://www.okcoin.com/api/spot/v3/instruments/BTC-USD/ticker"
    convert = "BTC_USD"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json['last'])
        d_price_info['volume'] = 0.0
        return d_price_info


class ItBitBTCUSD(PriceEngineBase):
    name = "itbit_btc_usd"
    description = "ItBit"
    uri = "https://api.itbit.com/v1/markets/XBTUSD/ticker"
    convert = "BTC_USD"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json['lastPrice'])
        d_price_info['volume'] = 0.0
        return d_price_info


# RIF BTC
class BitfinexRIFBTC(PriceEngineBase):
    name = "bitfinex_rif_btc"
    description = "Bitfinex RIF"
    uri = "https://api-pub.bitfinex.com/v2/ticker/tRIFBTC"
    convert = "RIF_BTC"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json[6])
        d_price_info['volume'] = Decimal(response_json[7])
        return d_price_info


class BithumbproRIFBTC(PriceEngineBase):
    name = "bithumbpro_rif_btc"
    description = "BitHumb RIF"
    uri = "https://global-openapi.bithumb.pro/openapi/v1/spot/ticker?symbol=RIF-BTC"
    convert = "RIF_BTC"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json['data'][0]['c'])
        d_price_info['volume'] = Decimal(response_json['data'][0]['v'])
        return d_price_info


class CoinbeneRIFBTC(PriceEngineBase):
    name = "coinbene_rif"
    description = "Coinbene_RIF"
    uri = "https://api.coinbene.com/v1/market/ticker?symbol=RIFBTC"
    convert = "RIF_BTC"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json['ticker'][0]['last'])
        d_price_info['volume'] = Decimal(response_json['ticker'][0]['24hrVol'])
        return d_price_info


class KucoinRIFBTC(PriceEngineBase):
    name = "kucoin_rif"
    description = "Kucoin_RIF"
    uri = "https://openapi-v2.kucoin.com/api/v1/market/orderbook/level1?symbol=RIF-BTC"
    convert = "RIF_BTC"

    def map(self, response_json, age):
        d_price_info = super().map(response_json, age)
        d_price_info['price'] = Decimal(response_json['data']['price'])
        d_price_info['volume'] = Decimal(response_json['data']['size'])
        d_price_info['timestamp'] = get_utc_time_ms(response_json['data']['time'])
        return d_price_info


base_engines_names = {
    "coinbase": CoinBaseBTCUSD,
    "bitstamp": BitstampBTCUSD,
    "bitgo": BitGOBTCUSD,
    "bitfinex": BitfinexBTCUSD,
    "blockchain": BlockchainBTCUSD,
    "bittrex": BittrexBTCUSD,
    "kraken": KrakenBTCUSD,
    "kucoin": KucoinBTCUSD,
    "binance": BinanceBTCUSD,
    "gemini": GeminiBTCUSD,
    "okcoin": OkCoinBTCUSD,
    "itbit": ItBitBTCUSD,
    "bitfinex_rif": BitfinexRIFBTC,
    "bithumbpro_rif": BithumbproRIFBTC,
    "coinbene_rif": CoinbeneRIFBTC,
    "kucoin_rif": KucoinRIFBTC,
    "binance_rif": BinanceRIFBTC,
    "mxc_rif": MxcRIFBTC,
}


class LogMeta(object):

    @staticmethod
    def info(msg):
        logger.info("INFO: {0}".format(msg))

    @staticmethod
    def error(msg):
        logger.error("ERROR: {0}".format(msg))

    @staticmethod
    def warning(msg):
        logger.error("WARNING: {0}".format(msg))


class PriceEngines(object):
    def __init__(self, conf: OracleConfiguration, coin_pair: str,
                 price_options, log=None, engines_names=None):
        self._conf = conf
        self._coin_pair = coin_pair
        self.price_options = price_options
        self.log = log
        if not self.log:
            self.log = LogMeta()
        self.engines_names = engines_names
        if not engines_names:
            self.engines_names = base_engines_names
        self.engines = []
        self.add_engines()

    def add_engines(self):
        for price_engine in self.price_options:
            engine_name = price_engine["name"]

            if engine_name not in self.engines_names:
                raise Exception("The engine price name not in the available list")

            engine = self.engines_names.get(engine_name)
            i_engine = engine(self._conf, self.log)

            d_engine = dict()
            d_engine["engine"] = i_engine
            d_engine["ponderation"] = price_engine["ponderation"]
            d_engine["min_volume"] = price_engine["min_volume"]
            d_engine["max_delay"] = price_engine["max_delay"]
            d_engine["name"] = engine_name
            self.engines.append(d_engine)

    async def fetch_prices(self):
        async def azip(engine):
            return (engine, await engine["engine"].get_price())

        cor = [azip(engine) for engine in self.engines]
        p_data = await asyncio.gather(*cor, return_exceptions=True)
        prices = []
        for (engine, (d_price, err_msg)) in p_data:
            if d_price:
                i_price = dict()
                i_price['name'] = engine["name"]
                i_price['ponderation'] = engine["ponderation"]
                i_price['price'] = d_price["price"]
                i_price['volume'] = d_price["volume"]
                i_price['timestamp'] = d_price["timestamp"]
                i_price['min_volume'] = engine["min_volume"]
                i_price['max_delay'] = engine["max_delay"]

                if i_price["min_volume"] > 0:
                    # the evaluation of volume is on
                    if not i_price['volume'] > i_price["min_volume"]:
                        # is not added to the price list
                        self.log.warning("Not added to the list because is not at to the desire volume: %s" %
                                         i_price['name'])
                        continue
                prices.append(i_price)
        return prices

    def get_weighted_from(self, f_prices):
        l_prices, l_weights, _idxback = zip(
                *( (p_price['price'], Decimal(p_price['ponderation']), idx)
                    for idx, p_price in enumerate(f_prices)
                                            if p_price['price'].is_finite()) )
        if len(l_prices)==0:
            return None
        idx = weighted_median_idx(l_prices, l_weights)
        monitor.exchange_log("%s median: %s" % (self._coin_pair, l_prices[idx]))
        return f_prices[_idxback[idx]]

    def get_weighted_median(self, f_prices):
        f_price = self.get_weighted_from(f_prices)
        return f_price['price']

    async def get_weighted(self):
        f_prices = await self.fetch_prices()
        monitor.report_prices(self.engines, f_prices)
        return f_prices
