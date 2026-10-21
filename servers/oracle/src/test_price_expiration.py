import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from common import crypto
from common.services.blockchain import BlockchainAccount
from common.services.coin_pair_price_service import CoinPairService
from common.services.contract_factory_service import with_expiring_publish_abi
from common.services.oracle_dao import (
    CoinPair,
    FullOracleRoundInfo,
    OracleBlockchainInfo,
    PriceWithTimestamp,
)
from hexbytes import HexBytes
from starlette.datastructures import Secret

from oracle.src import oracle_coin_pair_loop, request_validation
from oracle.src import app as oracle_app
from oracle.src.coin_pair_runner import CoinPairRunner
from oracle.src.oracle_publish_message import PublishPriceParams
from oracle.src.request_validation import PriceRequestValidation, ValidationFailure
from oracle.src.tasks_runner import TasksRunner

COIN_PAIR = CoinPair("BTCUSD")
ORACLE_ADDR = "0x610Bb1573d1046FCb8A70Bbbd395754cD57C2b60"
ORACLE_PRIVATE_KEY = (
    "0x77c5495fbb039eed474fc940f29955ed0531693cc9212911efd35dff0373153f"
)
LEGACY_ORACLE_ADDR = "0x855FA758c77D68a04990E992aA4dcdeF899F654A"
LEGACY_ORACLE_PRIVATE_KEY = (
    "0xd99b5b29e6da2528bf458b26237a6cf8655a3e3276c1cdc0de1f98cefee81c01"
)
THIRD_ORACLE_ADDR = "0xfA2435Eacf10Ca62ae6787ba2fB044f8733Ee843"


def account(address, private_key):
    result = BlockchainAccount(address, Secret(private_key))
    assert crypto.addr_from_key(private_key) == address
    return result


def price_params(version=3, expiration=None):
    return PublishPriceParams(
        version,
        COIN_PAIR,
        PriceWithTimestamp(10**18, 1_700_000_000),
        ORACLE_ADDR,
        123,
        expiration,
    )


def validator(params, min_validity=30, max_validity=600):
    return PriceRequestValidation(
        50,
        params,
        None,
        PriceWithTimestamp(10**18, 1_700_000_000),
        OracleBlockchainInfo(COIN_PAIR, [], 10**18, 124, 123, "", 300),
        min_validity,
        max_validity,
    )


def test_v3_and_v4_message_encoding():
    legacy = price_params()
    expiring = price_params(4, 1_800_000_000)

    assert len(legacy.prepare_msg()) == 148 * 2
    assert len(expiring.prepare_msg()) == 180 * 2
    assert expiring.prepare_msg().endswith(format(1_800_000_000, "064x"))
    assert expiring.as_legacy().prepare_msg() == legacy.prepare_msg()
    assert expiring.get_post() == "/sign-price-v4/"
    assert expiring.to_post_data(HexBytes("0x01"))["expiration"] == "1800000000"


@pytest.mark.asyncio
async def test_migrated_node_still_signs_v3_requests(monkeypatch):
    validation_data = Mock()
    validation_data.validate_and_sign.return_value = (
        "legacy-message",
        HexBytes("0x01"),
    )
    get_validation_data = AsyncMock(return_value=validation_data)
    monkeypatch.setattr(
        oracle_app.main_executor,
        "get_validation_data",
        get_validation_data,
    )

    response = await oracle_app.sign(
        version="3",
        coin_pair=str(COIN_PAIR),
        price=str(10**18),
        price_timestamp="1700000000",
        oracle_addr=ORACLE_ADDR,
        last_pub_block="123",
        signature="0x02",
    )

    assert response == {"message": "legacy-message", "signature": "0x01"}
    assert get_validation_data.await_args.args[0].version == 3


@pytest.mark.asyncio
async def test_info_reports_migration_capabilities():
    capabilities = (await oracle_app.read_info())["capabilities"]

    assert capabilities["price_signature_versions"] == [3, 4]


def test_expiration_validation(monkeypatch):
    monkeypatch.setattr(request_validation.time, "time", lambda: 1_000)

    validator(price_params(4, 1_300)).validate_params()

    with pytest.raises(ValidationFailure, match="too close or expired"):
        validator(price_params(4, 1_020)).validate_params()

    with pytest.raises(ValidationFailure, match="too far"):
        validator(price_params(4, 1_601)).validate_params()

    with pytest.raises(ValidationFailure, match="only valid for V4"):
        validator(price_params(3, 1_300)).validate_params()


@pytest.mark.asyncio
async def test_v4_signature_request_falls_back_to_v3(monkeypatch):
    params = price_params(4, int(time.time()) + 300)
    legacy = params.as_legacy()
    response = oracle_coin_pair_loop.OracleSignature(ORACLE_ADDR, HexBytes("0x01"))
    request_once = AsyncMock(
        side_effect=[
            oracle_coin_pair_loop.SIGNATURE_ENDPOINT_UNSUPPORTED,
            response,
        ]
    )
    monkeypatch.setattr(oracle_coin_pair_loop, "_get_signature_once", request_once)
    oracle = FullOracleRoundInfo(
        ORACLE_ADDR,
        "http://127.0.0.1:5001",
        1,
        ORACLE_ADDR,
        0,
        True,
        1,
    )

    result = await oracle_coin_pair_loop.get_signature(
        oracle,
        params,
        params.prepare_msg(),
        HexBytes("0x02"),
        legacy_params=legacy,
        legacy_message=legacy.prepare_msg(),
        legacy_signature=HexBytes("0x03"),
    )

    assert result == response
    assert request_once.await_count == 2
    assert request_once.await_args_list[0].args[1].version == 4
    assert request_once.await_args_list[1].args[1].version == 3


@pytest.mark.asyncio
async def test_v4_signature_rejection_does_not_fall_back_to_v3(monkeypatch):
    params = price_params(4, int(time.time()) + 300)
    legacy = params.as_legacy()
    request_once = AsyncMock(return_value=None)
    monkeypatch.setattr(oracle_coin_pair_loop, "_get_signature_once", request_once)
    oracle = FullOracleRoundInfo(
        ORACLE_ADDR,
        "http://127.0.0.1:5001",
        1,
        ORACLE_ADDR,
        0,
        True,
        1,
    )

    result = await oracle_coin_pair_loop.get_signature(
        oracle,
        params,
        params.prepare_msg(),
        HexBytes("0x02"),
        legacy_params=legacy,
        legacy_message=legacy.prepare_msg(),
        legacy_signature=HexBytes("0x03"),
    )

    assert result is None
    request_once.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, expected",
    [
        (404, oracle_coin_pair_loop.SIGNATURE_ENDPOINT_UNSUPPORTED),
        (405, oracle_coin_pair_loop.SIGNATURE_ENDPOINT_UNSUPPORTED),
        (424, None),
    ],
)
async def test_signature_http_status_controls_legacy_fallback(
    monkeypatch, status, expected
):
    request_post = AsyncMock(return_value=("response", status))
    monkeypatch.setattr(oracle_coin_pair_loop.helpers, "request_post", request_post)
    oracle = FullOracleRoundInfo(
        LEGACY_ORACLE_ADDR,
        "http://127.0.0.1:5001",
        1,
        LEGACY_ORACLE_ADDR,
        0,
        True,
        1,
    )
    params = price_params(4, int(time.time()) + 300)

    result = await oracle_coin_pair_loop._get_signature_once(
        oracle,
        params,
        params.prepare_msg(),
        HexBytes("0x02"),
    )

    assert result is expected


@pytest.mark.asyncio
async def test_gather_signatures_accepts_mixed_v4_and_legacy_quorum(monkeypatch):
    publisher = account(ORACLE_ADDR, ORACLE_PRIVATE_KEY)
    legacy_oracle = account(LEGACY_ORACLE_ADDR, LEGACY_ORACLE_PRIVATE_KEY)
    params = price_params(4, int(time.time()) + 300)
    legacy_params = params.as_legacy()
    message = params.prepare_msg()
    legacy_message = legacy_params.prepare_msg()
    publisher_signature = crypto.sign_message(hexstr=message, account=publisher)
    publisher_legacy_signature = crypto.sign_message(
        hexstr=legacy_message, account=publisher
    )
    legacy_signature = crypto.sign_message(
        hexstr=legacy_message, account=legacy_oracle
    )

    async def request_once(oracle, requested_params, *args, **kwargs):
        if oracle.addr == LEGACY_ORACLE_ADDR:
            if requested_params.version == 4:
                return oracle_coin_pair_loop.SIGNATURE_ENDPOINT_UNSUPPORTED
            return oracle_coin_pair_loop.OracleSignature(
                LEGACY_ORACLE_ADDR, legacy_signature
            )
        return None

    monkeypatch.setattr(oracle_coin_pair_loop, "_get_signature_once", request_once)
    oracles = [
        FullOracleRoundInfo(
            ORACLE_ADDR, "http://127.0.0.1:5000", 1, ORACLE_ADDR, 0, True, 1
        ),
        FullOracleRoundInfo(
            LEGACY_ORACLE_ADDR,
            "http://127.0.0.1:5001",
            1,
            LEGACY_ORACLE_ADDR,
            0,
            True,
            1,
        ),
        FullOracleRoundInfo(
            THIRD_ORACLE_ADDR,
            "http://127.0.0.1:5002",
            1,
            THIRD_ORACLE_ADDR,
            0,
            True,
            1,
        ),
    ]

    signatures = await oracle_coin_pair_loop.gather_signatures(
        oracles,
        params,
        message,
        publisher_signature,
        legacy_params=legacy_params,
        legacy_message=legacy_message,
        legacy_signature=publisher_legacy_signature,
    )

    assert signatures == [publisher_signature, legacy_signature]
    assert crypto.verify_signature(ORACLE_ADDR, message, signatures[0])
    assert crypto.verify_signature(LEGACY_ORACLE_ADDR, legacy_message, signatures[1])


@pytest.mark.asyncio
async def test_publish_does_not_send_transaction_when_expiration_is_too_close(
    monkeypatch,
):
    params = price_params(4, 1_020)
    gather = AsyncMock(return_value=[HexBytes("0x01"), HexBytes("0x02")])
    monkeypatch.setattr(oracle_coin_pair_loop, "gather_signatures", gather)
    monkeypatch.setattr(oracle_coin_pair_loop.crypto, "sign_message", Mock())
    monkeypatch.setattr(
        oracle_coin_pair_loop.oracle_settings,
        "get_oracle_account",
        Mock(return_value=object()),
    )
    monkeypatch.setattr(oracle_coin_pair_loop.time, "time", lambda: 1_000)
    loop = oracle_coin_pair_loop.OracleCoinPairLoop.__new__(
        oracle_coin_pair_loop.OracleCoinPairLoop
    )
    loop._conf = SimpleNamespace(
        ORACLE_GATHER_SIGNATURE_TIMEOUT=10,
        PRICE_SIGNATURE_MIN_VALIDITY_SECONDS=30,
    )
    loop._coin_pair = COIN_PAIR
    loop._oracle_addr = ORACLE_ADDR
    loop.info = Mock()
    loop.trace = Mock()
    loop._runner = SimpleNamespace(cps=SimpleNamespace(publish=AsyncMock()))
    oracles = [
        SimpleNamespace(addr=ORACLE_ADDR),
        SimpleNamespace(addr=LEGACY_ORACLE_ADDR),
        SimpleNamespace(addr=THIRD_ORACLE_ADDR),
    ]

    result = await loop.publish(oracles, params)

    assert result is False
    loop._runner.cps.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_coin_pair_service_selects_expiring_contract_method():
    service = CoinPairService(object())
    service.coin_pair_execute = AsyncMock(return_value="tx")
    params = price_params(4, 1_800_000_000)

    result = await service._publish(params, [27], [b"r"], [b"s"])

    assert result == "tx"
    assert service.coin_pair_execute.await_args.args[0] == "publishPriceWithExpiration"
    assert service.coin_pair_execute.await_args.args[6] == 1_800_000_000


@pytest.mark.asyncio
async def test_coin_pair_service_keeps_legacy_contract_method():
    service = CoinPairService(object())
    service.coin_pair_execute = AsyncMock(return_value="tx")

    result = await service._publish(price_params(), [27], [b"r"], [b"s"])

    assert result == "tx"
    assert service.coin_pair_execute.await_args.args[0] == "publishPrice"


def test_price_and_task_message_versions_are_independent(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1_000)
    blockchain_info = SimpleNamespace(last_pub_block=123)
    conf = SimpleNamespace(
        PRICE_SIGNATURE_EXPIRATION_SECONDS=300,
        TASK_MESSAGE_VERSION=3,
    )

    price_runner = CoinPairRunner.__new__(CoinPairRunner)
    price_runner._conf = conf
    price_runner._exchange_price = PriceWithTimestamp(10**18, 1_000)
    price_runner.cps = SimpleNamespace(coin_pair=COIN_PAIR)
    price_publication = price_runner.prepare_publish_params(
        blockchain_info, ORACLE_ADDR
    )

    task_runner = TasksRunner.__new__(TasksRunner)
    task_runner._conf = conf
    task_runner._tasks_flags = 7
    task_runner.cps = SimpleNamespace(coin_pair=CoinPair("TASKS"))
    task_publication = task_runner.prepare_publish_params(blockchain_info, ORACLE_ADDR)

    assert price_publication.version == 4
    assert price_publication.expiration == 1_300
    assert task_publication.version == 3


def test_old_contract_abi_is_extended_without_duplicates():
    legacy_abi = [{"name": "publishPrice", "type": "function"}]

    extended = with_expiring_publish_abi(legacy_abi)
    extended_again = with_expiring_publish_abi(extended)

    assert [item["name"] for item in extended].count("publishPriceWithExpiration") == 1
    assert extended_again is extended
