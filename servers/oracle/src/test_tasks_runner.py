from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from common import settings
from common.services.coin_pair_service_types import CoinPairServiceType
from common.services.oracle_dao import CoinPair
from oracle.src import request_validation
from oracle.src.oracle_coin_pair_loop import OracleCoinPairLoop
from oracle.src.oracle_coin_pair_service import OracleCoinPairService
from oracle.src.oracle_publish_message import PublishTaskParams
from oracle.src.request_validation import ValidationFailure
from oracle.src.tasks_runner import TasksRunner


STUCK_TASK = "0x40652119dfC7a114c43D36bd5369400577803E91"
OTHER_TASK = "0x610Bb1573d1046FCb8A70Bbbd395754cD57C2b60"


def make_runner(tasks):
    runner = TasksRunner.__new__(TasksRunner)
    runner.reset(None, "TASKS")
    runner._conf = SimpleNamespace(TASK_MESSAGE_VERSION=3)
    runner._last_block_when_available = None
    runner.cps = SimpleNamespace(
        coin_pair=CoinPair("TASKS"),
        get_are_tasks_available=AsyncMock(return_value=True),
        get_tasks_available_as_flags=AsyncMock(return_value=7),
        get_tasks_available=AsyncMock(return_value=tasks),
        log_data=AsyncMock(return_value="tasks available"),
    )
    runner.oracle_turn = Mock()
    runner.oracle_turn.is_oracle_turn.return_value = (True, [OTHER_TASK])
    runner.vi_loop = SimpleNamespace(get=Mock(return_value=SimpleNamespace(last_pub_block=5)))
    return runner


@pytest.mark.asyncio
async def test_available_task_addresses_are_forwarded_from_contract_service():
    service = OracleCoinPairService.__new__(OracleCoinPairService)
    service._coin_pair_service = SimpleNamespace(
        get_service_type=Mock(return_value=CoinPairServiceType.TASKS_RUNNER),
        get_tasks_available=AsyncMock(return_value=[STUCK_TASK]),
    )

    assert await service.get_tasks_available() == [STUCK_TASK]
    service._coin_pair_service.get_tasks_available.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_ignored_tasks_prevent_publish_and_signing(monkeypatch):
    monkeypatch.setattr(settings, "IGNORE_POSSIBLY_STUCK_TASKS", {STUCK_TASK.lower()})
    runner = make_runner([STUCK_TASK])

    assert await runner.is_oracle_turn(SimpleNamespace(block_num=6), OTHER_TASK) == (False, None, None)
    runner.oracle_turn.is_oracle_turn.assert_not_called()
    assert runner._tasks_flags == 0

    params = PublishTaskParams(3, runner.cps.coin_pair, 7, OTHER_TASK, 5)
    validator = await runner.create_validator(params)
    assert validator.are_tasks_available is False
    assert validator.tasks_flags == 0
    with pytest.raises(ValidationFailure):
        validator.validate_and_sign("0x00")


@pytest.mark.asyncio
async def test_ignored_tasks_never_start_signature_gathering(monkeypatch):
    monkeypatch.setattr(settings, "IGNORE_POSSIBLY_STUCK_TASKS", {STUCK_TASK.lower()})
    runner = make_runner([STUCK_TASK])
    runner.signal_service = SimpleNamespace(
        update=AsyncMock(), from_blockchain=Mock()
    )
    runner.cps.get_round_info = AsyncMock(return_value=SimpleNamespace(round=1))
    runner.vi_loop.get.return_value = SimpleNamespace(block_num=6, last_pub_block=5)
    loop = OracleCoinPairLoop.__new__(OracleCoinPairLoop)
    loop.reset(None, "TASKS")
    loop._runner = runner
    loop._oracle_addr = OTHER_TASK
    loop._conf = SimpleNamespace(ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL=3)
    loop._trace_enabled = False
    loop.publish = AsyncMock()

    assert await loop.run() == 3
    loop.publish.assert_not_awaited()
    runner.oracle_turn.is_oracle_turn.assert_not_called()


@pytest.mark.asyncio
async def test_ignored_tasks_reject_matching_zero_flags_without_signing(monkeypatch):
    monkeypatch.setattr(settings, "IGNORE_POSSIBLY_STUCK_TASKS", {STUCK_TASK.lower()})
    sign_message = Mock()
    monkeypatch.setattr(request_validation.crypto, "sign_message", sign_message)
    runner = make_runner([STUCK_TASK])
    runner.oracle_turn.validate_turn.return_value = (False, "There are no tasks available")
    validator = await runner.create_validator(
        PublishTaskParams(3, runner.cps.coin_pair, 0, OTHER_TASK, 5)
    )

    with pytest.raises(ValidationFailure):
        validator.validate_and_sign("0x00")
    sign_message.assert_not_called()


@pytest.mark.asyncio
async def test_mixed_tasks_remain_available(monkeypatch):
    monkeypatch.setattr(settings, "IGNORE_POSSIBLY_STUCK_TASKS", {STUCK_TASK.lower()})
    runner = make_runner([STUCK_TASK, OTHER_TASK])

    assert await runner.is_oracle_turn(SimpleNamespace(block_num=6), OTHER_TASK) == (
        True, True, [OTHER_TASK]
    )
    assert runner._tasks_flags == 7
    validator = await runner.create_validator(
        PublishTaskParams(3, runner.cps.coin_pair, 7, OTHER_TASK, 5)
    )
    assert validator.are_tasks_available is True
    assert validator.tasks_flags == 7


@pytest.mark.asyncio
async def test_multiple_ignored_tasks_suppress_the_round(monkeypatch):
    monkeypatch.setattr(
        settings, "IGNORE_POSSIBLY_STUCK_TASKS", {STUCK_TASK.lower(), OTHER_TASK.lower()}
    )
    runner = make_runner([STUCK_TASK, OTHER_TASK])

    assert await runner.is_oracle_turn(SimpleNamespace(block_num=6), OTHER_TASK) == (False, None, None)
    runner.oracle_turn.is_oracle_turn.assert_not_called()


@pytest.mark.asyncio
async def test_unconfigured_ignore_list_keeps_existing_behavior(monkeypatch):
    monkeypatch.setattr(settings, "IGNORE_POSSIBLY_STUCK_TASKS", frozenset())
    runner = make_runner([STUCK_TASK])

    assert await runner.is_oracle_turn(SimpleNamespace(block_num=6), OTHER_TASK) == (
        True, True, [OTHER_TASK]
    )
    runner.cps.get_tasks_available.assert_not_awaited()
