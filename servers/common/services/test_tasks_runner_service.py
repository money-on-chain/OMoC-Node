import logging

import pytest

from common.services.blockchain import BCError
from common.services.coin_pair_price_service import TasksRunnerService


class _FailingContract:
    addr = "0x0000000000000000000000000000000000000000"

    async def bc_call(self, method, *args, **kw):
        return BCError.Get("revert")


@pytest.mark.asyncio
async def test_get_are_tasks_available_revert_logs_warning(caplog):
    service = TasksRunnerService(_FailingContract())
    with caplog.at_level(logging.WARNING):
        ret = await service.get_are_tasks_available()
    assert ret is False
    assert "areTasksAvailable reverted, assuming false" in caplog.text


@pytest.mark.asyncio
async def test_get_tasks_available_revert_logs_warning(caplog):
    service = TasksRunnerService(_FailingContract())
    with caplog.at_level(logging.WARNING):
        ret = await service.get_tasks_available()
    assert ret == []
    assert "getTasksAvailable reverted, assuming empty list" in caplog.text


@pytest.mark.asyncio
async def test_get_tasks_available_as_flags_revert_logs_warning(caplog):
    service = TasksRunnerService(_FailingContract())
    with caplog.at_level(logging.WARNING):
        ret = await service.get_tasks_available_as_flags()
    assert ret == 0
    assert "getTasksAvailableAsFlags reverted, assuming 0" in caplog.text
