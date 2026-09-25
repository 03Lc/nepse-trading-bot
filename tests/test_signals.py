"""Phase 6 — signal / rule engine tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nepse_bot.indicators.engine import TechnicalEngine
from nepse_bot.signals.engine import SignalEngine
from nepse_bot.signals.rules import RuleConfig
from nepse_bot.signals.types import SignalState


def _ohlcv(n: int = 250, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")
    rets = rng.normal(0.001, 0.012, size=n)
    close = 400 * np.exp(np.cumsum(rets))
    open_ = close * (1 + rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.008, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.008, n))
    volume = rng.integers(5000, 80000, size=n).astype(float)
    volume[-1] = float(volume[-20:].mean() * 2.0)
    return pd.DataFrame({
        "symbol": "NABIL", "timestamp": dates,
        "open": open_, "high": high, "low": low, "close": close, "volume": volume,
    })


def test_signal_report_structure():
    tech = TechnicalEngine().compute(_ohlcv(), symbol="NABIL")
    eng = SignalEngine(RuleConfig(buy_setup_min_passed=3, buy_setup_max_failed=5))
    report = eng.evaluate("NABIL", technical=tech)
    assert report.symbol == "NABIL"
    assert isinstance(report.state, SignalState)
    assert report.passed + report.failed + report.unknown == len(report.conditions)
    assert len(report.summary_lines()) > 5


def test_no_signal_without_data():
    eng = SignalEngine()
    report = eng.evaluate("EMPTY")
    assert report.state in (SignalState.NO_SIGNAL, SignalState.WATCH, SignalState.HOLD)
    assert report.unknown >= 1
    assert any("unknown" in w.lower() or "missing" in w.lower() for w in report.warnings)


def test_breakdown_leans_sell():
    tech = TechnicalEngine().compute(_ohlcv(n=100, seed=1), symbol="X")
    tech.flags["breakdown"] = True
    report = SignalEngine().evaluate("X", technical=tech)
    assert report.state == SignalState.SELL_EXIT_SETUP


def test_config_affects_thresholds():
    tech = TechnicalEngine().compute(_ohlcv(), symbol="NABIL")
    strict = SignalEngine(RuleConfig(buy_setup_min_passed=50, watch_min_passed=50))
    loose = SignalEngine(RuleConfig(buy_setup_min_passed=1, buy_setup_max_failed=20, watch_min_passed=1))
    assert strict.evaluate("NABIL", technical=tech).state != SignalState.BUY_SETUP
    assert loose.evaluate("NABIL", technical=tech).passed >= 1


def test_conditions_have_marks():
    tech = TechnicalEngine().compute(_ohlcv(), symbol="NABIL")
    report = SignalEngine().evaluate("NABIL", technical=tech)
    assert {c.mark for c in report.conditions} & {"✓", "✗", "?"}
