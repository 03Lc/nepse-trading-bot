"""
Price levels, gaps, and simple trend structure.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def rolling_high_low(
    high: pd.Series,
    low: pd.Series,
    window: int,
) -> tuple[pd.Series, pd.Series]:
    """Rolling highest high / lowest low over `window` bars."""
    hh = high.astype(float).rolling(window, min_periods=1).max()
    ll = low.astype(float).rolling(window, min_periods=1).min()
    return hh, ll


def distance_from_extreme(
    close: float,
    extreme: float,
) -> Optional[float]:
    """Percent distance from extreme: (close - extreme) / extreme * 100."""
    if extreme is None or extreme == 0 or np.isnan(extreme):
        return None
    return 100.0 * (close - extreme) / extreme


def simple_support_resistance(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    lookback: int = 20,
) -> dict[str, Optional[float]]:
    """
    Lightweight S/R from recent swing extremes (not full pivot detection).

    resistance ≈ max high over lookback
    support    ≈ min low over lookback
    """
    if len(close) < 2:
        return {"support": None, "resistance": None}
    lb = min(lookback, len(close))
    h = high.astype(float).iloc[-lb:]
    l = low.astype(float).iloc[-lb:]
    return {
        "support": float(l.min()),
        "resistance": float(h.max()),
    }


def detect_gaps(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    min_gap_pct: float = 0.5,
) -> pd.DataFrame:
    """
    Detect overnight gaps on daily (or sequential) bars.

    gap_pct > 0 → gap up; < 0 → gap down.
    """
    o = open_.astype(float)
    c = close.astype(float)
    prev_c = c.shift(1)
    gap_pct = 100.0 * (o - prev_c) / prev_c.replace(0, np.nan)
    gap_up = gap_pct >= min_gap_pct
    gap_down = gap_pct <= -min_gap_pct
    filled = pd.Series(False, index=o.index)
    # simple fill: gap up filled if low <= prev close; gap down if high >= prev close
    filled = np.where(gap_up, low.astype(float) <= prev_c, filled)
    filled = np.where(gap_down, high.astype(float) >= prev_c, filled)
    return pd.DataFrame(
        {
            "gap_pct": gap_pct,
            "gap_up": gap_up.fillna(False),
            "gap_down": gap_down.fillna(False),
            "gap_filled": pd.Series(filled, index=o.index).fillna(False),
        },
        index=o.index,
    )


def trend_structure(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    ema_fast: pd.Series,
    ema_slow: pd.Series,
    lookback: int = 5,
) -> dict[str, object]:
    """
    Coarse trend label from EMA relationship + recent HH/HL or LH/LL.

    Returns dict with keys: label, higher_highs, higher_lows, lower_highs, lower_lows.
    """
    c = close.astype(float)
    h = high.astype(float)
    l = low.astype(float)
    if len(c) < lookback + 1:
        return {
            "label": "unknown",
            "higher_highs": False,
            "higher_lows": False,
            "lower_highs": False,
            "lower_lows": False,
            "above_ema_fast": None,
            "above_ema_slow": None,
        }

    recent_h = h.iloc[-lookback:]
    recent_l = l.iloc[-lookback:]
    mid = lookback // 2
    first_h, second_h = recent_h.iloc[:mid].max(), recent_h.iloc[mid:].max()
    first_l, second_l = recent_l.iloc[:mid].min(), recent_l.iloc[mid:].min()

    hh = second_h > first_h
    hl = second_l > first_l
    lh = second_h < first_h
    ll = second_l < first_l

    last_c = float(c.iloc[-1])
    ef = float(ema_fast.iloc[-1]) if not pd.isna(ema_fast.iloc[-1]) else None
    es = float(ema_slow.iloc[-1]) if not pd.isna(ema_slow.iloc[-1]) else None
    above_fast = (last_c > ef) if ef is not None else None
    above_slow = (last_c > es) if es is not None else None

    if above_fast and above_slow and hh and hl:
        label = "uptrend"
    elif above_fast is False and above_slow is False and lh and ll:
        label = "downtrend"
    elif ef is not None and es is not None and ef > es:
        label = "bullish_bias"
    elif ef is not None and es is not None and ef < es:
        label = "bearish_bias"
    else:
        label = "sideways"

    return {
        "label": label,
        "higher_highs": bool(hh),
        "higher_lows": bool(hl),
        "lower_highs": bool(lh),
        "lower_lows": bool(ll),
        "above_ema_fast": above_fast,
        "above_ema_slow": above_slow,
    }
