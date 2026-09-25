"""
Core technical indicator series (vectorized).

Functions return pandas Series aligned to the input index.
Warm-up / NaN rows are left as NaN; callers use last valid values
and MetricResult status for presentation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _series(x: pd.Series | np.ndarray | list) -> pd.Series:
    if isinstance(x, pd.Series):
        return x.astype(float)
    return pd.Series(x, dtype=float)


def sma(close: pd.Series, period: int) -> pd.Series:
    if period < 1:
        raise ValueError("period must be >= 1")
    return _series(close).rolling(window=period, min_periods=period).mean()


def ema(close: pd.Series, period: int) -> pd.Series:
    if period < 1:
        raise ValueError("period must be >= 1")
    return _series(close).ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder-style RSI via EWM of gains/losses."""
    c = _series(close)
    delta = c.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    # when avg_loss == 0 and avg_gain > 0 → RSI 100
    out = out.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    out = out.where(~((avg_loss == 0) & (avg_gain == 0)), 50.0)
    return out


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (macd_line, signal_line, histogram)."""
    c = _series(close)
    ema_fast = ema(c, fast)
    ema_slow = ema(c, slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    h = _series(high)
    l = _series(low)
    c = _series(close)
    prev_c = c.shift(1)
    tr = pd.concat(
        [
            (h - l).abs(),
            (h - prev_c).abs(),
            (l - prev_c).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr = true_range(high, low, close)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Returns (adx, plus_di, minus_di).
    Wilder smoothing style.
    """
    h = _series(high)
    l = _series(low)
    c = _series(close)

    up = h.diff()
    down = -l.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    plus_dm = pd.Series(plus_dm, index=h.index)
    minus_dm = pd.Series(minus_dm, index=h.index)

    tr = true_range(h, l, c)
    atr_s = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    plus_dm_s = plus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    minus_dm_s = minus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    plus_di = 100.0 * (plus_dm_s / atr_s.replace(0, np.nan))
    minus_di = 100.0 * (minus_dm_s / atr_s.replace(0, np.nan))
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_s = dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return adx_s, plus_di, minus_di


def stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    d_period: int = 3,
) -> tuple[pd.Series, pd.Series]:
    """Returns (%K, %D)."""
    h = _series(high)
    l = _series(low)
    c = _series(close)
    lowest = l.rolling(k_period, min_periods=k_period).min()
    highest = h.rolling(k_period, min_periods=k_period).max()
    denom = (highest - lowest).replace(0, np.nan)
    k = 100.0 * (c - lowest) / denom
    d = k.rolling(d_period, min_periods=d_period).mean()
    return k, d


def roc(close: pd.Series, period: int = 12) -> pd.Series:
    c = _series(close)
    return 100.0 * (c - c.shift(period)) / c.shift(period).replace(0, np.nan)


def momentum(close: pd.Series, period: int = 10) -> pd.Series:
    c = _series(close)
    return c - c.shift(period)


def vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
) -> pd.Series:
    """
    Session-style cumulative VWAP on the provided frame.
    For daily bars this is cumulative from the start of the series
    (caller may reset per session when intraday bars exist).
    """
    h = _series(high)
    l = _series(low)
    c = _series(close)
    v = _series(volume).clip(lower=0)
    typical = (h + l + c) / 3.0
    cum_tp_vol = (typical * v).cumsum()
    cum_vol = v.cumsum().replace(0, np.nan)
    return cum_tp_vol / cum_vol


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    c = _series(close)
    v = _series(volume).clip(lower=0)
    direction = np.sign(c.diff()).fillna(0.0)
    return (direction * v).cumsum()


def accumulation_distribution(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
) -> pd.Series:
    h = _series(high)
    l = _series(low)
    c = _series(close)
    v = _series(volume).clip(lower=0)
    hl = (h - l).replace(0, np.nan)
    mfm = ((c - l) - (h - c)) / hl
    mfm = mfm.fillna(0.0)
    mfv = mfm * v
    return mfv.cumsum()


def relative_volume(volume: pd.Series, period: int = 20) -> pd.Series:
    v = _series(volume)
    avg = v.rolling(period, min_periods=period).mean().replace(0, np.nan)
    return v / avg
