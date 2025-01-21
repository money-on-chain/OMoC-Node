import hashlib
import json
from decimal import Decimal

from starlette.datastructures import Secret

from common import crypto
from common.services.blockchain import BlockchainAccount
from common.settings import config

# Port in which the oracle listen for sign request
ORACLE_PORT = config('ORACLE_PORT', cast=int, default=5556)

# Run the oracle server
ORACLE_RUN = config('ORACLE_RUN', cast=bool, default=True)

# Flag that indicates if the monitor (a module that store information in
# logfiles) must be run
ORACLE_MONITOR_RUN = config('ORACLE_MONITOR_RUN', cast=bool, default=False)

# Flag that indicates if we must filter requests to /sign by ip.
ORACLE_RUN_IP_FILTER = config('ORACLE_RUN_IP_FILTER', cast=bool, default=True)

# Run the oracle round scheduler?
SCHEDULER_RUN_ORACLE_SCHEDULER = config('SCHEDULER_RUN_ORACLE_SCHEDULER',
                                        cast=bool, default=True)

# Run the supporters round scheduler?
SCHEDULER_RUN_SUPPORTERS_SCHEDULER = config('SCHEDULER_RUN_SUPPORTERS_SCHEDULER',
                                            cast=bool, default=True)

# Monitor : Log exchange prices file name
ORACLE_MONITOR_LOG_EXCHANGE_PRICE = config('ORACLE_MONITOR_LOG_EXCHANGE_PRICE',
                                           cast=str, default="exchanges.log")

# Monitor : Log published prices file name
ORACLE_MONITOR_LOG_PUBLISHED_PRICE = config('ORACLE_MONITOR_LOG_PUBLISHED_PRICE',
                                            cast=str, default="published.log")

# If configured (json array of strings) only publish for those coinpairs in the
# list
ORACLE_COIN_PAIR_FILTER = json.loads(config('ORACLE_COIN_PAIR_FILTER', cast=str,
                                            default="[]"))

GET_MOC_ADDR_COINPAIR = lambda coinpair: config(f'MOC_ADDR_{coinpair.upper()}',
                                                  cast=str, default="")


def load_exchange_info():
    with open("exchanges.json", "r") as f:
        data = json.loads(f.read())
    for exchange_info_list in data.values():
        for exchange_info in exchange_info_list:
            exchange_info['ponderation'] = Decimal(exchange_info['ponderation'])
    return data


def d2l(a_dict):
    """
    Convert a dict to a sorted list of pairs, changing the decimal values to str
    """
    d_to_str = lambda x: x if not isinstance(x, Decimal) else str(x)
    items = [(k, d_to_str(v)) for k, v in a_dict.items()]
    items.sort()
    return items


def normalize_exchange_info(data):
    """Normalize exchange definition. For that we use lists which can be sorted
    instead of dicts"""
    keys = list(data.keys())
    whole = []
    for key in keys:
        result = data[key]
        whole.append((key, list(map(d2l, result))))
    whole.sort()
    return whole


def hash_exchange_info(data):
    ndata = normalize_exchange_info(data)
    m = hashlib.sha256()
    m.update(json.dumps(ndata, ensure_ascii=False).encode('utf-8'))
    return m.hexdigest()


# Exchange price engines
ORACLE_PRICE_ENGINES = load_exchange_info()
ORACLE_PRICE_ENGINES_SIG = hash_exchange_info(ORACLE_PRICE_ENGINES)


def get_oracle_account() -> BlockchainAccount:
    secret = config('ORACLE_PRIVATE_KEY', cast=Secret)
    default_addr = crypto.addr_from_key(str(secret))
    addr = config('ORACLE_ADDR', cast=str, default=default_addr)
    if default_addr != addr:
        raise ValueError(f"ORACLE_ADDR doesn't match ORACLE_PRIVATE_KEY, {default_addr}!={addr}")
    return BlockchainAccount(addr, secret)


def get_oracle_scheduler_account() -> BlockchainAccount:
    return get_oracle_account()


def get_supporters_scheduler_account() -> BlockchainAccount:
    return get_oracle_account()
