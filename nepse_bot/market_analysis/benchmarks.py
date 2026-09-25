"""
Benchmark series storage (NEPSE index, sector indices).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from nepse_bot.data.storage.sqlite_store import SQLiteOHLCVStore
from nepse_bot.monitoring import get_logger

log = get_logger("market_analysis.benchmarks")

NEPSE_INDEX = "NEPSE"
SECTOR_BENCHMARK_IDS = {
    "commercial_bank": "SECTOR_BANKING",
    "development_bank": "SECTOR_DEVBANK",
    "finance": "SECTOR_FINANCE",
    "microfinance": "SECTOR_MICROFINANCE",
    "life_insurance": "SECTOR_LIFE_INS",
    "non_life_insurance": "SECTOR_NONLIFE_INS",
    "hydropower": "SECTOR_HYDRO",
    "manufacturing": "SECTOR_MANUFACTURING",
    "hotels_tourism": "SECTOR_HOTELS",
    "trading": "SECTOR_TRADING",
    "investment": "SECTOR_INVESTMENT",
    "others": "SECTOR_OTHERS",
}


@dataclass
class BenchmarkSeries:
    benchmark_id: str
    bars: pd.DataFrame

    @property
    def empty(self) -> bool:
        return self.bars is None or self.bars.empty


class BenchmarkStore:
    def __init__(self, db_path: str | Path = "data/storage/nepse_benchmarks.db"):
        self.store = SQLiteOHLCVStore(db_path)

    def upsert_bars(self, df: pd.DataFrame, benchmark_id: str) -> int:
        work = df.copy()
        work.columns = [str(c).strip().lower() for c in work.columns]
        work["symbol"] = benchmark_id.upper()
        n = self.store.upsert(work)
        log.info("Upserted %s bars for benchmark %s", n, benchmark_id)
        return n

    def get_series(
        self,
        benchmark_id: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> BenchmarkSeries:
        bars = self.store.get(benchmark_id.upper(), start=start, end=end)
        return BenchmarkSeries(benchmark_id=benchmark_id.upper(), bars=bars)

    def list_benchmarks(self) -> list[str]:
        return self.store.list_symbols()


def sector_to_benchmark_id(sector_value: str) -> Optional[str]:
    return SECTOR_BENCHMARK_IDS.get(sector_value)
