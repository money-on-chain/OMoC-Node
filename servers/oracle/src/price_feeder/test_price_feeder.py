import pytest
import time
import asyncio
import statistics

from oracle.src.price_feeder.price_feeder import TimeWithTimestampQueue, PriceFeederLoop
from common.services.oracle_dao import CoinPair
from common.services.contract_factory_service import ContractFactoryService
from oracle.src.oracle_configuration import OracleConfiguration


async def get_oracle_configuration():
    cf = ContractFactoryService.get_contract_factory_service()
    oracleConf = OracleConfiguration(cf)
    await oracleConf.initialize()
    return oracleConf

coin_pair = CoinPair('BTCUSD')

@pytest.mark.asyncio
async def test_right_price_in_time_get_last_price_passing_ts():
    oracleConfig = await get_oracle_configuration()
    price_feeder_loop = PriceFeederLoop(oracleConfig, coin_pair)
    sleep_time = 1
    counter = 0
    while counter < 30:
        await price_feeder_loop.run()
        await asyncio.sleep(sleep_time)
        counter += 1
    now_ts = time.time()
    price_data = []
    for j in price_feeder_loop._price_queues.keys():
        queue = price_feeder_loop._price_queues[j]
        data = queue.get_nearest_data(now_ts)
        price_data.append(data)
    price = await price_feeder_loop.get_last_price(now_ts)
    price_matches = [int(x['price'] * (10 ** price_feeder_loop._conf.ORACLE_PRICE_DIGITS)) == price.price for x in price_data]
    if not any(price_matches):
        assert False

@pytest.mark.asyncio
async def test_get_last_price_with_different_timestamps():
    oracleConfig = await get_oracle_configuration()
    price_feeder_loop = PriceFeederLoop(oracleConfig, coin_pair)
    wei_mult = 10 ** price_feeder_loop._conf.ORACLE_PRICE_DIGITS
    sleep_time = price_feeder_loop._conf.ORACLE_PRICE_FETCH_RATE
    counter = 0
    while counter < 30:
        await price_feeder_loop.run()
        await asyncio.sleep(sleep_time)
        counter += 1
    # looping of the amount of items in a queue (index)
    for i in range(len(price_feeder_loop._price_queues[list(price_feeder_loop._price_queues)[0]]._price_queue)):
        timestamps_current_index = []
        prices_current_index = []
        # looping of the keys of the price queues, meaning the exchanges' names
        for j in price_feeder_loop._price_queues.keys():
            queue = price_feeder_loop._price_queues[j]
            timestamps_current_index.append(queue._price_queue[i]['ts_utc'])
            prices_current_index.append(queue._price_queue[i]['data']['price'])
        # Now there's the list of ts of each exchange in the current index
        median_ts = statistics.median(timestamps_current_index)
        closest_ts = min(timestamps_current_index, key=lambda x:abs(x-median_ts))
        # Now there's a reasonable ts for this index to call get_last_price
        # and check it matches with one of the prices in this index.
        closest_ts_price = await price_feeder_loop.get_last_price(closest_ts)
        print(closest_ts_price)
        print(prices_current_index)
        if not any([int(x * wei_mult) == closest_ts_price.price for x in prices_current_index]):
            assert False

@pytest.mark.asyncio
async def test_get_nearest_data_with_different_timestamps():
    oracleConfig = await get_oracle_configuration()
    price_feeder_loop = PriceFeederLoop(oracleConfig, coin_pair)
    wei_mult = 10 ** price_feeder_loop._conf.ORACLE_PRICE_DIGITS
    sleep_time = 1
    counter = 0
    while counter < 30:
        await price_feeder_loop.run()
        await asyncio.sleep(sleep_time)
        counter += 1
    for j in price_feeder_loop._price_queues.keys():
        queue = price_feeder_loop._price_queues[j]
        for i in range(len(queue._price_queue)):
            current_ts = queue._price_queue[i]['ts_utc']
            assert int(queue._price_queue[i]['data']['price'] * wei_mult) == int(queue.get_nearest_data(current_ts)['price'] * wei_mult)
            assert current_ts == queue.get_nearest_data(current_ts)['timestamp'].timestamp()