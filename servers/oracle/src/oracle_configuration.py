import logging
import typing
from common.helpers import parseTimeDelta, MyCfgdLogger
from common.services.blockchain import is_error
from common.services.contract_factory_service import ContractFactoryService
from common.settings import config
from decimal import Decimal
from enum import Enum

logger = logging.getLogger(__name__)

OracleTurnConfiguration = typing.NamedTuple("OracleTurnConfiguration",
                                            [("price_delta_pct", int),
                                             ("price_publish_blocks", int),
                                             ("entering_fallbacks_amounts", bytes),
                                             ("trigger_valid_publication_blocks", int)
                                             ])


class OracleConfiguration(MyCfgdLogger):
    class Order(Enum):
        blockchain_configuration_default = 1
        configuration_blockchain_default = 2
        configuration_default_blockchain = 3
        configuration_default = 4

    def __init__(self, cf: ContractFactoryService):
        super().__init__(': ', 'Ocfg')
        registry_addr = config('REGISTRY_ADDR', cast=str)
        if registry_addr is None:
            raise ValueError("Missing REGISTRY_ADDR!!!")
        self.info("Configuration Registry address: %s" % registry_addr)
        self._eternal_storage_service = cf.get_eternal_storage(registry_addr)

        self.parameters = {
            "ORACLE_MANAGER_ADDR": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: config('ORACLE_MANAGER_ADDR', cast=str),
                "blockchain": lambda p: self._eternal_storage_service.get_address(p),
                "description": "Oracle manager address, used in OracleLoop to get coin"
                               "pairs and CoinPairPrice addresses"
            },
            "SUPPORTERS_ADDR": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: config('SUPPORTERS_ADDR', cast=str),
                "blockchain": lambda p: self._eternal_storage_service.get_address(p),
                "description": "Supporters address, called by scheduler to switch rounds"
            },
            "STAKING_MACHINE_ADDR": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: config('STAKING_MACHINE_ADDR', cast=str),
                "blockchain": lambda p: self._eternal_storage_service.get_address("moc.staking-machine"),
                "description": "Staking machine address, used to call oracle and staking operations",
            },
            "INFO_ADDR": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: config('INFO_ADDR', cast=str),
                "blockchain": lambda p: self._eternal_storage_service.get_address(p),
                "description": "Info address, contract to get all the information at once"
            },
            "ORACLE_PRICE_FETCH_RATE": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: parseTimeDelta(config('ORACLE_PRICE_FETCH_RATE', cast=str)),
                "blockchain": lambda p: self._eternal_storage_service.get_uint(p),
                "description": "Exchange price-fetch rate in seconds, all the exchanges are queried at the same time.",
                "default": 5
            },
            "ORACLE_BLOCKCHAIN_INFO_INTERVAL": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: parseTimeDelta(config('ORACLE_BLOCKCHAIN_INFO_INTERVAL', cast=str)),
                "blockchain": lambda p: self._eternal_storage_service.get_uint(p),
                "description": "This loop collect a lot of information needed for validation (like last pub block)"
                               " from the block chain",
                "default": 3,
            },
            "ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: parseTimeDelta(config('ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL', cast=str)),
                "blockchain": lambda p: self._eternal_storage_service.get_uint(p),
                "description": "Per coin pair loop scanning interval, in which we try to publish",
                "default": 5,
            },
            "ORACLE_MAIN_LOOP_TASK_INTERVAL": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: parseTimeDelta(config('ORACLE_MAIN_LOOP_TASK_INTERVAL', cast=str)),
                "blockchain": lambda p: self._eternal_storage_service.get_uint(p),
                "description": "Main Oracle loop scanning interval, in which we get the coinpair list",
                "default": 120,
            },
            "ORACLE_PRICE_REJECT_DELTA_PCT": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: config('ORACLE_PRICE_REJECT_DELTA_PCT', cast=Decimal),
                "blockchain": lambda p: self._eternal_storage_service.get_decimal(p),
                "description": "If the price delta percentage is grater than this we reject by not signing",
                "default": Decimal("50"),
            },
            "ORACLE_CONFIGURATION_TASK_INTERVAL": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: parseTimeDelta(config('ORACLE_CONFIGURATION_TASK_INTERVAL', cast=str)),
                "blockchain": lambda p: self._eternal_storage_service.get_uint(p),
                "description": "Configuration Oracle loop scanning interval, in which we get configuration info",
                "default": 240,
            },
            "ORACLE_MAIN_EXECUTOR_TASK_INTERVAL": {
                "priority": self.Order.configuration_default,
                "configuration": lambda: parseTimeDelta(config('ORACLE_MAIN_EXECUTOR_TASK_INTERVAL', cast=str)),
                "blockchain": lambda p: self._eternal_storage_service.get_uint(p),
                "description": "Configuration Main executor loop scanning interval",
                "default": 20,
            },
            "ORACLE_GATHER_SIGNATURE_TIMEOUT": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: parseTimeDelta(config('ORACLE_GATHER_SIGNATURE_TIMEOUT', cast=str)),
                "blockchain": lambda p: self._eternal_storage_service.get_uint(p),
                "description": "Timeout used when requesting signatures from other oracles",
                "default": 60,
            },
            "SCHEDULER_POOL_DELAY": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: parseTimeDelta(config('SCHEDULER_POOL_DELAY', cast=str)),
                "blockchain": lambda p: self._eternal_storage_service.get_uint(p),
                "description": "Delay in which the scheduler checks for round change conditions",
                "default": 10,
            },
            "SCHEDULER_ROUND_DELAY": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: parseTimeDelta(config('SCHEDULER_ROUND_DELAY', cast=str)),
                "blockchain": lambda p: self._eternal_storage_service.get_uint(p),
                "description": "Delay in which the scheduler checks for round change after a round was closed",
                "default": 60 * 60 * 24,
            },
            "ORACLE_PRICE_DIGITS": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: config('ORACLE_PRICE_DIGITS', cast=int),
                "blockchain": lambda p: self._eternal_storage_service.get_uint(p),
                "description": "Timeout used when requesting signatures fom other oracles",
                "default": 18,
            },
            "ORACLE_QUEUE_LEN": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: config('ORACLE_QUEUE_LEN', cast=int),
                "blockchain": lambda p: self._eternal_storage_service.get_uint(p),
                "description": "Size of the queue used to save historical exchange prices",
                "default": 30,
            },
            "MESSAGE_VERSION": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: config('MESSAGE_VERSION', cast=int),
                "blockchain": lambda p: self._eternal_storage_service.get_uint(p),
                "description": "Version field of the message that is send to the blockchain",
                "default": 3,
            },
            "ORACLE_PRICE_DELTA_PCT": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: config('ORACLE_PRICE_DELTA_PCT', cast=Decimal),
                "blockchain": lambda p: self._eternal_storage_service.get_decimal(p),
                "description": "Wait for this price change to start publishing a price",
                "default": Decimal("0.05"),
            },
            "ORACLE_PRICE_PUBLISH_BLOCKS": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: config('ORACLE_PRICE_PUBLISH_BLOCKS', cast=int),
                "blockchain": lambda p: self._eternal_storage_service.get_uint(p),
                "description": "Selected oracle publishes after ORACLE_PRICE_PUBLISH_BLOCKS blocks of a price change.",
                "default": 1,
            },
            "ORACLE_ENTERING_FALLBACKS_AMOUNTS": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: config('ORACLE_ENTERING_FALLBACKS_AMOUNTS', cast=bytes),
                "blockchain": lambda p: self._eternal_storage_service.get_bytes(p),
                "description": "Each int in the ORACLE_ENTERING_FALLBACKS_AMOUNTS sequence is the number of fallbacks that will be allowed to publish next.",
                "default": b'\x02\x04\x06\x08\n',
            },
            "ORACLE_TRIGGER_VALID_PUBLICATION_BLOCKS": {
                "priority": self.Order.configuration_blockchain_default,
                "configuration": lambda: config('ORACLE_TRIGGER_VALID_PUBLICATION_BLOCKS', cast=int),
                "blockchain": lambda p: self._eternal_storage_service.get_uint(p),
                "description": "Period in which selected oracle or fallbacks will publish before the price expires.",
                "default": 30,
            },

            "ORACLE_PRICE_RECEIVE_MAX_AGE": {
                "priority": self.Order.configuration_default,
                "configuration": lambda: config('ORACLE_PRICE_RECEIVE_MAX_AGE',
                                                cast=float),
                "blockchain": lambda *args:None,
                "description": "If an exchange sends a price with age greater than this value it will be kept as not-available (NaN) in the price queue.",
                "default": 30
            },
            "ORACLE_PRICE_PUBLISH_MAX_DIFF": {
                "priority": self.Order.configuration_default,
                "configuration": lambda: config('ORACLE_PRICE_PUBLISH_MAX_DIFF',
                                                cast=float),
                "blockchain": lambda *args: None,
                "description": "The maximal time difference (in seconds) a price in queue is considered when generating a price for publication.",
                "default": 30
            },
            "ORACLE_PRICE_VALIDATE_MAX_DIFF": {
                "priority": self.Order.configuration_default,
                "configuration": lambda: config('ORACLE_PRICE_VALIDATE_MAX_DIFF',
                                                cast=float),
                "blockchain": lambda *args: None,
                "description": "The maximal time difference (in seconds) a price in queue is considered when generating a price for validation.",
                "default": 30
            },
             "ORACLE_BLOCKCHAIN_STATE_DELAY": {
                "priority": self.Order.configuration_default_blockchain,
                "configuration": lambda: parseTimeDelta(config('ORACLE_BLOCKCHAIN_STATE_DELAY', cast=str)),
                "blockchain": lambda p: self._eternal_storage_service.get_uint(p),
                "description": "Delay in which the gas price is gathered",
                "default": 60
            },
            "MULTICALL_ADDR": {
                "priority": self.Order.configuration_default,
                "configuration": lambda: config('MULTICALL_ADDR', cast=str),
                "blockchain": lambda p: self._eternal_storage_service.get_address(p),
                "description": "Address of the multicall-contract (used for conditional publication)",
            },
        }
        self.from_conf = set()
        self.from_default = set()
        self.values = dict()

    def __getattr__(self, name):
        if name in self.values:
            return self.values[name]

    def __dir__(self):
        return self.mapping.keys()

    async def initialize(self):
        for (p, param) in self.parameters.items():
            val = None
            if val is None and "configuration" in param:
                try:
                    read_val = param["configuration"]()
                    if read_val == "":
                        val = None
                        self.values[p] = val
                    else:
                        val = read_val
                    self.from_conf.add(p)
                    self.info("Setting parameter %r from environ -> %r" % (p, val))
                except KeyError:
                    pass
                except (TypeError, ValueError) as err:
                    self.error("Error getting key %s from environ %r" % (p, err))

            if val is None and "default" in param and param["default"] is not None:
                val = param["default"]
                read_val = param["default"]
                if read_val == "":
                    val = None
                    self.values[p] = val
                else:
                    val = read_val
                self.from_default.add(p)
                self.info("Setting parameter %r from default -> %r" % (p, val))

            if val is None:
                val = await self._get_from_blockchain(p, param)

            if val is None:
                self.warning("Missing value %s" % p)
                continue
            self.values[p] = val

    async def update(self):
        for (p, param) in self.parameters.items():
            val = await self._get_from_blockchain(p, param)
            if val is not None and self.values[p] != val:
                self.info("Setting param %r from blockchain registry -> %r" % (p, val))
                self.values[p] = val

    async def _get_from_blockchain(self, p, param):
        if param["priority"] == self.Order.configuration_default:
            return None
        if p in self.from_conf and param["priority"] == self.Order.configuration_blockchain_default:
            return None
        if p in self.from_default and param["priority"] == self.Order.configuration_default_blockchain:
            return None
        p_path = self.get_registry_path(p)
        val = await param["blockchain"](p_path)
        if is_error(val):
            msg = "Error getting param from blockchain %r -> %r" % (p, val)
            if p not in self.values or self.values[p] is None:
                self.error(msg)
            else:
                self.warning(msg)
            return None
        return val

    @staticmethod
    def get_registry_path(param_name):
        version = 1
        return "MOC_ORACLE\\%s\\%s" % (version, param_name)

    @property
    def oracle_turn_conf(self):
        return OracleTurnConfiguration(self.ORACLE_PRICE_DELTA_PCT,
                                       self.ORACLE_PRICE_PUBLISH_BLOCKS,
                                       self.ORACLE_ENTERING_FALLBACKS_AMOUNTS,
                                       self.ORACLE_TRIGGER_VALID_PUBLICATION_BLOCKS)
