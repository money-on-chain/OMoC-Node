import os
from pprint import pprint

from common.services.blockchain import BlockChain
from common.services.signal_service import ConditionalPublishService

ONCE = True


def getSS(capsys):
    global ONCE
    multicall = os.environ.get('MULTICALL_ADDR', '0x72440269630E393d38975Db7fA7Cb4D14e7eC061')
    addr = os.environ.get('MOC_ADDR', '0xD8d315932b5c5b9B21B14A39f5F12e4b9Bd65571')
    node_url = os.environ.get('NODE_URL', 'http://127.0.0.1:8545')
    chainid = os.environ.get('CHAIN_ID', '1337')

    if ONCE:
        ONCE = False
        with capsys.disabled():
            print(f'Testing Conditional publishing var check with:')
            print(f' Multicall contract at: {multicall} (overwrite with MULTICALL_ADDR=...)')
            print(f' MOC (mock or real) at: {addr} (overwrite with MOC_ADDR=...)')
            print(f' RPC Node at: {node_url} (overwrite with MOC_ADDR=...)')
            print(f' Chain_id: {chainid} (overwrite with CHAIN_ID=...)')

    bc = BlockChain(node_url, chainid, 1)
    return ConditionalPublishService(blockchain=bc, cp ='BTCUSD', multicall=multicall, addr=addr)


def test_condition_qaclock(capsys):
    ss = getSS(capsys)
    result = ss._sync_fetch_multiple(ss._call_condition1_qACLockedInPending())
    value, blocknr = result[0][0], result[1]
    with capsys.disabled():
        print(f'(block:{blocknr}) qACLockedInPending={value}')


def test_condition_shouldCalculateEMA(capsys):
    ss = getSS(capsys)
    result = ss._sync_fetch_multiple(ss._call_condition2_shouldCalculateEMA())
    value, blocknr = result[0][0], result[1]
    with capsys.disabled():
        print(f'(block:{blocknr}) shouldCalculateEMA={value}')


def test_condition_getBTS(capsys):
    ss = getSS(capsys)
    result = ss._sync_fetch_multiple(ss._call_condition3_getBts())
    value, blocknr = result[0][0], result[1]
    with capsys.disabled():
        print(f'(block:{blocknr}) getBts={value}')


def test_condition_nextTCInterestPayment(capsys):
    ss = getSS(capsys)
    result = ss._sync_fetch_multiple(ss._call_condition4_nextTCInterestPayment())
    value, blocknr = result[0][0], result[1]
    with capsys.disabled():
        print(f'(block:{blocknr}) nextTCInterestPayment={value}')


def test_fetch_all(capsys):
    ss = getSS(capsys)
    result = ss._sync_fetch_multiple(
        ss._call_condition1_qACLockedInPending(),
        ss._call_condition2_shouldCalculateEMA(),
        ss._call_condition3_getBts(),
        ss._call_condition4_nextTCInterestPayment())
    value, blocknr = result[0][0], result[1]
    with capsys.disabled():
        pprint(result)
        print(f'(block:{blocknr}) nextTCInterestPayment={value}')

