"""Market breadth from a universe of OHLCV frames."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class BreadthSnapshot:
    symbols_counted: int
    advancers: int
    decliners: int
    unchanged: int
    advance_decline_ratio: Optional[float]
    pct_above_sma20: Optional[float]
    pct_above_sma50: Optional[float]
    notes: list[str]


def compute_breadth(
    frames: dict[str, pd.DataFrame],
    *,
    change_lookback: int = 1,
) -> BreadthSnapshot:
    notes: list[str] = []
    if not frames:
        return BreadthSnapshot(
            symbols_counted=0,
            advancers=0,
            decliners=0,
            unchanged=0,
            advance_decline_ratio=None,
            pct_above_sma20=None,
            pct_above_sma50=None,
            notes=["no symbols provided"],
        )

    adv = dec = unc = 0
    above20 = above50 = 0
    counted20 = counted50 = 0
    used = 0

    for sym, df in frames.items():
        if df is None or df.empty or "close" not in df.columns:
            continue
        c = df["close"].astype(float).dropna()
        if len(c) <= change_lookback:
            continue
        used += 1
        chg = float(c.iloc[-1] - c.iloc[-(change_lookback + 1)])
        if chg > 0:
            adv += 1
        elif chg < 0:
            dec += 1
        else:
            unc += 1

        if len(c) >= 20:
            counted20 += 1
            sma20 = c.rolling(20).mean().iloc[-1]
            if not pd.isna(sma20) and c.iloc[-1] > sma20:
                above20 += 1
        if len(c) >= 50:
            counted50 += 1
            sma50 = c.rolling(50).mean().iloc[-1]
            if not pd.isna(sma50) and c.iloc[-1] > sma50:
                above50 += 1

    if used == 0:
        notes.append("insufficient bars on all symbols")

    adr = (adv / dec) if dec > 0 else (None if adv == 0 else None)
    if dec == 0 and adv > 0:
        notes.append("no decliners — A/D ratio undefined")

    pct20 = (100.0 * above20 / counted20) if counted20 else None
    pct50 = (100.0 * above50 / counted50) if counted50 else None
    if counted20 == 0:
        notes.append("% above SMA20 unavailable")
    if counted50 == 0:
        notes.append("% above SMA50 unavailable")

    return BreadthSnapshot(
        symbols_counted=used,
        advancers=adv,
        decliners=dec,
        unchanged=unc,
        advance_decline_ratio=adr,
        pct_above_sma20=pct20,
        pct_above_sma50=pct50,
        notes=notes,
    )
