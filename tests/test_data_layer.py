"""Phase 2 — data layer tests."""

from pathlib import Path

import pandas as pd
import pytest

from nepse_bot.data.cleaning.cleaner import OHLCVCleaner
from nepse_bot.data.ingestion.csv_loader import CSVHistoricalLoader
from nepse_bot.data.repository import MarketDataRepository
from nepse_bot.data.schema import validate_ohlcv_frame
from nepse_bot.data.storage.sqlite_store import SQLiteOHLCVStore


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    path = tmp_path / "sample.csv"
    df = pd.DataFrame({
        "symbol": ["NABIL"] * 5,
        "timestamp": pd.date_range("2025-01-02", periods=5, freq="B", tz="UTC"),
        "open": [100.0, 101.0, 102.0, 103.0, 104.0],
        "high": [102.0, 103.0, 104.0, 105.0, 106.0],
        "low": [99.0, 100.0, 101.0, 102.0, 103.0],
        "close": [101.0, 102.0, 103.0, 104.0, 105.0],
        "volume": [1000, 1100, 1200, 1300, 1400],
    })
    df.to_csv(path, index=False)
    return path


def test_validate_ohlcv_frame(sample_csv):
    df = pd.read_csv(sample_csv)
    clean = validate_ohlcv_frame(df)
    assert len(clean) == 5


def test_validate_rejects_high_lt_low():
    df = pd.DataFrame({
        "symbol": ["X"], "timestamp": ["2025-01-02"],
        "open": [10], "high": [9], "low": [11], "close": [10], "volume": [100],
    })
    assert validate_ohlcv_frame(df).empty


def test_csv_loader(sample_csv):
    df = CSVHistoricalLoader(sample_csv).load(symbol="NABIL")
    assert len(df) == 5
    assert df["symbol"].iloc[0] == "NABIL"


def test_cleaner_drops_duplicates():
    df = pd.DataFrame({
        "symbol": ["A", "A"],
        "timestamp": pd.to_datetime(["2025-01-02", "2025-01-02"], utc=True),
        "open": [1.0, 1.1], "high": [1.2, 1.3], "low": [0.9, 1.0],
        "close": [1.1, 1.2], "volume": [10, 20],
    })
    out = OHLCVCleaner().clean(df)
    assert len(out) == 1
    assert out["close"].iloc[0] == 1.2


def test_sqlite_upsert_and_get(tmp_path, sample_csv):
    store = SQLiteOHLCVStore(tmp_path / "test.db")
    df = CSVHistoricalLoader(sample_csv).load()
    assert store.upsert(df) == 5
    assert store.count("NABIL") == 5
    assert len(store.get("NABIL")) == 5


def test_repository_ingest(tmp_path, sample_csv):
    repo = MarketDataRepository(db_path=tmp_path / "repo.db")
    n = repo.ingest(CSVHistoricalLoader(sample_csv))
    assert n == 5
    assert "NABIL" in repo.list_symbols()
    bars = repo.get_bars("NABIL")
    assert len(bars) == 5
    assert bars["timestamp"].is_monotonic_increasing
