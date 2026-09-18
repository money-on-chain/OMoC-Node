from unittest.mock import AsyncMock, MagicMock

import pytest

from common import settings
from common.services.blockchain import GasCalculator


def make_calculator(monkeypatch, network_gas_price, moc_max_gas_price):
    monkeypatch.setattr(settings, "DEFAULT_GAS_PRICE", 65_800_000)
    monkeypatch.setattr(settings, "GAS_PERCENTAGE_ADMITTED", 10)
    monkeypatch.setattr(settings, "GAS_PRICE_HARD_LIMIT_MIN", 0)
    monkeypatch.setattr(settings, "GAS_PRICE_HARD_LIMIT_MAX", 0)
    monkeypatch.setattr(settings, "GAS_PRICE_HARD_LIMIT_MULTIPLIER", 1)

    gas_limit_service = MagicMock()
    gas_limit_service.value = AsyncMock(return_value=moc_max_gas_price)
    calculator = GasCalculator(gas_limit_service)
    calculator.W3 = MagicMock()
    calculator.W3.eth.gasPrice = network_gas_price
    return calculator


@pytest.mark.asyncio
async def test_moc_max_gas_price_remains_a_floor_for_regular_publications(monkeypatch):
    calculator = make_calculator(monkeypatch, 22_000_000, 30_300_000)

    gas_price = await calculator.get_current()

    assert gas_price == 30_300_001


@pytest.mark.asyncio
async def test_moc_max_gas_price_is_a_ceiling_for_liquidations(monkeypatch):
    calculator = make_calculator(monkeypatch, 45_000_000, 30_300_000)

    gas_price = await calculator.get_current(gas_limit_as_ceiling=True)

    assert gas_price == 30_299_999
    assert calculator.last_price == 45_000_000


@pytest.mark.asyncio
async def test_liquidation_keeps_lower_network_gas_price(monkeypatch):
    calculator = make_calculator(monkeypatch, 22_000_000, 30_300_000)

    gas_price = await calculator.get_current(gas_limit_as_ceiling=True)

    assert gas_price == 22_000_000
