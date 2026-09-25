"""Tests for transaction cost model."""

import pytest

from nepse_bot.market.costs import TransactionCostModel


def test_commission_slab_small_trade():
    model = TransactionCostModel()
    assert model.commission_rate(40_000) == pytest.approx(0.36)
    assert model.commission_rate(100_000) == pytest.approx(0.33)
    assert model.commission_rate(20_000_000) == pytest.approx(0.24)


def test_buy_cost_no_dp():
    model = TransactionCostModel()
    b = model.estimate(quantity=100, price=500, side="buy")
    assert b.trade_value == 50_000
    assert b.dp_charge == 0.0
    assert b.commission == pytest.approx(50_000 * 0.0036)
    assert b.sebon_fee == pytest.approx(50_000 * 0.00015)
    assert b.total_fees > 0
    assert b.slippage_cost > 0


def test_sell_cost_includes_dp():
    model = TransactionCostModel()
    s = model.estimate(quantity=100, price=500, side="sell")
    assert s.dp_charge == 25.0


def test_round_trip_pct_positive():
    model = TransactionCostModel()
    rt = model.round_trip_cost_pct(100, 500)
    assert rt > 0.5
    assert rt < 2.0


def test_cgt_on_sell():
    model = TransactionCostModel()
    s = model.estimate(
        quantity=100,
        price=500,
        side="sell",
        realized_profit=10_000,
        apply_cgt=True,
        is_long_term=False,
    )
    assert s.cgt == pytest.approx(1_000.0)


def test_invalid_side():
    model = TransactionCostModel()
    with pytest.raises(ValueError):
        model.estimate(10, 100, "hold")


def test_from_config():
    cfg = {
        "commission_slabs": [[50000, 0.36], [None, 0.24]],
        "sebon_fee_pct": 0.015,
        "dp_charge_npr": 25,
        "slippage_pct": 0.1,
    }
    model = TransactionCostModel.from_config(cfg)
    assert model.commission_rate(10_000) == pytest.approx(0.36)
    assert model.commission_rate(1_000_000) == pytest.approx(0.24)
