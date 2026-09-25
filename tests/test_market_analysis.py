"""Phase 5 — market / sector analysis tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nepse_bot.fundamentals.models import Sector
from nepse_bot.indicators.types import MetricStatus
from nepse_bot.market_analysis.benchmarks import BenchmarkStore, NEPSE_INDEX
from nepse_bot.market_analysis.breadth import compute_breadth
from nepse_bot.market_analysis.engine import MarketAnalysisEngine
from nepse_bot.market_analysis.loader import load_benchmark_csv
from nepse_bot.market_analysis.relative import (
    period_return,
    relative_strength,
    realized_volatility,
    simple_trend_label,
)


def _ohlcv(n: int = 100, seed: int = 1, start: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")
    rets = rng.normal(0.0005, 0.015, size=n)
    close = start * np.exp(np.cumsum(rets))
    open_ = close * (1 + rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.01, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.01, n))
    volume = rng.integers(1000, 50000, size=n).astype(float)
    return pd.DataFrame(
        {
            "symbol": "T",
            "timestamp": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def test_period_return_and_rs():
    s = pd.Series([100.0, 110.0, 121.0])
    assert period_return(s, 1) == pytest.approx(10.0)
    assert relative_strength(s, pd.Series([100.0, 105.0, 110.25]), 2) is not None


def test_volatility_and_trend():
    df = _ohlcv(80)
    v = realized_volatility(df["close"], 20)
    assert v is not None and v > 0
    label = simple_trend_label(df["close"])
    assert label in {
        "uptrend", "downtrend", "bullish_bias", "bearish_bias", "sideways", "unknown",
    }


def test_breadth():
    frames = {"A": _ohlcv(60, seed=1), "B": _ohlcv(60, seed=2), "C": _ohlcv(60, seed=3)}
    b = compute_breadth(frames)
    assert b.symbols_counted == 3
    assert b.advancers + b.decliners + b.unchanged == 3


def test_engine_without_benchmarks(tmp_path: Path):
    store = BenchmarkStore(db_path=tmp_path / "b.db")
    eng = MarketAnalysisEngine(benchmarks=store)
    stock = _ohlcv(80)
    snap = eng.analyze_symbol("NABIL", stock, sector=Sector.COMMERCIAL_BANK)
    assert snap.symbol == "NABIL"
    assert any(r.status == MetricStatus.UNAVAILABLE for r in snap.relative_vs_nepse)


def test_engine_with_nepse(tmp_path: Path):
    store = BenchmarkStore(db_path=tmp_path / "b.db")
    nepse = _ohlcv(100, seed=10, start=2000)
    nepse["symbol"] = NEPSE_INDEX
    store.upsert_bars(nepse, NEPSE_INDEX)
    bank = _ohlcv(100, seed=11, start=1500)
    bank["symbol"] = "SECTOR_BANKING"
    store.upsert_bars(bank, "SECTOR_BANKING")
    eng = MarketAnalysisEngine(benchmarks=store)
    stock = _ohlcv(100, seed=12, start=500)
    snap = eng.analyze_symbol(
        "NABIL",
        stock,
        sector=Sector.COMMERCIAL_BANK,
        universe_frames={"NABIL": stock, "X": _ohlcv(100, seed=13)},
    )
    assert snap.metrics.get("nepse_trend") is not None
    assert any(r.status == MetricStatus.OK for r in snap.relative_vs_nepse)
    assert snap.breadth is not None
    assert snap.breadth.symbols_counted >= 1


def test_load_benchmark_csv(tmp_path: Path):
    sample = Path(__file__).resolve().parents[1] / "data" / "samples" / "NEPSE_index_sample.csv"
    if not sample.exists():
        pytest.skip("sample missing")
    store = BenchmarkStore(db_path=tmp_path / "b.db")
    n = load_benchmark_csv(sample, store, benchmark_id="NEPSE")
    assert n > 0
    assert not store.get_series("NEPSE").empty
