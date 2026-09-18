from enum import Enum, auto


class CoinPairServiceType(Enum):
    """Type of service that can operate on a coin pair contract."""

    COIN_PAIR = auto()
    TASKS_RUNNER = auto()
    LIQUIDATION_ENGINE = auto()
    UNKNOWN = auto()


__all__ = ["CoinPairServiceType"]
