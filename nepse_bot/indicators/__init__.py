"""
Technical indicators and technical analysis engine.

All calculations are pure pandas/NumPy (no TA-Lib required).
Every metric carries status so missing data is never silently invented.
"""

from nepse_bot.indicators.types import MetricStatus, MetricResult
from nepse_bot.indicators.core import (
    sma,
    ema,
    rsi,
    macd,
    atr,
    adx,
    stochastic,
    roc,
    momentum,
    vwap,
    obv,
    accumulation_distribution,
    relative_volume,
)
from nepse_bot.indicators.levels import (
    rolling_high_low,
    distance_from_extreme,
    simple_support_resistance,
    detect_gaps,
    trend_structure,
)
from nepse_bot.indicators.engine import TechnicalEngine, TechnicalSnapshot

__all__ = [
    "MetricStatus",
    "MetricResult",
    "sma",
    "ema",
    "rsi",
    "macd",
    "atr",
    "adx",
    "stochastic",
    "roc",
    "momentum",
    "vwap",
    "obv",
    "accumulation_distribution",
    "relative_volume",
    "rolling_high_low",
    "distance_from_extreme",
    "simple_support_resistance",
    "detect_gaps",
    "trend_structure",
    "TechnicalEngine",
    "TechnicalSnapshot",
]
