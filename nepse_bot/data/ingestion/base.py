"""Abstract data source interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd


class DataSource(ABC):
    """
    All ingestion adapters implement this interface.

    Implementations must return validated OHLCV frames
    (see nepse_bot.data.schema.validate_ohlcv_frame).
    """

    @abstractmethod
    def load(
        self,
        symbol: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """Load OHLCV data. symbol/start/end are optional filters."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable source name for logging."""
        ...
