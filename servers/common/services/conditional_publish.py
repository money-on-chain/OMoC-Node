from eth_typing import BlockIdentifier

import asyncio
import logging
import traceback
from common.helpers import MyCfgdLogger
from common.services.blockchain import run_in_executor
from common.services.contract_factory_service import ContractFactoryService
from common.services.oracle_dao import OracleBlockchainInfo
from common.settings import config_per_chain_id
from decimal import Decimal
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfoLoop
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.oracle_settings import GET_VAR_COINPAIR
from typing import Optional
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


class NoConditionalPublication(Exception):
    pass


class InvalidCfg(NoConditionalPublication):
    pass


_NULL_OPTS = ('', '0x0', 'false', 'disabled')

DefaultDecimal = Decimal('-2')


class ConditionalConfig:

    _VARS = (
        'MOC_V3_QUEUE_IS_EMPTY',
        'MOC_V3_SHOULD_CALCULATE_EMA',
        'MOC_V3_TC_INTEREST_PAYMENT',
        'MOC_V3_SETTLEMENT_TIME',
        'MOC_QUEUE',
        'MOC_BASE_BUCKET',
        'MOC_V3_BUCKET',
        'MOC_EMA',
        'MOC_CORE',
        'MOC_MULTICOLLATERAL_GUARD',
    )

    @classmethod
    def GetCP(cls, cp: str, name: str):
        return GET_VAR_COINPAIR(name, cp)
    
    @classmethod
    def GetRegular(cls, ocfg: OracleConfiguration, name: str):
        return getattr(ocfg, name.upper(), None)

    def validate(self, valid: bool, var: str, value: str, _null_opts=_NULL_OPTS):
        if value in _null_opts:
            logger.warning(f" * ConditionalPublishService: ({self.cp}) Conf.var: {var} have no valid value: '{value}'.")
            valid = False
        return valid and (value is not None)

    def __init__(self, cp: str, ocfg: OracleConfiguration):
        self.cp = cp.upper()
        self.logger = MyCfgdLogger(': ', str(self.cp))
        
        for var in ConditionalConfig._VARS:
            setattr(self, f'_{var}', None)       
        
        self._MULTICALL_ADDR = None
        
        valid = True

        self._ORACLE_OFFLINE_CFG = config_per_chain_id('ORACLE_OFFLINE_CFG_'+self.cp, cast=bool, default=False)
        valid = self.validate(valid, 'ORACLE_OFFLINE_CFG_', self._ORACLE_OFFLINE_CFG, ('', '0x0', 'disabled'))

        for var in ConditionalConfig._VARS:
            value = ConditionalConfig.GetCP(self.cp, var)
            #valid = self.validate(valid, var, value)
            if not value or value in _NULL_OPTS:
                value = []
            else:
                for sep in "'" + '"' + "[](){}":
                    value = value.replace(sep, '')
                for sep in " ;&":
                    value = value.replace(sep, ',')
                value = [x for x in value.split(',') if x]
            if not value and self._ORACLE_OFFLINE_CFG:
                self.logger.warning(f"{var}_{self.cp} is not set or is empty.")
            setattr(self, f'_{var}', value)  # set "protected" variable..

        self._MULTICALL_ADDR = ConditionalConfig.GetRegular(
            ocfg, 'MULTICALL_ADDR')
        valid = self.validate(valid, 'MULTICALL_ADDR', self._MULTICALL_ADDR)

        self._PRICE_DELTA_PCT_NEED = config_per_chain_id(
            'PRICE_DELTA_PCT_NEED_' + self.cp,
            cast=Decimal, default=DefaultDecimal)
        valid = self.validate(valid, 'PRICE_DELTA_PCT_NEED_',
                              self._PRICE_DELTA_PCT_NEED)

        self._ORACLE_PRICE_PUBLISH_BLOCKS_NEED = config_per_chain_id(
            'ORACLE_PRICE_PUBLISH_BLOCKS_NEED_' + self.cp,
            cast=int, default=DefaultDecimal)
        valid = self.validate(valid, 'ORACLE_PRICE_PUBLISH_BLOCKS_NEED_',
                              self._ORACLE_PRICE_PUBLISH_BLOCKS_NEED)

        self._PRICE_DELTA_PCT_UNNEED = config_per_chain_id(
            'PRICE_DELTA_PCT_UNNEED_' + self.cp,
            cast=Decimal, default=-1)
        valid = self.validate(valid, 'PRICE_DELTA_PCT_UNNEED_',
                              self._PRICE_DELTA_PCT_UNNEED)

        self._ORACLE_PRICE_PUBLISH_BLOCKS_UNNEED = config_per_chain_id(
            'ORACLE_PRICE_PUBLISH_BLOCKS_UNNEED_' + self.cp,
            cast=int, default='-1')
        valid = self.validate(valid, 'ORACLE_PRICE_PUBLISH_BLOCKS_UNNEED_',
                              self._ORACLE_PRICE_PUBLISH_BLOCKS_UNNEED)
        
        self.valid = valid

    def check_valid(self):
        return self.valid

    def as_dict(self):
        return {
            'COINPAIR': self.cp,
            'ORACLE_OFFLINE_CFG': self.ORACLE_OFFLINE_CFG,
            'PRICE_DELTA_PCT_NEED': str(self.PRICE_DELTA_PCT_NEED),
            'ORACLE_PRICE_PUBLISH_BLOCKS_NEED':
                self.ORACLE_PRICE_PUBLISH_BLOCKS_NEED,
            'PRICE_DELTA_PCT_UNNEED': str(self.PRICE_DELTA_PCT_UNNEED),
            'ORACLE_PRICE_PUBLISH_BLOCKS_UNNEED':
                self.ORACLE_PRICE_PUBLISH_BLOCKS_UNNEED,
            'MOC_V3_QUEUE_IS_EMPTY': self.MOC_V3_QUEUE_IS_EMPTY,
            'MOC_V3_SHOULD_CALCULATE_EMA': self.MOC_V3_SHOULD_CALCULATE_EMA,
            'MOC_V3_TC_INTEREST_PAYMENT': self.MOC_V3_TC_INTEREST_PAYMENT,
            'MOC_V3_SETTLEMENT_TIME': self.MOC_V3_SETTLEMENT_TIME,            
            'MOC_QUEUE': self.MOC_QUEUE,
            'MOC_BASE_BUCKET': self.MOC_BASE_BUCKET,
            'MOC_V3_BUCKET': self.MOC_V3_BUCKET,
            'MOC_EMA': self.MOC_EMA,
            'MOC_CORE': self.MOC_CORE,
            'MOC_MULTICOLLATERAL_GUARD': self.MOC_MULTICOLLATERAL_GUARD,
            'MULTICALL_ADDR': self.MULTICALL_ADDR,
        }

    @property
    def ORACLE_OFFLINE_CFG(self):
        return self._ORACLE_OFFLINE_CFG

    @property
    def PRICE_DELTA_PCT_NEED(self):
        return self._PRICE_DELTA_PCT_NEED

    @property
    def ORACLE_PRICE_PUBLISH_BLOCKS_NEED(self):
        return self._ORACLE_PRICE_PUBLISH_BLOCKS_NEED

    @property
    def PRICE_DELTA_PCT_UNNEED(self):
        return self._PRICE_DELTA_PCT_UNNEED

    @property
    def ORACLE_PRICE_PUBLISH_BLOCKS_UNNEED(self):
        return self._ORACLE_PRICE_PUBLISH_BLOCKS_UNNEED

    @property
    def MOC_V3_QUEUE_IS_EMPTY(self):
        return self._MOC_V3_QUEUE_IS_EMPTY

    @property
    def MOC_V3_SHOULD_CALCULATE_EMA(self):
        return self._MOC_V3_SHOULD_CALCULATE_EMA

    @property
    def MOC_V3_TC_INTEREST_PAYMENT(self):
        return self._MOC_V3_TC_INTEREST_PAYMENT

    @property
    def MOC_V3_SETTLEMENT_TIME(self):
        return self._MOC_V3_SETTLEMENT_TIME

    @property
    def MOC_QUEUE(self):
        return self._MOC_QUEUE

    @property
    def MOC_BASE_BUCKET(self):
        return self._MOC_BASE_BUCKET

    @property
    def MOC_V3_BUCKET(self):
        return self._MOC_V3_BUCKET

    @property
    def MOC_EMA(self):
        return self._MOC_EMA

    @property
    def MOC_CORE(self):
        return self._MOC_CORE

    @property
    def MOC_MULTICOLLATERAL_GUARD(self):
        return self._MOC_MULTICOLLATERAL_GUARD

    @property
    def MULTICALL_ADDR(self):
        return self._MULTICALL_ADDR


class ConditionalPublishServiceBase:
    @classmethod
    def SyncCreate(cls, blockchain, cp, loop: OracleBlockchainInfoLoop
                   ) -> "ConditionalPublishServiceBase":
        oc = OracleConfiguration(
            ContractFactoryService.get_contract_factory_service())
        run_and_wait_async(oc.initialize)
        ccfg = ConditionalConfig(cp, oc)
        try:
            if not ccfg.ORACLE_OFFLINE_CFG:
                raise NoConditionalPublication(f" * ConditionalPublishService disabled for {ccfg.cp} because of ORACLE_OFFLINE_CFG.")
            if not ccfg.check_valid():
                raise InvalidCfg(f" * ConditionalPublishService disabled for {ccfg.cp} not valid cfg!.")
            return ConditionalPublishService(blockchain, ccfg, loop)
        except InvalidCfg as err:
            logger.error(err)
            return DisabledConditionalPublishService(ccfg)
        except NoConditionalPublication as err:
            logger.warning(err)           
            return DisabledConditionalPublishService(ccfg)

    def __init__(self, ccfg: ConditionalConfig):
        self.cfg = ccfg
        self.logger = MyCfgdLogger(': ', str(self.cfg.cp))

    def from_blockchain(self, blockchain_info:OracleBlockchainInfo):
        pass

    async def update__offline_cfg(self):
        await self.update()
        return self.offline_cfg()

    @property
    def is_running(self):
        raise NotImplementedError

    def getConditionActive(self, value, currentBlockNr):
        raise NotImplementedError

    async def update(self):
        raise NotImplementedError

    def offline_cfg(self):
        raise NotImplementedError

    def max_pub_block(self, blockchain_last_pub_block: int):
        raise NotImplementedError

    def get_price_delta(self, default_delta):
        raise NotImplementedError

    def get_valid_price_period(self, default_value):
        raise NotImplementedError

    def cfg_as_dict(self):
        return {self.__class__.__name__: self.cfg.as_dict()}


class DisabledConditionalPublishService(ConditionalPublishServiceBase):
    def __init__(self, ccfg: ConditionalConfig):
        super().__init__(ccfg)
        self.logger.warning(f" * ConditionalPublishService disabled for {ccfg.cp}.")
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

    def offline_cfg(self):
        return False

    def max_pub_block(self, blockchain_last_pub_block: int):
        return blockchain_last_pub_block

    def get_price_delta(self, default_delta):
        return default_delta

    def get_valid_price_period(self, default_value):
        return default_value


class ConditionalPublishService(ConditionalPublishServiceBase):
    
    queueIsEmpty = 'isEmpty()(bool)' # both
    shouldCalculateEma = 'shouldCalculateEma()(bool)' # both
    getBts = 'getBts()(uint256)' # V1
    nextTCInterestPayment = 'nextTCInterestPayment()(uint256)' # both
    nextSettlementTime = "nextSettlementTime()(uint256)" # V3
    isMicroLiquidationAvailable = 'isMicroLiquidationAvailable(address)(bool)' # V3
    isLiquidationAvailable = 'isLiquidationAvailable(address)(bool)' # V3

    _last_value = None
    _last_block = None
    _expiration_blocks = None

    def __init__(self, blockchain, ccfg: ConditionalConfig, loop: OracleBlockchainInfoLoop):
        super().__init__(ccfg)
        if (ccfg.PRICE_DELTA_PCT_NEED<0 or ccfg.PRICE_DELTA_PCT_NEED>100) and (ccfg.PRICE_DELTA_PCT_NEED!=DefaultDecimal):
            raise InvalidCfg('Invalid price delta pct need setup')
        if (ccfg.PRICE_DELTA_PCT_UNNEED<0 or ccfg.PRICE_DELTA_PCT_UNNEED>100) and (ccfg.PRICE_DELTA_PCT_UNNEED!=DefaultDecimal):
            raise InvalidCfg('Invalid price delta pct unneed setup')
        self.blockchain = blockchain
        self.logger.info(f" * ConditionalPublishService setup for {self.cfg.cp}.")
        self.from_blockchain(loop.get())
        self._sync_fetch()  # prevent running without values!

    def get_price_delta(self, default_delta):
        x = self.cfg.PRICE_DELTA_PCT_UNNEED if self.offline_cfg() else self.cfg.PRICE_DELTA_PCT_NEED
        if x == DefaultDecimal:
            return default_delta
        return x

    def get_valid_price_period(self, default_value):
        x = (self.cfg.ORACLE_PRICE_PUBLISH_BLOCKS_UNNEED if self.offline_cfg() else
                self.cfg.ORACLE_PRICE_PUBLISH_BLOCKS_NEED)
        if x == DefaultDecimal:
            return default_value
        return x

    def from_blockchain(self, blockchain_info:OracleBlockchainInfo):
        if blockchain_info is not None:
            self._expiration_blocks = blockchain_info.valid_price_period_in_blocks

    def _call_condition_base(self, addresses, signature):
        out = []
        for addr in addresses:
            try:
                addr = self._fix(addr)
            except ValueError as e:
                self.logger.error(
                    f"{repr(addr)} is an invalid addr, it is discarded for " +
                    f"{signature.split('()')[0]}() condition"
                )
                addr = None
            obj = None if addr is None else W3Multicall.Call(addr, signature)
            if obj is not None:
                out.append(obj)
        return out

    def _call_condition_guard(self, guards, buckets, signature):
        out = []
        fixed_guards = []
        for g in guards:
            try:
                fixed_guards.append(self._fix(g))
            except ValueError as e:
                self.logger.error(
                    f"{repr(g)} is an invalid addr, it is discarded for " +
                    f"{signature.split('(')[0]} condition"
                )
        fixed_buckets = []
        for b in buckets:
            try:
                fixed_buckets.append(self._fix(b))
            except ValueError as e:
                self.logger.error(
                    f"{repr(b)} is an invalid bucket addr, it is discarded for " +
                    f"{signature.split('(')[0]} condition"
                )
        for g in fixed_guards:
            for b in fixed_buckets:
                out.append(W3Multicall.Call(g, signature, [b]))
        return out

    def _call_v3_condition1_queueIsEmpty(self):
        return self._call_condition_base(self.cfg.MOC_V3_QUEUE_IS_EMPTY,
                                         self.queueIsEmpty)

    def _call_v3_condition2_shouldCalculateEMA(self):
        return self._call_condition_base(self.cfg.MOC_V3_SHOULD_CALCULATE_EMA,
                                         self.shouldCalculateEma)

    def _call_v3_condition3_nextTCInterestPayment(self):
        return self._call_condition_base(self.cfg.MOC_V3_TC_INTEREST_PAYMENT,
                                         self.nextTCInterestPayment)

    def _call_v3_condition4_nextSettlementTime(self):
        return self._call_condition_base(self.cfg.MOC_V3_SETTLEMENT_TIME,
                                         self.nextSettlementTime)

    def _call_v3_condition5_isMicroLiquidationAvailable(self):
        return self._call_condition_guard(self.cfg.MOC_MULTICOLLATERAL_GUARD,
                                          self.cfg.MOC_V3_BUCKET,
                                          self.isMicroLiquidationAvailable)

    def _call_v3_condition6_isLiquidationAvailable(self):
        return self._call_condition_guard(self.cfg.MOC_MULTICOLLATERAL_GUARD,
                                          self.cfg.MOC_V3_BUCKET,
                                          self.isLiquidationAvailable)

    def _call_condition1_queueIsEmpty(self):
        return self._call_condition_base(self.cfg.MOC_QUEUE,
                                         self.queueIsEmpty)

    def _call_condition2_shouldCalculateEMA(self):
        return self._call_condition_base(self.cfg.MOC_EMA,
                                         self.shouldCalculateEma)

    def _call_condition3_getBts(self):
        return self._call_condition_base(self.cfg.MOC_CORE,
                                         self.getBts)

    def _call_condition4_nextTCInterestPayment(self):
        return self._call_condition_base(self.cfg.MOC_BASE_BUCKET,
                                         self.nextTCInterestPayment)

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
        calls = [
            self._call_v3_condition1_queueIsEmpty(),
            self._call_v3_condition2_shouldCalculateEMA(),
            self._call_v3_condition3_nextTCInterestPayment(),
            self._call_v3_condition4_nextSettlementTime(),
            self._call_v3_condition5_isMicroLiquidationAvailable(),
            self._call_v3_condition6_isLiquidationAvailable(),
            self._call_condition1_queueIsEmpty(),
            self._call_condition2_shouldCalculateEMA(),
            self._call_condition3_getBts(),
            self._call_condition4_nextTCInterestPayment(),
        ]
        args = []
        for call in calls:
            for c in call:
                args.append(c)
        results_base, self._last_block = self._sync_fetch_multiple(*args)
        results = []
        for call in calls:
            r = []
            for c in call:
                r.append(results_base.pop(0))
            results.append(r)
        self._last_value = results

    @property
    def _tuple_value(self):
        return (self._last_value, self._last_block) if self.is_running else None

    def __str__(self):
        values = ','.join(','.join([str(y) for y in x]
            ) for x in self._last_value).replace('True', 'T').replace(
                'False', 'F')
        return '[%s|%s]' % (values, 'P.' if self.offline_cfg() else 'ok')

    @property
    def is_running(self):
        return self._last_block is not None

    def getConditionActive(self, value, currentBlockNr):

        (v3_is_empty_lst, v3_calc_ema_lst, v3_next_tc_lst, v3_next_st_lst,
         v3_micro_liq_lst, v3_liq_lst,
         is_empty_lst, calc_ema_lst, bts_lst, next_tc_lst) = value

        for is_empty in v3_is_empty_lst:
            if not is_empty:
                return True
        
        for calc_ema in v3_calc_ema_lst:
            if calc_ema:
                return True

        for micro in v3_micro_liq_lst:
            if micro:
                return True

        for liq in v3_liq_lst:
            if liq:
                return True

        for is_empty in is_empty_lst:
            if not is_empty:
                return True
        
        for calc_ema in calc_ema_lst:
            if calc_ema:
                return True
            
        for bts in bts_lst:
            if bts == 0:
                return True
            
        for next_tc in next_tc_lst:
            if next_tc < currentBlockNr:
                return True

        if (not v3_next_tc_lst and not v3_next_st_lst and
                not v3_micro_liq_lst and not v3_liq_lst):
            return False

        block_timestamp = self._w3.eth.getBlock(currentBlockNr)["timestamp"]
        #logger.info(f"Block timestamp: {block_timestamp}")
        
        for next_payment_time in v3_next_tc_lst:
            if next_payment_time < block_timestamp:
                return True

        for next_settlement_time in v3_next_st_lst:
            if next_settlement_time < block_timestamp:
                return True

        return False

    async def update(self):
        try:
            await run_in_executor(self._sync_fetch)
        except Exception as err:
            self.error(f"ConditionalPublishService update failed: {err!r}")
            self.warning(traceback.format_exc())
            self._last_block = None
            self._last_value = None

    async def update__offline_cfg(self):
        await self.update()
        return self.offline_cfg()

    def offline_cfg(self):
        if self.is_running:
            return not self.getConditionActive(self._last_value, self._last_block)
        return False
