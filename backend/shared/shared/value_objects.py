from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Money:
    """Integer Iranian Rial. No fractional Rial; no conversion."""

    amount: int
    currency: str = "IRR"

    def __post_init__(self) -> None:
        if self.currency != "IRR":
            raise ValueError("only IRR is supported")


@dataclass(frozen=True)
class FeeProxyValue:
    """Uniformly-scaled fee proxy.

    Deliberately has no ``as_currency()`` / ``to_rial()`` method. Absolute
    currency claims are forbidden; only rank, share-of-revenue, and trend.
    """

    _raw: int

    def rank_within(self, peers: Sequence[FeeProxyValue]) -> float:
        if not peers:
            return 0.0
        below_or_equal = sum(1 for peer in peers if peer._raw <= self._raw)
        return below_or_equal / len(peers)

    def share_of_revenue(self, gross: Money) -> float:
        if gross.amount == 0:
            return 0.0
        return self._raw / gross.amount

    def trend_vs(self, other: FeeProxyValue) -> float:
        if other._raw == 0:
            return 0.0
        return (self._raw - other._raw) / other._raw
