import asyncio
import logging
from typing import Optional

from eth_typing import BlockIdentifier

from common.helpers import MyCfgdLogger
from common.services.blockchain import run_in_executor
from common.services.contract_factory_service import ContractFactoryService
from common.services.oracle_dao import OracleBlockchainInfo
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfoLoop
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.oracle_settings import GET_VAR_COINPAIR
from w3multicall.multicall import W3Multicall
from w3multicall.multicall import _decode_output, _unpack_aggregate_outputs, _encode_data

logger = logging.getLogger(__name__)


class MulticallWBlock(W3Multicall):
    def callWBlock(self, block_identifier: Optional[BlockIdentifier] = None) -> [list, int]:
        args = self._get_args()
        data = _encode_data(W3Multicall.MULTICALL_SELECTOR, W3Multicall.MULTICALL_INPUT_TYPES, args)
        eth_call_params = {
            'to': self.address,
            'data': data
        }
        rpc_response = self.web3.eth.call(eth_call_params, block_identifier=block_identifier)
        aggregated = _decode_output(rpc_response, W3Multicall.MULTICALL_OUTPUT_TYPES)
        try:
            unpacked = _unpack_aggregate_outputs(aggregated[1])
        except TypeError:
            if rpc_response == b'':
                msg = f'Response from Multicall/MOC contract is not valid: {rpc_response}.'
                logger.error(msg)
                raise Exception(msg)
            raise
        outputs = []
        for call, (success, output) in zip(self.calls, unpacked):
            call_output = _decode_output(output, call.output_types, None, True)
            outputs.append(call_output)
        return outputs, aggregated[0]


def run_and_wait_async(func, *args, **kwargs):
    """
    We only use threads here in order to be able to spawn and wait an async function from a sync one.
    This is used to execute the initialize() from oracle-configuration. In the future is recommended to make that
    instance a singleton..
    """
    import threading

    class RunThread(threading.Thread):
        def __init__(self, func, args, kwargs):
            self.func = func
            self.args = args
            self.kwargs = kwargs
            self.result = None
            super().__init__()

        def run(self):
            self.result = asyncio.run(self.func(*self.args, **self.kwargs))

    # we do already have a loop and so..
    # try:
    #     loop = asyncio.get_running_loop()
    # except RuntimeError:
    #     loop = None
    # if loop and loop.is_running():
    thread = RunThread(func, args, kwargs)
    thread.start()
    thread.join()


_NULL_OPTS = ('', '0x0', 'false', 'disabled')


class ConditionalConfig:
    _VARS = ('MOC_BASE_BUCKET', 'MOC_EMA', 'MOC_CORE', )

    @classmethod
    def GetCP(cls, cp: str, name: str):
        return GET_VAR_COINPAIR(name, cp)
    @classmethod
    def GetRegular(cls, ocfg: OracleConfiguration, name: str):
        return getattr(ocfg, name.upper(), None)

    def validate(self, valid: bool, var: str, value: str):
        if value in _NULL_OPTS:
            logger.warning(f" * ConditionalPublishService: ({self.cp}) Config variable {var} have no valid value: '{value}'.")
            valid = False
        return valid and (value is not None)

    def __init__(self, cp: str, ocfg: OracleConfiguration):
        self.cp = cp.upper()
        self._MOC_BASE_BUCKET = self._MOC_EMA = self._MOC_CORE = self._MULTICALL_ADDR = None
        valid = True
        for var in ConditionalConfig._VARS:
            value = ConditionalConfig.GetCP(self.cp, var)
            valid = self.validate(valid, var, value)
            setattr(self, f'_{var}', value)  # set "protected" variable..

        value = ConditionalConfig.GetRegular(ocfg, 'MULTICALL_ADDR')
        valid = self.validate(valid, 'MULTICALL_ADDR', value)
        setattr(self, f'_MULTICALL_ADDR', value)  # set "protected" variable..
        self.valid = valid

    def check_valid(self):
        return self.valid

    @property
    def MOC_BASE_BUCKET(self):
        return self._MOC_BASE_BUCKET

    @property
    def MOC_EMA(self):
        return self._MOC_EMA

    @property
    def MOC_CORE(self):
        return self._MOC_CORE

    @property
    def MULTICALL_ADDR(self):
        return self._MULTICALL_ADDR


class ConditionalPublishServiceBase:
    @classmethod
    def SyncCreate(cls, blockchain, cp, loop: OracleBlockchainInfoLoop) -> "ConditionalPublishServiceBase":
        oc = OracleConfiguration(
            ContractFactoryService.get_contract_factory_service())
        run_and_wait_async(oc.initialize)
        cfg = ConditionalConfig(cp, oc)
        if not cfg.check_valid():
            return DisabledConditionalPublishService(cfg)
        return ConditionalPublishService(blockchain, cfg, oc, loop)

    def __init__(self, cfg: ConditionalConfig):
        self.cfg = cfg
        self.logger = MyCfgdLogger(': ', str(self.cfg.cp))

    def set_conf_and_loop(self, conf: OracleConfiguration, loop: OracleBlockchainInfoLoop):
        pass

    def from_blockchain(self, blockchain_info:OracleBlockchainInfo):
        pass

    async def update__is_paused(self):
        await self.update()
        return self.is_paused()

    @property
    def is_running(self):
        raise NotImplementedError

    def getConditionActive(self, value, currentBlockNr):
        raise NotImplementedError

    async def update(self):
        raise NotImplementedError

    def is_paused(self):
        raise NotImplementedError

    def max_pub_block(self, blockchain_last_pub_block: int):
        raise NotImplementedError


class DisabledConditionalPublishService(ConditionalPublishServiceBase):
    def __init__(self, cfg: ConditionalConfig):
        super().__init__(cfg)
        self.logger.warning(f" * ConditionalPublishService disabled for {cfg.cp}.")
        self.last_value = None

    def __str__(self):
        return '--'

    @property
    def is_running(self):
        return True

    def getConditionActive(self, *args, **kw):
        return True

    async def update(self):
        pass

    def is_paused(self):
        return False

    def max_pub_block(self, blockchain_last_pub_block: int):
        return blockchain_last_pub_block


class ConditionalPublishService(ConditionalPublishServiceBase):
    qACLockedInPending = 'qACLockedInPending()(uint256)'
    shouldCalculateEma = 'shouldCalculateEma()(bool)'
    getBts = 'getBts()(uint256)'
    nextTCInterestPayment = 'nextTCInterestPayment()(uint256)'
    _conf: OracleConfiguration
    _last_value = None
    _last_block = None
    _last_pub = None
    _expiration_blocks = None

    def __init__(self, blockchain, cfg: ConditionalConfig, conf: OracleConfiguration, loop: OracleBlockchainInfoLoop):
        super().__init__(cfg)
        self.blockchain = blockchain
        self.logger.info(f" * ConditionalPublishService setup for {self.cfg.cp}.")
        self.set_conf_and_loop(conf, loop)  # ready before fetch
        self._sync_fetch()  # prevent running without values!

    def set_conf_and_loop(self, conf: OracleConfiguration, loop: OracleBlockchainInfoLoop):
        self._conf = conf
        self.from_blockchain(loop.get())

    @property
    def _trigger_valid_publication_blocks(self):
        return self._conf.oracle_turn_conf.trigger_valid_publication_blocks

    def from_blockchain(self, blockchain_info:OracleBlockchainInfo):
        if blockchain_info is not None:
            self._expiration_blocks = blockchain_info.valid_price_period_in_blocks

    def _call_condition1_qACLockedInPending(self):
        return W3Multicall.Call(self._fix(self.cfg.MOC_BASE_BUCKET), self.qACLockedInPending)

    def _call_condition2_shouldCalculateEMA(self):
        return W3Multicall.Call(self._fix(self.cfg.MOC_EMA), self.shouldCalculateEma)

    def _call_condition3_getBts(self):
        return W3Multicall.Call(self._fix(self.cfg.MOC_CORE), self.getBts)

    def _call_condition4_nextTCInterestPayment(self):
        # function shouldCalculateEma() public view returns (bool)
        return W3Multicall.Call(self._fix(self.cfg.MOC_BASE_BUCKET), self.nextTCInterestPayment)

    @property
    def _w3(self):
        return self.blockchain.W3
    
    def _fix(self, a):
        return self._w3.toChecksumAddress(a)

    def _sync_fetch_multiple(self, *conditions):
        w3_multicall = MulticallWBlock(self._w3)
        for condition in conditions:
            w3_multicall.add(condition)
        w3_multicall.address = self._fix(self.cfg.MULTICALL_ADDR)
        return w3_multicall.callWBlock()

    def _sync_fetch(self):
        results = self._sync_fetch_multiple(
            self._call_condition1_qACLockedInPending(),
            self._call_condition2_shouldCalculateEMA(),
            self._call_condition3_getBts(),
            self._call_condition4_nextTCInterestPayment(),
        )
        self._last_value, self._last_block = results[0], results[1]
        if self.is_paused():
            self._last_pub = self._last_block

    @property
    def _tuple_value(self):
        return (self._last_value, self._last_block) if self.is_running else None

    @property
    def adjusted_last_pub(self):
        trigger_blocks = self._trigger_valid_publication_blocks
        if None in (self._expiration_blocks, trigger_blocks):
            if self._expiration_blocks is None:
                self.logger.warning("Expiration blocks : None")
            if trigger_blocks is None:
                self.logger.warning("Trigger blocks : None")
            return self._last_pub
        return self._last_pub - self._expiration_blocks + trigger_blocks

    def __str__(self):
        values = ','.join(str(x) for x in self._last_value).replace('True', 'T').replace('False', 'F')
        return '[%s/%s|%s]' % (values, self.adjusted_last_pub, 'P.' if self.is_paused() else 'ok')

    @property
    def is_running(self):
        return self._last_block is not None

    def getConditionActive(self, value, currentBlockNr):
        qACLockedInPending, calcEMA, Bts, nextTC = value
        return (qACLockedInPending > 0) or calcEMA or (Bts == 0) or (nextTC < currentBlockNr)

    async def update(self):
        await run_in_executor(self._sync_fetch)

    async def update__is_paused(self):
        await self.update()
        return self.is_paused()

    def is_paused(self):
        if self.is_running:
            return not self.getConditionActive(self._last_value, self._last_block)
        return False

    def max_pub_block(self, blockchain_last_pub_block: int):
        if self.is_running:
            if not (self._last_pub is None):
                return max(blockchain_last_pub_block, self.adjusted_last_pub)
        return blockchain_last_pub_block
