import pytest
from shared.value_objects import FeeProxyValue, Money


def test_money_valid_irr() -> None:
    m = Money(amount=100000)
    assert m.amount == 100000
    assert m.currency == "IRR"


def test_money_rejects_non_irr() -> None:
    with pytest.raises(ValueError, match="only IRR is supported"):
        Money(amount=100, currency="USD")


def test_fee_proxy_rank_and_share() -> None:
    f1 = FeeProxyValue(_raw=100)
    f2 = FeeProxyValue(_raw=200)
    f3 = FeeProxyValue(_raw=300)

    # Rank within peers
    rank = f2.rank_within([f1, f2, f3])
    assert rank == pytest.approx(2 / 3)

    # Share of revenue
    gross = Money(amount=10000)
    share = f2.share_of_revenue(gross)
    assert share == pytest.approx(200 / 10000)

    # Trend vs other
    trend = f2.trend_vs(f1)
    assert trend == pytest.approx(1.0)
