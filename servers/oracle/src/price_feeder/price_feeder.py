import asyncio
import collections
import logging

from common.bg_task_executor import BgTaskExecutor
from common.services.oracle_dao import CoinPair, PriceWithTimestamp
from oracle.src import oracle_settings, monitor
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.price_feeder import moc_price_engines

logger = logging.getLogger(__name__)


class TimeWithTimestampQueue:
    def __init__(self, conf: OracleConfiguration, name):
        self.name = name
        self._price_queue = collections.deque(maxlen=conf.ORACLE_QUEUE_LEN)

    def get_nearest_data(self, target_time_utc):
        if len(self._price_queue)==0:
            return None
        ret1 = min(self._price_queue, key=lambda x: abs(target_time_utc - x["ts_utc"]))
        ret2 = self.min_without(target_time_utc, ret1)
        if ret2 is None:
            ret = ret1
        else:
            d_ret1 = ret1["ts_utc"]-target_time_utc
            d_ret2 = ret2["ts_utc"]-target_time_utc
            if abs(d_ret1)!=abs(d_ret2):
                ret = ret1
            else:
                ret = ret1 if d_ret1>0 else ret2
        return ret["data"]

    def min_without(self, target_time_utc, x):
        list_without = [y for y in self._price_queue if y['ts_utc']!=x['ts_utc']]
        if len(list_without)==0:
            return None
        return min(list_without, key=lambda x: abs(target_time_utc - x["ts_utc"]))

    def append(self, ts_utc, data):
        data['ts_utc']=ts_utc
        self._price_queue.append({"ts_utc": ts_utc, "data": data})


class PriceFeederLoop(BgTaskExecutor):
    def __init__(self, conf: OracleConfiguration, coin_pair: CoinPair):
        self._conf = conf
        self._price_queues = {}
        self._coin_pair = str(coin_pair)
        engines = oracle_settings.ORACLE_PRICE_ENGINES[self._coin_pair]
        self._moc_price_engines = moc_price_engines.PriceEngines(conf, self._coin_pair, engines)
        self.maxdiffs = {
            True: conf.ORACLE_PRICE_PUBLISH_MAX_DIFF,        # publish
            False: conf.ORACLE_PRICE_VALIDATE_MAX_DIFF,      # validate
        }
        super().__init__(name="PriceFeederLoop", main=self.run)

    @property
    def coin_pair(self):
        return self._coin_pair

    async def get_last_price(self, target_time_utc, to_publish) -> PriceWithTimestamp or None:
        MAX = self.maxdiffs[to_publish]
        w_data = [q.get_nearest_data(target_time_utc)
                                        for q in self._price_queues.values()]
        # avoid the following situations:
        #  * no data (None)
        #  * data is NoPrice (NaN)
        #  * data outside the required freshness period (>MAX)
        w_data = [x for x in w_data if (x is not None) and
                                        x["price"].is_finite() and
                                        abs(target_time_utc - x["ts_utc"])<=MAX]
        if len(w_data) == 0:
            return

        val = self._moc_price_engines.get_weighted_from(w_data)
        if val is None:  # in case there are no prices available at all
            return
        tm_utc = val['timestamp'].timestamp()
        price = val['price']

        l_times = [p_price['timestamp'].timestamp() for p_price in w_data]
        l_names = [p_price['name'] for p_price in w_data]
        l_prices = [p_price['price'] for p_price in w_data]

        info = [(x[1], str(x[0]), x[2]) for x in sorted(zip(l_prices, l_names, l_times))]


        #logger.info("%s median: %r %r %r, %r" % (self._coin_pair, val['name'],
        #                                                 str(price), tm_utc, info))

        last_price_fetch_wei = int(price * (10 ** self._conf.ORACLE_PRICE_DIGITS))
        #logger.info("%s got price: %s, timestamp %r" % (self._coin_pair,
        #                                                last_price_fetch_wei,
        #                                                tm_utc))
        return PriceWithTimestamp(last_price_fetch_wei, tm_utc)

    async def run(self):
        try:
            w_data = await self._moc_price_engines.get_weighted()
            for val in w_data:
                name = val['name']
                tm_utc = val['timestamp'].timestamp()
                if name not in self._price_queues:
                    self._price_queues[name] = TimeWithTimestampQueue(self._conf, name)
                logger.debug("%s insert: %s -> %s, timestamp %r" % (self._coin_pair, name, val['price'], tm_utc))
                self._price_queues[name].append(tm_utc, val)
            return self._conf.ORACLE_PRICE_FETCH_RATE
        except asyncio.CancelledError as e:
            raise e
        except Exception as ex:
            monitor.exchange_log("ERROR FETCHING PRICE %r" % ex)
            logger.error("ERROR FETCHING PRICE %r" % ex)
        return self._conf.ORACLE_PRICE_FETCH_RATE
