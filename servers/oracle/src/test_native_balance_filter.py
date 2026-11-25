import asyncio
from types import SimpleNamespace

from common.services.oracle_dao import CoinPair, FullOracleRoundInfo, OracleBlockchainInfo
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfoLoop
from oracle.src.oracle_turn import OracleTurn
from w3multicall.multicall import W3Multicall


def oracle(number):
    addr = "0x" + format(number, "040x")
    return FullOracleRoundInfo(addr, "http://localhost", 1, addr, 0, True, 1)


class TurnForTest(OracleTurn):
    def __init__(self):
        pass

    def _is_oracle_turn_with_msg(self, vi, oracle_addr, oracle_addresses, extra_args,
                                 only_chosen=False):
        return oracle_addr in oracle_addresses, None


def make_loop(monkeypatch, balances, gas_prices=None):
    selected = [oracle(1), oracle(2), oracle(3)]
    snapshot = OracleBlockchainInfo(CoinPair("BTCUSD"), selected, 1, 10, 9,
                                    "0x" + "01" * 32, 60)
    calls = []

    class MulticallForTest:
        Call = W3Multicall.Call

        def __init__(self, web3, address):
            self.address = address
            self.batch = []

        def add(self, call):
            self.batch.append(call)

        def call(self, block_identifier=None):
            calls.append((self.address, self.batch, block_identifier))
            result = balances.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

    monkeypatch.setattr("oracle.src.oracle_blockchain_info_loop.W3Multicall", MulticallForTest)
    async def execute_now(func):
        return func()

    monkeypatch.setattr("oracle.src.oracle_blockchain_info_loop.run_in_executor", execute_now)
    loop = object.__new__(OracleBlockchainInfoLoop)
    loop._conf = SimpleNamespace(ORACLE_MIN_PUBLICATION_GAS=10, MULTICALL_ADDR=oracle(99).addr)
    gas_prices = list(gas_prices if gas_prices is not None else [10] * max(1, len(balances)))
    async def get_current_gas_price():
        return gas_prices.pop(0)

    loop._gas_calc = SimpleNamespace(get_current=get_current_gas_price)
    loop._cps = SimpleNamespace(
        _blockchain=SimpleNamespace(W3=object()),
        is_info_service_available=lambda: True,
        get_oracle_server_info=lambda: asyncio.sleep(0, result=snapshot),
    )
    loop._blockchain_info = None
    class LockForTest:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    loop.update_lock = LockForTest()
    loop.last_update = None
    return loop, selected, calls


def test_multicall_filters_turns_and_reinstates_recharged_oracle(monkeypatch):
    loop, selected, calls = make_loop(monkeypatch, [[99, 100, 150], [100, 100, 150]])

    asyncio.run(loop.force_update())
    first = loop.get()
    assert first.selected_oracles == selected
    assert first.eligible_oracles == selected[1:]
    assert len(calls) == 1
    assert calls[0][2] == "latest"
    assert [call.args[0] for call in calls[0][1]] == [x.addr for x in selected]
    assert all(call.address == loop._conf.MULTICALL_ADDR and
               call.signature == "getEthBalance(address)(uint256)" for call in calls[0][1])

    turn = TurnForTest()
    assert selected[0].addr not in turn.is_oracle_turn(first, selected[0].addr, None)[1]
    assert turn.validate_turn(first, selected[0].addr, None)[0] is False

    asyncio.run(loop.force_update())
    second = loop.get()
    assert second.eligible_oracles == selected
    assert selected[0].addr in turn.is_oracle_turn(second, selected[0].addr, None)[1]
    assert len(calls) == 2


def test_multicall_failure_closes_turns(monkeypatch):
    loop, selected, _ = make_loop(monkeypatch, [RuntimeError("RPC unavailable")])
    asyncio.run(loop.force_update())
    assert loop.get().eligible_oracles == []
    turn = TurnForTest()
    assert turn.is_oracle_turn(loop.get(), selected[0].addr, None) == (False, [])
    assert turn.validate_turn(loop.get(), selected[0].addr, None)[0] is False


def test_zero_threshold_skips_multicall(monkeypatch):
    loop, selected, calls = make_loop(monkeypatch, [])
    loop._conf.ORACLE_MIN_PUBLICATION_GAS = 0
    asyncio.run(loop.force_update())
    assert loop.get().eligible_oracles is None
    assert loop.get().selected_oracles == selected
    assert calls == []


def test_gas_price_changes_required_balance(monkeypatch):
    loop, selected, _ = make_loop(monkeypatch, [[150, 150, 150], [150, 150, 150]],
                                  gas_prices=[10, 20])
    asyncio.run(loop.force_update())
    assert loop.get().eligible_oracles == selected
    asyncio.run(loop.force_update())
    assert loop.get().eligible_oracles == []


def test_gas_price_failure_closes_turns_without_multicall(monkeypatch):
    loop, _, calls = make_loop(monkeypatch, [[150, 150, 150]], gas_prices=[None])
    asyncio.run(loop.force_update())
    assert loop.get().eligible_oracles == []
    assert calls == []
