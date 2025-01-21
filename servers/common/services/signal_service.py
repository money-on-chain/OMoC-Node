import asyncio
import logging
from typing import Optional

from eth_typing import BlockIdentifier

from common.services.blockchain import run_in_executor
from common.services.contract_factory_service import ContractFactoryService
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.oracle_settings import GET_MOC_ADDR_COINPAIR
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
        unpacked = _unpack_aggregate_outputs(aggregated[1])
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


class ConditionalPublishServiceBase:
    """This depends on:

    - ORACLE_CONFIGURATION.MULTICALL_ADDR = the multicall contract
    - environment: MOC_ADDR_{coinpair}' => to take variables from
    """
    @classmethod
    def SyncCreate(cls, blockchain, cp) -> "ConditionalPublishServiceBase":
        oc = OracleConfiguration(
            ContractFactoryService.get_contract_factory_service())
        run_and_wait_async(oc.initialize)
        cp_addr = GET_MOC_ADDR_COINPAIR(cp)
        if cp_addr in ('', '0x0', 'false', 'disabled'):
            return DisabledConditionalPublishService(cp, cp_addr)
        return ConditionalPublishService(blockchain, cp, oc.MULTICALL_ADDR, GET_MOC_ADDR_COINPAIR(cp))

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
    def __init__(self, cp, cfg_str):
        logger.warning(f" * ConditionalPublishService disabled for {cp}. (cfg string: {repr(cfg_str)})")
        self.cp = cp

    @property
    def is_running(self):
        return True

    def getConditionActive(self, value, currentBlockNr):
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

    """
    This depends on:

    - ORACLE_CONFIGURATION.MULTICALL_ADDR = the multicall contract
    - environment: MOC_ADDR_{coinpair}' => to take variables from
    """
    def __init__(self, blockchain, cp, multicall, addr):
        self.blockchain = blockchain
        logger.info(f" * ConditionalPublishService setup for {cp}: moc: {addr} multicall: {multicall}.")
        self.MOC_ADDR = self._w3.toChecksumAddress(addr)
        self.MULTICALL_ADDR = self._w3.toChecksumAddress(multicall)
        self.cp = cp
        self.last_value = self.last_block = None
        self.last_pub = None
        self._sync_fetch()  # prevent running without values!

    def _call_condition1_qACLockedInPending(self):
        #     { "inputs": [],
        #       "name": "qACLockedInPending",
        #       "outputs": [{"name": "",
        #           "internalType": "uint256",
        #           "type": "uint256"}],
        #       "stateMutability": "view",
        #       "type": "function"}
        return W3Multicall.Call(self.MOC_ADDR, self.qACLockedInPending)

    def _call_condition2_shouldCalculateEMA(self):
        # function shouldCalculateEma() public view returns (bool)
        return W3Multicall.Call(self.MOC_ADDR, self.shouldCalculateEma)

    def _call_condition3_getBts(self):
        # function shouldCalculateEma() public view returns (bool)
        return W3Multicall.Call(self.MOC_ADDR, self.getBts)

    def _call_condition4_nextTCInterestPayment(self):
        # function shouldCalculateEma() public view returns (bool)
        return W3Multicall.Call(self.MOC_ADDR, self.nextTCInterestPayment)

    @property
    def _w3(self):
        return self.blockchain.W3

    def _sync_fetch_multiple(self, *conditions):
        w3_multicall = MulticallWBlock(self._w3)
        for condition in conditions:
            w3_multicall.add(condition)
        w3_multicall.address = self.MULTICALL_ADDR
        return w3_multicall.callWBlock()

    def _sync_fetch(self):
        results = self._sync_fetch_multiple(
            self._call_condition1_qACLockedInPending(),
            self._call_condition2_shouldCalculateEMA(),
            self._call_condition3_getBts(),
            self._call_condition4_nextTCInterestPayment(),
        )
        self.last_value, self.last_block = results[0], results[1]
        if self.is_paused():
            self.last_pub = self.last_block

    @property
    def _tuple_value(self):
        return (self.last_value, self.last_block) if self.is_running else None

    @property
    def is_running(self):
        return self.last_block is not None

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
            return not self.getConditionActive(self.last_value, self.last_block)
        return False

    def max_pub_block(self, blockchain_last_pub_block: int):
        if self.is_paused():
            if not (self.last_pub is None):
                return max(blockchain_last_pub_block, self.last_pub)
        return blockchain_last_pub_block
