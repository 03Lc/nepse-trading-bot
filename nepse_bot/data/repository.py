"""
High-level market data repository.

Orchestrates: source → clean → store → query.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from nepse_bot.data.cleaning.cleaner import OHLCVCleaner
from nepse_bot.data.ingestion.base import DataSource
from nepse_bot.data.storage.sqlite_store import SQLiteOHLCVStore
from nepse_bot.monitoring import get_logger

log = get_logger("data.repository")


class MarketDataRepository:
    def __init__(
        self,
        db_path: str | Path = "data/storage/nepse_ohlcv.db",
        cleaner: Optional[OHLCVCleaner] = None,
    ):
        self.store = SQLiteOHLCVStore(db_path)
        self.cleaner = cleaner or OHLCVCleaner()

    def ingest(
        self,
        source: DataSource,
        symbol: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> int:
        log.info("Ingesting from %s (symbol=%s)", source.name, symbol)
        raw = source.load(symbol=symbol, start=start, end=end)
        cleaned = self.cleaner.clean(raw, symbol=symbol)
        if cleaned.empty:
            log.warning("No rows after cleaning from %s", source.name)
            return 0
        return self.store.upsert(cleaned)

    def get_bars(
        self,
        symbol: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        return self.store.get(symbol, start=start, end=end)

    def list_symbols(self) -> list[str]:
        return self.store.list_symbols()

    def bar_count(self, symbol: Optional[str] = None) -> int:
        return self.store.count(symbol)
