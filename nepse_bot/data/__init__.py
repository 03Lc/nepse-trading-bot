"""
Data layer: ingestion, cleaning, storage, and repository access.

Phase 2 provides:
- OHLCV schema and validation
- SQLite storage
- CSV historical loader (research)
- Basic cleaning (gaps, outliers, sorting)
- Repository API for backtests / paper trading

Live unofficial scraping is intentionally not the default path.
Prefer licensed data or user-supplied CSV for production research.
"""

from nepse_bot.data.repository import MarketDataRepository
from nepse_bot.data.schema import OHLCVBar, validate_ohlcv_frame

__all__ = [
    "MarketDataRepository",
    "OHLCVBar",
    "validate_ohlcv_frame",
]
