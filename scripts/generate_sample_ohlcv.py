#!/usr/bin/env python3
"""Generate synthetic daily OHLCV CSV for testing (not real market data)."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def generate(symbol: str, days: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-01", periods=days, tz="UTC")
    rets = rng.normal(0.0005, 0.015, size=days)
    close = 500 * np.cumprod(1 + rets)
    open_ = close * (1 + rng.normal(0, 0.003, size=days))
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.01, size=days))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.01, size=days))
    volume = rng.integers(1_000, 50_000, size=days).astype(float)
    return pd.DataFrame({
        "symbol": symbol.upper(),
        "timestamp": dates,
        "open": np.round(open_, 2),
        "high": np.round(high, 2),
        "low": np.round(low, 2),
        "close": np.round(close, 2),
        "volume": volume,
    })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="NABIL")
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--out", default="data/samples/NABIL_sample.csv")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df = generate(args.symbol, args.days, args.seed)
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} rows to {out}")


if __name__ == "__main__":
    main()
