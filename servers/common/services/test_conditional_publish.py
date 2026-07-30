import logging
import os
import threading
from contextlib import contextmanager
from pprint import pprint

from common.services.blockchain import BlockChain
from common.services.conditional_publish import ConditionalPublishService, ConditionalConfig, run_and_wait_async
from common.services.contract_factory_service import ContractFactoryService
from oracle.src.oracle_configuration import OracleConfiguration

ONCE = True


class EndpointConfig:
    def __init__(self, force_publish):
        self.force_publish = force_publish
        self.endpoint_calls = 0
        self.MULTICALL_ADDR = "0x0000000000000000000000000000000000000000"
        self.MOC_V3_QUEUE_IS_EMPTY = []
        self.MOC_V3_SHOULD_CALCULATE_EMA = []
        self.MOC_V3_TC_INTEREST_PAYMENT = []
        self.MOC_V3_SETTLEMENT_TIME = []
        self.MOC_QUEUE = []
        self.MOC_EMA = []
        self.MOC_BASE_BUCKET = []

    @property
    def ORACLE_OFFLINE_CFG_FORCE_PUBLISH(self):
        self.endpoint_calls += 1
        return self.force_publish


def conditional_service(base_condition_active, force_publish):
    service = object.__new__(ConditionalPublishService)
    service.cfg = EndpointConfig(force_publish)
    service.logger = logging.getLogger(__name__)
    service._last_value = None
    service._last_block = None
    service._base_condition_active = True
    service._force_publish = False
    service._last_online_block = 0
    service._last_offline_block = 0
    service._last_offline_cfg = False
    service._sync_fetch_multiple = lambda *args: ([], 123)
    service.getConditionActive = lambda value, block: base_condition_active
    return service


@contextmanager
def with_env( *env_tuples ):
    prevs = {}
    for varname, value in env_tuples:
        prevs[varname] = os.environ.get(varname)
        os.environ[varname] = value
    try:
        yield
    finally:
        for varname, value in prevs.items():
            if value is None:
                del os.environ[varname]
            else:
                os.environ[varname] = value

def _get_env():
    return with_env(('MULTICALL_ADDR', '0x72440269630E393d38975Db7fA7Cb4D14e7eC061'),
                  ('MOC_EMA_BTCUSD', '0xD8d315932b5c5b9B21B14A39f5F12e4b9Bd65571'),
                  ('MOC_BASE_BUCKET_BTCUSD', '0xD8d315932b5c5b9B21B14A39f5F12e4b9Bd65571'),
                  ('MOC_V3_BUCKET_BTCUSD', '0xD8d315932b5c5b9B21B14A39f5F12e4b9Bd65571'),
                  ('MOC_MULTICOLLATERAL_GUARD_BTCUSD', '0xD8d315932b5c5b9B21B14A39f5F12e4b9Bd65571'))


def getOCFG(capsys):
    with _get_env():
        ocfg = OracleConfiguration(ContractFactoryService.get_contract_factory_service())
        run_and_wait_async(ocfg.initialize)
        return ocfg

def getCFG(capsys):
    oc = getOCFG(capsys)
    with _get_env():
        return ConditionalConfig('btcusd', oc)

def getSS(capsys):
    global ONCE
    node_url = os.environ.get('NODE_URL', 'http://127.0.0.1:8545')
    chainid = os.environ.get('CHAIN_ID', '1337')
    if ONCE:
        ONCE = False
        with capsys.disabled():
            print(f'Testing Conditional publishing var check with:')
            # print(f' Multicall contract at: {multicall} (overwrite with MULTICALL_ADDR=...)')
            # print(f' MOC (mock or real) at: {addr} (overwrite with MOC_ADDR=...)')
            print(f' RPC Node at: {node_url} (overwrite with MOC_ADDR=...)')
            print(f' Chain_id: {chainid} (overwrite with CHAIN_ID=...)')
    cfg = getCFG(capsys)
    bc = BlockChain(node_url, chainid, 1)
    return ConditionalPublishService(bc, cfg)


def test_ocfg(capsys):
    ocfg = getOCFG(capsys)
    assert ocfg.MULTICALL_ADDR is not None

def test_cfg(capsys):
    cfg = getCFG(capsys)
    assert cfg.valid
    assert cfg.cp=='BTCUSD'
    assert cfg._MOC_EMA is not None
    assert cfg._MOC_BASE_BUCKET is not None
    assert cfg._MOC_V3_BUCKET is not None
    assert cfg.MOC_EMA is not None
    assert cfg.MOC_BASE_BUCKET is not None
    assert cfg.MOC_V3_BUCKET is not None


def test_invalid_cfg(capsys):
    oc = getOCFG(capsys)
    cfg = ConditionalConfig('btcusd', oc)
    assert not cfg.valid


def test_active_base_condition_does_not_fetch_endpoint():
    service = conditional_service(base_condition_active=True, force_publish=True)

    service._sync_fetch()

    assert not service.offline_cfg()
    assert service.cfg.endpoint_calls == 0


def test_inactive_base_condition_fetches_endpoint_once_per_update():
    service = conditional_service(base_condition_active=False, force_publish=True)

    service._sync_fetch()

    assert not service.offline_cfg()
    assert not service.offline_cfg()
    assert service.cfg.endpoint_calls == 1


def test_inactive_conditions_without_force_publish_use_unneed_config():
    service = conditional_service(base_condition_active=False, force_publish=False)

    service._sync_fetch()

    assert service.offline_cfg()
    assert service.cfg.endpoint_calls == 1


def test_inactive_conditions_keep_previous_force_publish_until_endpoint_fetch_finishes():
    service = conditional_service(base_condition_active=False, force_publish=True)
    service._base_condition_active = False
    service._force_publish = True
    service._last_block = 123
    service._last_value = None
    service._sync_fetch_multiple = lambda *args: ([], 123)
    service.getConditionActive = lambda value, block: False

    class BlockingEndpointConfig(EndpointConfig):
        def __init__(self, force_publish):
            super().__init__(force_publish)
            self.entered = threading.Event()
            self.release = threading.Event()

        @property
        def ORACLE_OFFLINE_CFG_FORCE_PUBLISH(self):
            self.endpoint_calls += 1
            self.entered.set()
            self.release.wait(timeout=2)
            return self.force_publish

    cfg = BlockingEndpointConfig(force_publish=True)
    service.cfg = cfg

    refresh = threading.Thread(target=service._sync_fetch)
    refresh.start()

    assert cfg.entered.wait(timeout=1)
    assert not service.offline_cfg()

    cfg.release.set()
    refresh.join(timeout=1)

    assert not service.offline_cfg()
    assert service.cfg.endpoint_calls == 1


# def test_condition_qaclock(capsys):
#     ss = getSS(capsys)
#     result = ss._sync_fetch_multiple(ss._call_condition1_qACLockedInPending())
#     value, blocknr = result[0][0], result[1]
#     with capsys.disabled():
#         print(f'(block:{blocknr}) qACLockedInPending={value}')
#
#
# def test_condition_shouldCalculateEMA(capsys):
#     ss = getSS(capsys)
#     result = ss._sync_fetch_multiple(ss._call_condition2_shouldCalculateEMA())
#     value, blocknr = result[0][0], result[1]
#     with capsys.disabled():
#         print(f'(block:{blocknr}) shouldCalculateEMA={value}')
#
#
# def test_condition_getBTS(capsys):
#     ss = getSS(capsys)
#     result = ss._sync_fetch_multiple(ss._call_condition3_getBts())
#     value, blocknr = result[0][0], result[1]
#     with capsys.disabled():
#         print(f'(block:{blocknr}) getBts={value}')
#
#
# def test_condition_nextTCInterestPayment(capsys):
#     ss = getSS(capsys)
#     result = ss._sync_fetch_multiple(ss._call_condition4_nextTCInterestPayment())
#     value, blocknr = result[0][0], result[1]
#     with capsys.disabled():
#         print(f'(block:{blocknr}) nextTCInterestPayment={value}')
#
#
# def test_fetch_all(capsys):
#     ss = getSS(capsys)
#     result = ss._sync_fetch_multiple(
#         ss._call_condition1_qACLockedInPending(),
#         ss._call_condition2_shouldCalculateEMA(),
#         ss._call_condition3_getBts(),
#         ss._call_condition4_nextTCInterestPayment())
#     value, blocknr = result[0][0], result[1]
#     with capsys.disabled():
#         pprint(result)
#         print(f'(block:{blocknr}) nextTCInterestPayment={value}')
#
