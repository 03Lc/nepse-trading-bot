"""
OHLCV cleaning utilities.

Operations (all optional via flags):
- Drop duplicate (symbol, timestamp)
- Sort chronologically
- Drop rows with zero volume (optional)
- Clip extreme single-day returns (outlier filter)
- Forward-fill small gaps is intentionally NOT done by default
  (avoids inventing prices; backtests should respect missing bars)
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from nepse_bot.data.schema import validate_ohlcv_frame
from nepse_bot.monitoring import get_logger

log = get_logger("data.cleaning")


class OHLCVCleaner:
    def __init__(
        self,
        max_abs_return: float = 0.25,
        drop_zero_volume: bool = False,
        drop_duplicates: bool = True,
    ):
        self.max_abs_return = max_abs_return
        self.drop_zero_volume = drop_zero_volume
        self.drop_duplicates = drop_duplicates

    def clean(self, df: pd.DataFrame, symbol: Optional[str] = None) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        out = validate_ohlcv_frame(df, require_symbol="symbol" in df.columns)

        if symbol and "symbol" in out.columns:
            out = out[out["symbol"] == symbol.upper()]

        n0 = len(out)

        if self.drop_duplicates and not out.empty:
            subset = ["symbol", "timestamp"] if "symbol" in out.columns else ["timestamp"]
            out = out.drop_duplicates(subset=subset, keep="last")

        if self.drop_zero_volume and not out.empty:
            out = out[out["volume"] > 0]

        if self.max_abs_return and self.max_abs_return > 0 and not out.empty:
            out = self._filter_return_outliers(out)

        n1 = len(out)
        if n0 != n1:
            log.info("Cleaned OHLCV: %d -> %d rows (dropped %d)", n0, n1, n0 - n1)

        return out.reset_index(drop=True)

    def _filter_return_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        parts = []
        if "symbol" in df.columns:
            groups = df.groupby("symbol", sort=False)
        else:
            groups = [(None, df)]

        for _, g in groups:
            g = g.sort_values("timestamp").copy()
            ret = g["close"].pct_change().abs()
            mask = ret.isna() | (ret <= self.max_abs_return)
            parts.append(g.loc[mask])

        if not parts:
            return df.iloc[0:0]
        return pd.concat(parts, ignore_index=True)
