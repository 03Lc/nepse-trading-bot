"""
CSV historical data loader.

Expected columns (case-insensitive, aliases supported):
  symbol (optional if default_symbol set), timestamp/date, open, high, low, close, volume
  optional: turnover, trades

This is the primary research path for Phase 2. Users supply their own
CSV exports from licensed vendors or cleaned public archives.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from nepse_bot.data.ingestion.base import DataSource
from nepse_bot.data.schema import validate_ohlcv_frame
from nepse_bot.monitoring import get_logger

log = get_logger("data.ingestion.csv")


class CSVHistoricalLoader(DataSource):
    def __init__(
        self,
        path: str | Path,
        default_symbol: Optional[str] = None,
        date_column: Optional[str] = None,
    ):
        self.path = Path(path)
        self.default_symbol = default_symbol.upper() if default_symbol else None
        self.date_column = date_column

    @property
    def name(self) -> str:
        return f"csv:{self.path.name}"

    def load(
        self,
        symbol: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        if not self.path.exists():
            raise FileNotFoundError(f"CSV not found: {self.path}")

        df = pd.read_csv(self.path)
        if self.date_column and self.date_column in df.columns:
            df = df.rename(columns={self.date_column: "timestamp"})

        require_symbol = True
        if "symbol" not in [c.lower() for c in df.columns]:
            if self.default_symbol:
                df["symbol"] = self.default_symbol
            else:
                require_symbol = False

        df = validate_ohlcv_frame(df, require_symbol=require_symbol)

        if self.default_symbol and "symbol" not in df.columns:
            df["symbol"] = self.default_symbol

        if "symbol" in df.columns:
            df["symbol"] = df["symbol"].astype(str).str.upper()

        if symbol:
            if "symbol" not in df.columns:
                raise ValueError("CSV has no symbol column; cannot filter by symbol")
            df = df[df["symbol"] == symbol.upper()]

        if start is not None:
            start_ts = pd.Timestamp(start, tz="UTC")
            df = df[df["timestamp"] >= start_ts]
        if end is not None:
            end_ts = pd.Timestamp(end, tz="UTC")
            df = df[df["timestamp"] <= end_ts]

        log.info(
            "Loaded %d rows from %s (symbol filter=%s)",
            len(df),
            self.path.name,
            symbol,
        )
        return df.reset_index(drop=True)
