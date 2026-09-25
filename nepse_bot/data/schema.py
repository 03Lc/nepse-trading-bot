"""
OHLCV schema and validation helpers.

All timestamps are stored as timezone-aware UTC in the database;
display/conversion to Asia/Kathmandu happens at the edges.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd

REQUIRED_COLUMNS = ("symbol", "timestamp", "open", "high", "low", "close", "volume")
OPTIONAL_COLUMNS = ("turnover", "trades")


@dataclass(frozen=True)
class OHLCVBar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: Optional[float] = None
    trades: Optional[int] = None

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ValueError(f"high < low for {self.symbol} @ {self.timestamp}")
        if self.open <= 0 or self.close <= 0:
            raise ValueError(f"non-positive price for {self.symbol}")
        if self.volume < 0:
            raise ValueError(f"negative volume for {self.symbol}")


def validate_ohlcv_frame(df: pd.DataFrame, require_symbol: bool = True) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=list(REQUIRED_COLUMNS))

    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]

    rename_map = {
        "date": "timestamp",
        "datetime": "timestamp",
        "time": "timestamp",
        "ticker": "symbol",
        "scrip": "symbol",
        "qty": "volume",
        "vol": "volume",
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
    }
    out = out.rename(columns={k: v for k, v in rename_map.items() if k in out.columns})

    missing = [c for c in REQUIRED_COLUMNS if c not in out.columns]
    if missing:
        if not require_symbol and missing == ["symbol"]:
            pass
        else:
            raise ValueError(f"Missing required columns: {missing}")

    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    for col in ("open", "high", "low", "close", "volume"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    if "turnover" in out.columns:
        out["turnover"] = pd.to_numeric(out["turnover"], errors="coerce")
    if "trades" in out.columns:
        out["trades"] = pd.to_numeric(out["trades"], errors="coerce")

    out = out.dropna(subset=["timestamp", "open", "high", "low", "close", "volume"])
    out = out[out["high"] >= out["low"]]
    out = out[(out["open"] > 0) & (out["close"] > 0) & (out["volume"] >= 0)]

    sort_cols = ["symbol", "timestamp"] if "symbol" in out.columns else ["timestamp"]
    out = out.sort_values(sort_cols).reset_index(drop=True)
    return out
