import os
import pathlib

from starlette.config import Config
from starlette.datastructures import URL

from common.helpers import parseTimeDelta

config = Config(".env")

# Block chain server url
NODE_URL = config('NODE_URL', cast=URL, default=None)
# Block chain chain id
CHAIN_ID = config('CHAIN_ID', cast=str, default=None)

# If this parameter is set we use the moneyonchain library abis and addresses.
# In not then we use the build diretory
MOC_NETWORK = config('MOC_NETWORK', cast=str, default=None)
# If we use the build directory (MOC_NETWORK unconfigured) we must set this parameter to the block chain network id
DEVELOP_NETWORK_ID = config('DEVELOP_NETWORK_ID', cast=int, default=None)
CONTRACT_ROOT_FOLDER = config('CONTRACT_ROOT_FOLDER', cast=pathlib.Path,
                              default=pathlib.Path(os.path.dirname(os.path.realpath(__file__))).parent)
# The server expect to find in this folder the *.json files with the abi an addresses of contracts
CONTRACT_FOLDER = config('CONTRACT_FOLDER', cast=pathlib.Path,
                         default=os.path.join(CONTRACT_ROOT_FOLDER, "build", "contracts"))
REGISTRY_ADDR = config('REGISTRY_ADDR', cast=str)

# Timeout used when connection to the blockchain node
WEB3_TIMEOUT = parseTimeDelta(config('WEB3_TIMEOUT ', cast=str, default="30 secs"))

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
VERSION = "1.3.6.5"

# This four are for the gas_price fix. Sometime the gas_price reaches 20Gwei
# Used the first time if the gas price exceeds the admitted
DEFAULT_GAS_PRICE = config('DEFAULT_GAS_PRICE', cast=int, default=65000000)
# The percentage that is consider to be admitted 
GAS_PERCENTAGE_ADMITTED = config('GAS_PERCENTAGE_ADMITTED', cast=int, default=10)
