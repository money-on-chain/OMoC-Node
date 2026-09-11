from starlette.config import Config
from starlette.datastructures import URL

import os
import pathlib
import sys
from common.helpers import parseTimeDelta
from decimal import Decimal

try:
    config = Config(".env")
except FileNotFoundError as e:
    print(e, file=sys.stderr)
    exit(1)

# Block chain server url
NODE_URL = config('NODE_URL', cast=URL, default=None)
# Block chain chain id
CHAIN_ID = config('CHAIN_ID', cast=str, default=None)

# If this parameter is set we use the moneyonchain library abis and addresses.
# In not then we use the build directory
MOC_NETWORK = config('MOC_NETWORK', cast=str, default=None)
# If we use the build directory (MOC_NETWORK unconfigured) we must set this parameter to the block chain network id
DEVELOP_NETWORK_ID = config('DEVELOP_NETWORK_ID', cast=int, default=None)
CONTRACT_ROOT_FOLDER = config('CONTRACT_ROOT_FOLDER', cast=pathlib.Path,
                              default=pathlib.Path(os.path.dirname(os.path.realpath(__file__))).parent)
# The server expect to find in this folder the *.json files with the abi an addresses of contracts
CONTRACT_FOLDER = config('CONTRACT_FOLDER', cast=pathlib.Path,
                         default=os.path.join(CONTRACT_ROOT_FOLDER, "build", "contracts"))

try:
    REGISTRY_ADDR = config('REGISTRY_ADDR', cast=str)
except KeyError as e:
    print("Config env 'REGISTRY_ADDR' is missing.", file=sys.stderr)
    exit(1)

# Timeout used when connection to the blockchain node
WEB3_TIMEOUT = parseTimeDelta(config('WEB3_TIMEOUT', cast=str, default="30 secs"))

# Turn on debug?
DEBUG = config('DEBUG', cast=bool, default=False)
UVICOIN_DEBUG = config('UVICOIN_DEBUG', cast=bool, default=False)
LOG_LEVEL = config('LOG_LEVEL', cast=str, default="info")
# Add some development endpoints
DEBUG_ENDPOINTS = config('DEBUG_ENDPOINTS', cast=bool, default=False)
# Reload on source code change, used for development
RELOAD = config('RELOAD', cast=bool, default=False)
# Populate remote address info.
PROXY_HEADERS = config('PROXY_HEADERS', cast=bool, default=False)
# Print stack trace of errors, used for development
ON_ERROR_PRINT_STACK_TRACE = config('ON_ERROR_PRINT_STACK_TRACE', cast=bool, default=False)
# Swagger app version
VERSION = "1.3.7.3"

# These four are for the gas_price fix. Sometimes the gas_price reaches 20Gwei
# Used the first time if the gas price exceeds the admitted
DEFAULT_GAS_PRICE = config('DEFAULT_GAS_PRICE', cast=int, default=65800000)
# The percentage that is considered to be admitted
GAS_PERCENTAGE_ADMITTED = config('GAS_PERCENTAGE_ADMITTED', cast=int, default=10)
# Hard limits to the gas price
GAS_PRICE_HARD_LIMIT_MIN = config('GAS_PRICE_HARD_LIMIT_MIN', cast=int, default=0)  # 0 means no limit
GAS_PRICE_HARD_LIMIT_MAX = config('GAS_PRICE_HARD_LIMIT_MAX', cast=int, default=0)  # 0 means no limit
GAS_PRICE_HARD_LIMIT_MULTIPLIER = config('GAS_PRICE_HARD_LIMIT_MULTIPLIER', cast=int, default=1)  # 1 means no changes

COIN_PAIR_SW_ROUND_GAS_LIMIT = config('COIN_PAIR_SW_ROUND_GAS_LIMIT', cast=int, default=2500000)
TASKS_RUNNER_MIN_GAS = config('TASKS_RUNNER_MIN_GAS', cast=int, default=0)
LIQUIDATION_ENGINE_GAS_LIMIT = config('LIQUIDATION_ENGINE_GAS_LIMIT', cast=int, default=0)

# Local lending indexing is opt-in. Markets is a JSON array with ``tpToken``
# and ``mocBucket`` addresses.
LENDING_INDEXER_ENABLED = config('LENDING_INDEXER_ENABLED', cast=bool, default=False)
LENDING_MANAGER_ADDRESS = config('LENDING_MANAGER_ADDRESS', cast=str, default='')
LENDING_DEPLOYMENT_BLOCK = config('LENDING_DEPLOYMENT_BLOCK', cast=int, default=0)
LENDING_DB_PATH = config('LENDING_DB_PATH', cast=str, default='lending-index.sqlite3')
LENDING_CONFIRMATIONS = config('LENDING_CONFIRMATIONS', cast=int, default=2)
LENDING_GET_LOGS_BLOCK_RANGE = config(
    'LENDING_GET_LOGS_BLOCK_RANGE', cast=int, default=2000
)
LENDING_INDEX_INTERVAL = config('LENDING_INDEX_INTERVAL', cast=float, default=10.0)
LENDING_DISCOVERY_TIMEOUT = config('LENDING_DISCOVERY_TIMEOUT', cast=float, default=2.0)
LENDING_MAX_LAG_BLOCKS = config('LENDING_MAX_LAG_BLOCKS', cast=int, default=20)
LENDING_REORG_RETENTION_BLOCKS = config(
    'LENDING_REORG_RETENTION_BLOCKS', cast=int, default=1000
)
LENDING_LIQUIDATION_MARKETS = config(
    'LENDING_LIQUIDATION_MARKETS', cast=str, default='[]'
)

MOC_PRICE_SOURCES_API_URI = config('MOC_PRICE_SOURCES_API_URI', cast=str, default='http://localhost:7989')
OFFLINE_CFG_URL = MOC_PRICE_SOURCES_API_URI + "/api/coinpairs/get_value_simple?coinpair="

PER_CHAIN_ID_DEFAULTS={
    '30':{ # RSK Mainnet
        'GAS_LIMIT_ADDR': '0xf773B590aF754D597770937Fa8ea7AbDf2668370',
        'MULTICALL_ADDR': '0x8F344C3B2a02a801c24635F594C5652c8A2eB02a',
       
        # Allow ORACLE_OFFLINE_CFG to be driven by endpoint URL
        # 'ORACLE_OFFLINE_CFG_RIFUSD': OFFLINE_CFG_URL + "ISLIQ_ROC",
        'PRICE_DELTA_PCT_UNNEED_RIFUSD': Decimal('10.0'),
        'ORACLE_PRICE_PUBLISH_BLOCKS_UNNEED_RIFUSD': 3456,

    },
    '31':{ # RSK Testnet
        
        # No gas limit address for RSK Testnet as default
        'GAS_LIMIT_ADDR': None,
        'MULTICALL_ADDR': '0xca11bde05977b3631167028862be2a173976ca11',
        
        #
        # You can uncomment the following lines and complete to assign
        # default parameters to the coinpairpar XXXZZZ.
        #
        # 'ORACLE_OFFLINE_CFG_XXXZZZ': True,
        # 'MOC_V3_QUEUE_IS_EMPTY_XXXZZZ': '0x0000000000000000000000000000000000000000',
        # 'MOC_V3_SHOULD_CALCULATE_EMA_XXXZZZ': '0x0000000000000000000000000000000000000000',
        # 'MOC_V3_TC_INTEREST_PAYMENT_XXXZZZ': '0x0000000000000000000000000000000000000000',
        # 'MOC_V3_SETTLEMENT_TIME_XXXZZZ': '0x0000000000000000000000000000000000000000',
        # 'MOC_MULTICOLLATERAL_GUARD_XXXZZZ': '0x0000000000000000000000000000000000000000',
        # 'MOC_V3_BUCKET_XXXZZZ': '0x0000000000000000000000000000000000000000',
        # 'PRICE_DELTA_PCT_UNNEED_XXXZZZ': Decimal(1.0),
        # 'ORACLE_PRICE_PUBLISH_BLOCKS_UNNEED_XXXZZZ': 100, #int
        # 'PRICE_DELTA_PCT_NEED_XXXZZZ': Decimal(0.1),
        # 'ORACLE_PRICE_PUBLISH_BLOCKS_NEED_XXXZZZ': 10, #int
        #

        # Allow ORACLE_OFFLINE_CFG to be driven by endpoint URL
        # 'ORACLE_OFFLINE_CFG_RIFUSD': OFFLINE_CFG_URL + "ISLIQ_ROC(test)",
        'PRICE_DELTA_PCT_UNNEED_RIFUSD': Decimal('10.0'),
        'ORACLE_PRICE_PUBLISH_BLOCKS_UNNEED_RIFUSD': 3456,

    }
}

def config_per_chain_id(envvar, cast=str, default = None):
    return config(envvar, cast=cast,
        default=PER_CHAIN_ID_DEFAULTS.get(str(CHAIN_ID), {}).get(envvar, default))

GAS_LIMIT_ADDR = config_per_chain_id('GAS_LIMIT_ADDR')
MULTICALL_ADDR = config_per_chain_id('MULTICALL_ADDR')

DISABLE_FALLBACKS = config('DISABLE_FALLBACKS', cast=bool, default=False)
