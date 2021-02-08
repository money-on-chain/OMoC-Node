import os
from datetime import datetime, timedelta
from decimal import Decimal

import pytest


os.environ['REGISTRY_ADDR'] = '0x'+('0'*40)

from common import settings
from common.services.contract_factory_service import ContractFactoryService
from common.services.oracle_dao import CoinPair
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.price_feeder.price_feeder import PriceFeederLoop
from oracle.src.price_feeder.moc_price_engines import PriceEngineBase
from oracle.src.price_feeder.moc_price_engines import PriceEngines, LogMeta, \
    base_engines_names


def get_oracle_configuration():
    settings.NODE_URL = 'http://localhost'
    cf = ContractFactoryService.get_contract_factory_service()
    oracleConf = OracleConfiguration(cf)
    # default is not set by default... !!
    oracleConf.ORACLE_PRICE_FETCH_RATE = 5
    oracleConf.ORACLE_QUEUE_LEN = 30
    oracleConf.ORACLE_PRICE_RECEIVE_MAX_AGE = 30
    oracleConf.ORACLE_PRICE_PUBLISH_MAX_DIFF = 30
    oracleConf.ORACLE_PRICE_VALIDATE_MAX_DIFF = 30
    return oracleConf

Conf = get_oracle_configuration()


@pytest.mark.exchanges
@pytest.mark.asyncio
async def test_fetch_from_all_exchanges():
    log = LogMeta()
    for name in base_engines_names.keys():
        engine = base_engines_names[name](log)
        json, _, err_msg = await engine.fetch()
        print("------------------->", name, json,
              type(engine.map(json)["price"]))


def PriceMockPriceEngineTest(price, volume=0.0, age=0):
    class PriceEngineTest(PriceEngineBase):
        def __init__(self, conf=Conf, log=LogMeta()):
            super().__init__(conf, log)

        async def fetch(self):
            return (Decimal(price), volume), age, ""

        def map(self, response_json, age):
            price, vol = response_json
            d_price_info = super().map(response_json, age)
            d_price_info['price'] = price
            d_price_info['volume'] = vol
            return d_price_info
    return PriceEngineTest


class ErrorPriceEngine(PriceEngineBase):
    async def get_price(self):
        return None, "Error"


@pytest.mark.asyncio
async def test_engines1():
    pr_engine = PriceEngines(Conf, "BTCUSD", [
        {"name": "test_1", "ponderation": Decimal('0.1605'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_2", "ponderation": Decimal('0.2138'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_3", "ponderation": Decimal('0.2782'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_4", "ponderation": Decimal('0.3475'), "min_volume": 0.0,
         "max_delay": 0}
    ], engines_names={
        "test_1": PriceMockPriceEngineTest('7250.10'),
        "test_2": PriceMockPriceEngineTest('7258.32'),
        "test_3": PriceMockPriceEngineTest('7283.81'),
        "test_4": PriceMockPriceEngineTest('7286.25'),
    })
    w_prices = await pr_engine.get_weighted()
    w_median = pr_engine.get_weighted_median(w_prices)
    # Taken from running price-feeder/price_test.py
    assert w_median == Decimal('7283.81')


@pytest.mark.asyncio
async def test_engines2():
    pr_engine = PriceEngines(Conf, "BTCUSD", [
        {"name": "test_5", "ponderation": Decimal('0.1605'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_6", "ponderation": Decimal('0.2782'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_7", "ponderation": Decimal('0.3475'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_8", "ponderation": Decimal('0.2138'), "min_volume": 0.0,
         "max_delay": 0}
    ], engines_names={
        "test_5": PriceMockPriceEngineTest('7250.10'),
        "test_6": PriceMockPriceEngineTest('7283.81'),
        "test_7": PriceMockPriceEngineTest('7286.25'),
        "test_8": PriceMockPriceEngineTest('7984.15')
    })
    w_prices = await pr_engine.get_weighted()
    w_median = pr_engine.get_weighted_median(w_prices)
    # Taken from running price-feeder/price_test.py
    assert w_median == Decimal('7286.25')


@pytest.mark.asyncio
async def test_engines3():
    pr_engine = PriceEngines(Conf, "BTCUSD", [
        {"name": "test_9", "ponderation": Decimal('0.1605'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_10", "ponderation": Decimal('0.2782'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_11", "ponderation": Decimal('0.3475'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_12", "ponderation": Decimal('0.2138'), "min_volume": 0.0,
         "max_delay": 0}
    ], engines_names={
        "test_9": PriceMockPriceEngineTest('7250.1'),
        "test_10": PriceMockPriceEngineTest('7283.81'),
        "test_11": PriceMockPriceEngineTest('7286.25'),
        "test_12": ErrorPriceEngine
    })
    w_prices = await  pr_engine.get_weighted()
    w_median = pr_engine.get_weighted_median(w_prices)
    # Taken from running price-feeder/price_test.py
    assert w_median == Decimal('7283.81')


@pytest.mark.asyncio
async def test_engines4():
    pr_engine = PriceEngines(Conf, "BTCUSD", [
        {"name": "test_13", "ponderation": Decimal('0.2782'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_14", "ponderation": Decimal('0.2138'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_15", "ponderation": Decimal('0.3475'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_16", "ponderation": Decimal('0.1605'), "min_volume": 0.0,
         "max_delay": 0}
    ], engines_names={
        "test_13": PriceMockPriceEngineTest('8000'),
        "test_14": PriceMockPriceEngineTest('7000'),
        "test_15": PriceMockPriceEngineTest('7000'),
        "test_16": PriceMockPriceEngineTest('7000')
    })
    w_prices = await pr_engine.get_weighted()
    w_median = pr_engine.get_weighted_median(w_prices)
    # Taken from running price-feeder/price_test.py
    assert w_median == Decimal('7000')


@pytest.mark.asyncio
async def test_float_fail():
    pr_engine = PriceEngines(Conf, "BTCUSD", [
        {"name": "test_17", "ponderation": 0.2782, "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_18", "ponderation": 0.2138, "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_19", "ponderation": 0.3475, "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_20", "ponderation": 0.1605, "min_volume": 0.0,
         "max_delay": 0}
    ], engines_names={
        "test_17": PriceMockPriceEngineTest(0.1 + 0.2),
        "test_18": PriceMockPriceEngineTest(0.1 + 0.2),
        "test_19": PriceMockPriceEngineTest(0.1 + 0.2),
        "test_20": PriceMockPriceEngineTest(0.1 + 0.2)
    })
    w_prices = await pr_engine.get_weighted()
    w_median = pr_engine.get_weighted_median(w_prices)
    # Taken from running price-feeder/price_test.py
    assert w_median == 0.30000000000000004


@pytest.mark.asyncio
async def test_age():
    """check that when used a fallback timestamp it is adjusted according the
    age"""
    engine = PriceMockPriceEngineTest(0.0, age=5)()  # MockedEngine(5)
    price_data = (await engine.get_price())[0]
    print(repr(price_data))
    ts = price_data["timestamp"]
    now = datetime.now(price_data["timestamp"].tzinfo)
    assert now - ts > timedelta(seconds=0)
    assert now - ts > timedelta(seconds=1)
    assert now - ts < timedelta(seconds=10)


@pytest.mark.asyncio
async def test_age2():
    """When age is > X:
        * price returned must be NaN
        * date should be current
    """
    engine = PriceMockPriceEngineTest(0.0, age=31)()
    price_data = (await engine.get_price())[0]
    assert price_data["price"].is_nan()
    ts = price_data["timestamp"]
    now = datetime.now(price_data["timestamp"].tzinfo)
    assert now - ts >= timedelta(seconds=0)
    assert now - ts < timedelta(seconds=5)


@pytest.mark.asyncio
async def test_age3():
    """When age is > X:
        * price returned must be NaN
        * date should be current
    """
    engine = PriceMockPriceEngineTest(0.0, age=31)()
    price_data = (await engine.get_price())[0]
    assert price_data["price"].is_nan()
    ts = price_data["timestamp"]
    now = datetime.now(price_data["timestamp"].tzinfo)
    assert now - ts >= timedelta(seconds=0)
    assert now - ts < timedelta(seconds=5)


def ListedPriceMockPriceEngineTest(price_time_list):
    class PriceEngineTest(PriceEngineBase):
        def __init__(self, conf=Conf, log=LogMeta()):
            super().__init__(conf, log)
            self.idx = 0

        async def fetch(self):
            price, self.dt = price_time_list[self.idx]
            self.idx += 1
            return (Decimal(price), 0.0), 0, ""

        def map(self, response_json, age):
            price, vol = response_json
            d_price_info = super().map(response_json, age)
            d_price_info['price'] = price
            d_price_info['volume'] = vol
            d_price_info['timestamp'] = self.dt
            return d_price_info
    return PriceEngineTest



# ------------------------------------------------------------------------------

_1sec = timedelta(seconds=1)
now = datetime.now()
NAN = Decimal("NAN")
LE = lambda *args: list(enumerate(args))

@pytest.mark.parametrize("schedule,searchfor,result", [
        #schedule, searchfor, result
        ## the one searched for is returned when exists
        (LE( now - 1 * _1sec, now, now + _1sec),
         now + 0 * _1sec, 1),
        ## when two prices left and right match distance, choose right
        (LE(now - 2 * _1sec, now - 1 * _1sec, now + _1sec, now + 2 * _1sec),
         now + 0 * _1sec, 2),
        ## when a price on the left and a NaN on the right, choose right
        ([(0,now - 2 * _1sec),
          (1,now - 1 * _1sec),
          (NAN,now + 1 * _1sec),
          (3,now + 2 * _1sec)],
         now + 0 * _1sec, NAN),
        # if we are at the left of any price, return the first one
        (LE(now - 1 * _1sec, now, now + _1sec),
         now - 2 * _1sec, 0),
        # if we are at the right of any price, return the last one
        (LE(now - 1 * _1sec, now, now + _1sec),
         now + 2 * _1sec, 2),
        #  also for NaN
        ([(NAN,now - 1 * _1sec),
          (0,now + 0 * _1sec),
          (1,now + 1 * _1sec)],
         now - 2 * _1sec, NAN),
        # if we are at the right of any price, return the last one
        ([(0,now - 1 * _1sec),
          (1,now + 0 * _1sec),
          (NAN,now + 1 * _1sec)],
         now + 2 * _1sec, NAN),
])
@pytest.mark.asyncio
async def test_selection(schedule, searchfor, result):
    coin_pair = CoinPair('BTCUSD')
    price_feeder_loop = PriceFeederLoop(Conf, coin_pair)
    price_feeder_loop._moc_price_engines = PriceEngines(Conf, "BTCUSD", [
        {"name": "test", "ponderation": 1, "min_volume": 0.0,
         "max_delay": 0},
    ], engines_names={"test": ListedPriceMockPriceEngineTest(schedule)})

    # fill the queue..
    for _ in schedule:
        await price_feeder_loop.run()

    # select from queue..
    for queue in price_feeder_loop._price_queues.values():
        price = queue.get_nearest_data(searchfor.timestamp())['price']
        if isinstance(result, Decimal) and result.is_nan():
            assert price.is_nan()
        else:
            assert price==result


@pytest.mark.asyncio
async def test_ponderation_excess_handled():
    pr_engine = PriceEngines(Conf, "BTCUSD", [
        {"name": "test_9", "ponderation": Decimal('0.33'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_10", "ponderation": Decimal('0.33'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_11", "ponderation": Decimal('0.33'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_12", "ponderation": Decimal('0.33'), "min_volume": 0.0,
         "max_delay": 0}
    ], engines_names={
        "test_9": PriceMockPriceEngineTest('10'),
        "test_10": PriceMockPriceEngineTest('10'),
        "test_11": PriceMockPriceEngineTest('10'),
        "test_12": PriceMockPriceEngineTest('10'),
    })
    w_prices = await  pr_engine.get_weighted()
    w_median = pr_engine.get_weighted_median(w_prices)
    assert w_median == Decimal('10')


@pytest.mark.asyncio
async def test_ponderation_excess_is_handled_when_engine_failure():
    pr_engine = PriceEngines(Conf, "BTCUSD", [
        {"name": "test_9", "ponderation": Decimal('0.4'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_10", "ponderation": Decimal('0.5'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_11", "ponderation": Decimal('0.6'), "min_volume": 0.0,
         "max_delay": 0},
        {"name": "test_12", "ponderation": Decimal('0.6'), "min_volume": 0.0,
         "max_delay": 0}
    ], engines_names={
        "test_9": PriceMockPriceEngineTest('10'),
        "test_10": PriceMockPriceEngineTest('10'),
        "test_11": PriceMockPriceEngineTest('10'),
        "test_12": ErrorPriceEngine,
    })
    w_prices = await  pr_engine.get_weighted()
    w_median = pr_engine.get_weighted_median(w_prices)
    assert w_median == Decimal('10')
