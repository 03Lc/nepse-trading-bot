"""DataProvider interface (Phase 13). Official realtime plugs in later."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import pandas as pd


class FeedStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass
class TickEvent:
    symbol: str
    price: float
    volume: float
    data_timestamp: datetime
    receive_timestamp: datetime
    source: str
    sequence: Optional[int] = None

    @property
    def data_age_sec(self) -> float:
        return max(0.0, (datetime.now(timezone.utc) - self.data_timestamp).total_seconds())


class DataProvider(ABC):
    name: str = "base"

    @abstractmethod
    def get_ohlcv(self, symbol: str, start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
        ...

    @abstractmethod
    def list_symbols(self) -> list[str]:
        ...

    def status(self) -> FeedStatus:
        return FeedStatus.UNKNOWN

    def is_realtime(self) -> bool:
        return False


class HistoricalDataProvider(DataProvider):
    name = "historical"

    def __init__(self, repository):
        self.repository = repository

    def get_ohlcv(self, symbol: str, start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
        return self.repository.get_bars(symbol, start=start, end=end)

    def list_symbols(self) -> list[str]:
        return self.repository.list_symbols()

    def status(self) -> FeedStatus:
        return FeedStatus.CONNECTED


class MockDataProvider(DataProvider):
    name = "mock"

    def __init__(self, frames: Optional[dict[str, pd.DataFrame]] = None):
        self.frames = frames or {}

    def get_ohlcv(self, symbol: str, start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
        df = self.frames.get(symbol.upper(), pd.DataFrame())
        return df.copy() if df is not None else pd.DataFrame()

    def list_symbols(self) -> list[str]:
        return sorted(self.frames.keys())

    def status(self) -> FeedStatus:
        return FeedStatus.CONNECTED


class OfficialRealtimeDataProvider(DataProvider):
    name = "official_realtime"

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "No officially supported retail real-time NEPSE feed is wired. "
            "Do not bypass authentication or use unauthorized APIs."
        )

    def get_ohlcv(self, symbol: str, start=None, end=None) -> pd.DataFrame:
        raise NotImplementedError

    def list_symbols(self) -> list[str]:
        raise NotImplementedError

    def is_realtime(self) -> bool:
        return True
