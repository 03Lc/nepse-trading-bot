"""
Market and sector analysis.

Compares symbols to NEPSE / sector benchmarks, estimates breadth,
trend, and volatility. Missing benchmark data → explicit N/A status.
"""

from nepse_bot.market_analysis.engine import (
    MarketAnalysisEngine,
    MarketContext,
    RelativePerformance,
)
from nepse_bot.market_analysis.benchmarks import BenchmarkStore, BenchmarkSeries

__all__ = [
    "MarketAnalysisEngine",
    "MarketContext",
    "RelativePerformance",
    "BenchmarkStore",
    "BenchmarkSeries",
]
