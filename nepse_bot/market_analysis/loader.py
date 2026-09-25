"""Load benchmark OHLCV CSV into BenchmarkStore."""

from __future__ import annotations

from pathlib import Path

from nepse_bot.data.ingestion.csv_loader import CSVHistoricalLoader
from nepse_bot.market_analysis.benchmarks import BenchmarkStore
from nepse_bot.monitoring import get_logger

log = get_logger("market_analysis.loader")


def load_benchmark_csv(
    path: str | Path,
    store: BenchmarkStore,
    *,
    benchmark_id: str,
) -> int:
    path = Path(path)
    loader = CSVHistoricalLoader(path, default_symbol=benchmark_id.upper())
    df = loader.load(symbol=benchmark_id.upper())
    if df.empty:
        log.warning("No rows loaded from %s", path)
        return 0
    return store.upsert_bars(df, benchmark_id.upper())
