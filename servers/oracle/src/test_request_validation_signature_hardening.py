import pytest
from types import SimpleNamespace

from common.services.oracle_dao import CoinPair, PriceWithTimestamp
from oracle.src.request_validation import (
    InvalidSignature,
    PriceRequestValidation,
    TaskRequestValidation,
)


class DummyOracleTurn:
    pass


def make_validator(validation_cls):
    params = SimpleNamespace(
        oracle_addr="0x1234567890abcdef1234567890abcdef12345678",
        coin_pair=CoinPair("BTCUSD"),
    )

    if validation_cls is PriceRequestValidation:
        return validation_cls(
            0,
            params,
            DummyOracleTurn(),
            PriceWithTimestamp(1, 1),
            object(),
        )

    return validation_cls(params, DummyOracleTurn(), False, 0, 0, object())


@pytest.mark.parametrize("validation_cls", [PriceRequestValidation, TaskRequestValidation])
def test_validate_signature_rejects_malformed_hex(validation_cls):
    validator = make_validator(validation_cls)

    with pytest.raises(InvalidSignature):
        validator.validate_signature("message", "not-a-valid-hex-signature")
