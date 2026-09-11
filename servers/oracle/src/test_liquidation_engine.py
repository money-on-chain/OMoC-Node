import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from hexbytes import HexBytes
from web3 import Web3

from common.services.coin_pair_price_service import LiquidationEngineService
from common.services.contract_factory_service import (
    LIQUIDATION_ENGINE_ABI,
    with_liquidation_engine_abi,
)
from common.services.oracle_dao import CoinPair
from oracle.src.liquidation_runner import LiquidationRunner
from oracle.src.oracle_publish_message import PoolLiquidations, PublishLiquidationParams
from oracle.src.lending import LendingLiquidationProvider, LendingMarket
from oracle.src.request_validation import LiquidationRequestValidation, ValidationFailure


POOL_ID = "0x" + "11" * 32
POOL_ID_B = "0x" + "22" * 32
ORACLE = "0x0000000000000000000000000000000000000003"
USER = "0x0000000000000000000000000000000000000002"
USER_B = "0x0000000000000000000000000000000000000008"
USER_C = "0x0000000000000000000000000000000000000009"
TP_TOKEN = "0x0000000000000000000000000000000000000004"
MOC_BUCKET = "0x0000000000000000000000000000000000000005"
TP_TOKEN_B = "0x000000000000000000000000000000000000000a"
MOC_BUCKET_B = "0x000000000000000000000000000000000000000b"
MANAGER = "0x0000000000000000000000000000000000000006"
MULTICALL = "0x0000000000000000000000000000000000000007"


def liquidation_params(liquidations=None):
    return PublishLiquidationParams(
        3,
        CoinPair("LENDING"),
        liquidations if liquidations is not None else [PoolLiquidations(POOL_ID, [USER])],
        ORACLE,
        123,
    )


def test_liquidation_message_matches_contract_shape():
    params = liquidation_params()

    assert len(params.prepare_msg()) == 116 * 2
    assert params.prepare_msg()[0:64] == (3).to_bytes(32, "big").hex()
    assert params.prepare_msg()[64:128] == CoinPair("LENDING").longer().hex()
    assert params.prepare_msg()[128:168] == ORACLE[2:].lower()
    assert params.prepare_msg()[168:232] == (123).to_bytes(32, "big").hex()


def test_liquidation_authorization_post_excludes_local_batch():
    params = liquidation_params()
    post = params.to_post_data(HexBytes("0x01"))
    parsed = PublishLiquidationParams.from_post_data(
        post["version"],
        post["coin_pair"],
        post["oracle_addr"],
        post["last_pub_block"],
    )

    assert str(parsed.coin_pair) == str(params.coin_pair)
    assert parsed.liquidations == ()
    assert "liquidations" not in post
    assert params.get_post() == "/sign-liquidation/"
    assert params.as_contract_liquidations() == [(POOL_ID, [USER])]


def test_liquidation_engine_abi_is_extended_without_duplicates():
    base = [{"name": "getPrice", "type": "function"}]
    extended = with_liquidation_engine_abi(base)
    extended_again = with_liquidation_engine_abi(extended)

    names = [item.get("name") for item in extended]
    assert names.count("runLiquidations") == 1
    assert names.count("getPoolId") == 1
    assert names.count("maxLiquidationsPerBatch") == 1
    assert extended_again is extended


def test_liquidation_engine_abi_encodes_run_liquidations():
    contract = Web3().eth.contract(abi=LIQUIDATION_ENGINE_ABI)
    encoded = contract.functions.runLiquidations(
        3,
        CoinPair("LENDING").longer(),
        [(HexBytes(POOL_ID), [USER])],
        ORACLE,
        123,
        [27],
        [b"r" * 32],
        [b"s" * 32],
    )._encode_transaction_data()

    assert encoded.startswith("0x")


@pytest.mark.asyncio
async def test_liquidation_service_calls_run_liquidations():
    service = LiquidationEngineService(object())
    service.coin_pair_execute = AsyncMock(return_value="tx")

    result = await service._publish(liquidation_params(), [27], [b"r"], [b"s"])

    assert result == "tx"
    call = service.coin_pair_execute.await_args
    assert call.args[:6] == (
        "runLiquidations",
        3,
        CoinPair("LENDING").longer(),
        [(POOL_ID, [USER])],
        ORACLE,
        123,
    )
    assert call.args[6:9] == ([27], [b"r"], [b"s"])


@pytest.mark.asyncio
async def test_liquidation_service_reads_contract_batch_limit():
    service = LiquidationEngineService(object())
    service.coin_pair_call = AsyncMock(return_value=12)

    assert await service.get_max_liquidations_per_batch() == 12
    service.coin_pair_call.assert_awaited_once_with("maxLiquidationsPerBatch")


@pytest.mark.asyncio
async def test_liquidation_service_checks_availability_with_multicall():
    encoded_calls = []

    class ManagerFunctions:
        @staticmethod
        def isLiquidationAvailable(user, tp_token, moc_bucket):
            return SimpleNamespace(
                _encode_transaction_data=lambda: "0x" + user[2:]
            )

    class MulticallFunctions:
        @staticmethod
        def tryAggregate(require_success, calls):
            encoded_calls.extend(calls)
            assert require_success is False
            return SimpleNamespace(
                call=lambda transaction: [
                    (True, (1).to_bytes(32, "big")),
                    (True, (0).to_bytes(32, "big")),
                ]
            )

    blockchain = SimpleNamespace(
        get_contract=Mock(
            side_effect=[
                SimpleNamespace(functions=ManagerFunctions()),
                SimpleNamespace(functions=MulticallFunctions()),
            ]
        )
    )
    service = LiquidationEngineService(
        SimpleNamespace(_blockchain=blockchain, addr=MULTICALL)
    )
    service.get_lending_manager = AsyncMock(return_value=MANAGER)

    results = await service.get_liquidations_available(
        [(USER, TP_TOKEN, MOC_BUCKET), (ORACLE, TP_TOKEN, MOC_BUCKET)],
        MULTICALL,
    )

    assert results == [True, False]
    assert [target for target, _ in encoded_calls] == [MANAGER, MANAGER]


@pytest.mark.asyncio
async def test_provider_builds_grouped_liquidations_with_multicall():
    service = SimpleNamespace(
        get_liquidation_pool_id=AsyncMock(return_value=HexBytes(POOL_ID)),
        get_liquidation_pool=AsyncMock(return_value=(TP_TOKEN, MOC_BUCKET, True)),
        get_liquidations_available=AsyncMock(return_value=[True, False]),
    )
    repository = SimpleNamespace(
        top_vaults=Mock(
            return_value=[
                SimpleNamespace(
                    user=USER,
                    ac_balance="100",
                    credit_units="90",
                    liquidating=False,
                ),
                SimpleNamespace(
                    user=ORACLE,
                    ac_balance="100",
                    credit_units="80",
                    liquidating=False,
                ),
            ]
        )
    )
    indexer = SimpleNamespace(status=Mock(return_value={"status": "ready"}))
    provider = LendingLiquidationProvider(
        service,
        repository,
        indexer,
        markets=[LendingMarket(TP_TOKEN, MOC_BUCKET)],
        multicall_addr=MULTICALL,
    )

    liquidations = await provider.build_liquidations(2)

    assert liquidations == [PoolLiquidations(POOL_ID, [USER])]
    expected_call = (
        [
            (
                USER,
                Web3.toChecksumAddress(TP_TOKEN),
                Web3.toChecksumAddress(MOC_BUCKET),
            ),
            (
                ORACLE,
                Web3.toChecksumAddress(TP_TOKEN),
                Web3.toChecksumAddress(MOC_BUCKET),
            ),
        ],
        MULTICALL,
    )
    service.get_liquidations_available.assert_awaited_once_with(*expected_call)


@pytest.mark.asyncio
async def test_provider_interleaves_markets_and_does_not_refill_unavailable_slots():
    def vault(user, risk):
        return SimpleNamespace(
            user=user,
            ac_balance="100",
            credit_units=str(risk),
            liquidating=False,
        )

    service = SimpleNamespace(
        get_liquidation_pool_id=AsyncMock(
            side_effect=[HexBytes(POOL_ID), HexBytes(POOL_ID_B)]
        ),
        get_liquidation_pool=AsyncMock(
            side_effect=[
                (TP_TOKEN, MOC_BUCKET, True),
                (TP_TOKEN_B, MOC_BUCKET_B, True),
            ]
        ),
        get_liquidations_available=AsyncMock(return_value=[True, False, True]),
    )
    repository = SimpleNamespace(
        top_vaults=Mock(
            side_effect=[
                [vault(USER, 90), vault(USER_B, 80)],
                [vault(ORACLE, 70), vault(USER_C, 60)],
            ]
        )
    )
    provider = LendingLiquidationProvider(
        service,
        repository,
        SimpleNamespace(status=Mock(return_value={"status": "ready"})),
        markets=[
            LendingMarket(TP_TOKEN, MOC_BUCKET),
            LendingMarket(TP_TOKEN_B, MOC_BUCKET_B),
        ],
        multicall_addr=MULTICALL,
    )

    liquidations = await provider.build_liquidations(3)

    assert liquidations == [PoolLiquidations(POOL_ID, [USER, USER_B])]
    checked = service.get_liquidations_available.await_args.args[0]
    assert [item[0] for item in checked] == [USER, ORACLE, USER_B]
    assert len(checked) == 3


@pytest.mark.asyncio
async def test_runner_publishes_liquidations_with_engine_nonce():
    runner = LiquidationRunner.__new__(LiquidationRunner)
    runner.cps = SimpleNamespace(
        coin_pair=CoinPair("LENDING"),
        get_max_liquidations_per_batch=AsyncMock(return_value=7),
    )
    runner.liquidation_provider = SimpleNamespace(
        build_liquidations=AsyncMock(return_value=[PoolLiquidations(POOL_ID, [USER])])
    )
    runner.oracle_turn = SimpleNamespace(
        is_oracle_turn=Mock(return_value=(True, [ORACLE]))
    )
    runner._discovery = None
    runner._retry_at = 0
    runner._liquidations = []
    runner._conf = SimpleNamespace(LIQUIDATION_MESSAGE_VERSION=3)
    blockchain_info = SimpleNamespace(block_num=130, last_pub_block=123)

    available, my_turn, _ = await runner.is_oracle_turn(blockchain_info, ORACLE)
    params = runner.prepare_publish_params(blockchain_info, ORACLE)

    assert available and my_turn
    runner.liquidation_provider.build_liquidations.assert_awaited_once_with(7)
    expected = liquidation_params()
    assert str(params.coin_pair) == str(expected.coin_pair)
    assert params._replace(coin_pair=expected.coin_pair) == expected


@pytest.mark.asyncio
async def test_runner_reuses_discovery_that_completed_after_timeout():
    expected = [PoolLiquidations(POOL_ID, [USER])]
    runner = LiquidationRunner.__new__(LiquidationRunner)
    runner._discovery = asyncio.create_task(asyncio.sleep(0, result=expected))
    runner._retry_at = 0
    await runner._discovery

    assert await runner._discover_liquidations() == expected
    assert runner._discovery is None


def test_liquidation_validator_checks_authorization_version():
    params = liquidation_params()
    turn = SimpleNamespace(is_oracle_turn=Mock(return_value=(True, [ORACLE])))
    blockchain_info = SimpleNamespace(last_pub_block=123)
    validator = LiquidationRequestValidation(params, turn, blockchain_info, 3)
    validator.validate_params()
    validator.validate_turn()


def test_lending_name_is_detected_as_liquidation_engine():
    assert CoinPair("LENDING").is_liquidation_engine()
    assert CoinPair("LIQUIDATIONS").is_liquidation_engine()
    assert not CoinPair("TASKS").is_liquidation_engine()
