"""Relative performance and return helpers."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def period_return(close: pd.Series, lookback: int) -> Optional[float]:
    c = close.astype(float).dropna()
    if len(c) <= lookback:
        return None
    start = float(c.iloc[-(lookback + 1)])
    end = float(c.iloc[-1])
    if start == 0:
        return None
    return 100.0 * (end - start) / start


def relative_strength(
    stock_close: pd.Series,
    bench_close: pd.Series,
    lookback: int,
) -> Optional[float]:
    s = period_return(stock_close, lookback)
    b = period_return(bench_close, lookback)
    if s is None or b is None:
        return None
    return s - b


def align_closes(
    stock: pd.DataFrame,
    bench: pd.DataFrame,
) -> tuple[pd.Series, pd.Series]:
    s = stock.copy()
    b = bench.copy()
    s.columns = [str(c).strip().lower() for c in s.columns]
    b.columns = [str(c).strip().lower() for c in b.columns]
    if "timestamp" not in s.columns or "timestamp" not in b.columns:
        raise ValueError("both frames need timestamp")
    s["timestamp"] = pd.to_datetime(s["timestamp"], utc=True)
    b["timestamp"] = pd.to_datetime(b["timestamp"], utc=True)
    s = s.set_index("timestamp").sort_index()
    b = b.set_index("timestamp").sort_index()
    joined = s[["close"]].join(b[["close"]], how="inner", lsuffix="_s", rsuffix="_b")
    if joined.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    return joined["close_s"].astype(float), joined["close_b"].astype(float)


def realized_volatility(close: pd.Series, lookback: int = 20) -> Optional[float]:
    c = close.astype(float).dropna()
    if len(c) < lookback + 1:
        return None
    rets = np.log(c / c.shift(1)).iloc[-lookback:]
    if rets.isna().all():
        return None
    return float(rets.std() * np.sqrt(252) * 100.0)


def simple_trend_label(close: pd.Series, fast: int = 20, slow: int = 50) -> str:
    c = close.astype(float).dropna()
    if len(c) < slow:
        return "unknown"
    sma_f = c.rolling(fast).mean().iloc[-1]
    sma_s = c.rolling(slow).mean().iloc[-1]
    last = c.iloc[-1]
    if pd.isna(sma_f) or pd.isna(sma_s):
        return "unknown"
    if last > sma_f > sma_s:
        return "uptrend"
    if last < sma_f < sma_s:
        return "downtrend"
    if sma_f > sma_s:
        return "bullish_bias"
    if sma_f < sma_s:
        return "bearish_bias"
    return "sideways"
