"""Phase 3 — technical indicators unit tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nepse_bot.indicators.core import (
    adx,
    atr,
    ema,
    macd,
    momentum,
    obv,
    relative_volume,
    roc,
    rsi,
    sma,
    stochastic,
    vwap,
)
from nepse_bot.indicators.engine import TechnicalEngine
from nepse_bot.indicators.types import MetricStatus


def _synthetic_ohlcv(n: int = 300, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")
    rets = rng.normal(0.0005, 0.015, size=n)
    close = 500 * np.exp(np.cumsum(rets))
    open_ = close * (1 + rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.01, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.01, n))
    volume = rng.integers(1000, 50000, size=n).astype(float)
    return pd.DataFrame(
        {
            "symbol": "TEST",
            "timestamp": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def test_sma_length_and_warmup():
    s = pd.Series(range(1, 11), dtype=float)
    out = sma(s, 5)
    assert out.isna().sum() == 4
    assert abs(out.iloc[-1] - 8.0) < 1e-9


def test_ema_responds():
    s = pd.Series([1.0] * 10 + [10.0] * 10)
    out = ema(s, 5)
    assert out.iloc[-1] > out.iloc[10]


def test_rsi_bounds():
    df = _synthetic_ohlcv(100)
    r = rsi(df["close"], 14)
    valid = r.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_macd_shapes():
    df = _synthetic_ohlcv(100)
    m, sig, hist = macd(df["close"])
    assert len(m) == len(df)
    assert len(sig) == len(df)
    assert len(hist) == len(df)


def test_atr_positive():
    df = _synthetic_ohlcv(50)
    a = atr(df["high"], df["low"], df["close"], 14)
    valid = a.dropna()
    assert (valid > 0).all()


def test_adx_range():
    df = _synthetic_ohlcv(80)
    a, pdi, mdi = adx(df["high"], df["low"], df["close"], 14)
    valid = a.dropna()
    assert len(valid) > 0
    assert (valid >= 0).all()


def test_stochastic_bounds():
    df = _synthetic_ohlcv(50)
    k, d = stochastic(df["high"], df["low"], df["close"])
    kv = k.dropna()
    assert (kv >= -1e-6).all() and (kv <= 100 + 1e-6).all()


def test_roc_momentum():
    s = pd.Series([100.0, 110.0, 121.0])
    r = roc(s, 1)
    assert abs(r.iloc[1] - 10.0) < 1e-9
    m = momentum(s, 1)
    assert abs(m.iloc[1] - 10.0) < 1e-9


def test_vwap_and_obv():
    df = _synthetic_ohlcv(30)
    w = vwap(df["high"], df["low"], df["close"], df["volume"])
    assert w.notna().all()
    o = obv(df["close"], df["volume"])
    assert len(o) == 30


def test_relative_volume():
    # Rolling window of 20 on series of 21: last window = 19×10 + 30 → mean 11
    v = pd.Series([10.0] * 20 + [30.0])
    r = relative_volume(v, 20)
    assert abs(r.iloc[-1] - (30.0 / 11.0)) < 1e-9


def test_engine_insufficient_data():
    df = _synthetic_ohlcv(10)
    eng = TechnicalEngine()
    snap = eng.compute(df, symbol="TEST")
    assert snap.bars_used == 10
    assert snap.metrics["sma_200"].status == MetricStatus.INSUFFICIENT_DATA
    assert snap.metrics["rsi"].status in (
        MetricStatus.OK,
        MetricStatus.INSUFFICIENT_DATA,
    )


def test_engine_full_snapshot():
    df = _synthetic_ohlcv(300)
    eng = TechnicalEngine()
    snap = eng.compute(df, symbol="TEST")
    assert snap.symbol == "TEST"
    assert snap.price is not None
    assert snap.metrics["sma_20"].status == MetricStatus.OK
    assert snap.metrics["sma_50"].status == MetricStatus.OK
    assert snap.metrics["ema_200"].status == MetricStatus.OK
    assert snap.metrics["rsi"].status == MetricStatus.OK
    assert 0 <= snap.metrics["rsi"].value <= 100
    assert snap.metrics["macd"].status == MetricStatus.OK
    assert snap.metrics["atr"].status == MetricStatus.OK
    assert snap.metrics["adx"].status == MetricStatus.OK
    assert snap.metrics["relative_volume"].status == MetricStatus.OK
    assert snap.metrics["high_52w"].status == MetricStatus.OK
    assert snap.metrics["support"].status == MetricStatus.OK
    assert "label" in snap.structure
    d = snap.as_dict()
    assert "metrics" in d
    lines = snap.summary_lines()
    assert any("TEST" in x for x in lines)


def test_engine_empty():
    eng = TechnicalEngine()
    snap = eng.compute(pd.DataFrame(), symbol="EMPTY")
    assert snap.bars_used == 0
    assert snap.price is None


def test_metric_never_invents():
    eng = TechnicalEngine()
    snap = eng.compute(_synthetic_ohlcv(5), symbol="X")
    for name, m in snap.metrics.items():
        if m.status != MetricStatus.OK:
            assert m.value is None, f"{name} should not invent a value"
