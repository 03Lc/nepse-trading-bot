"""
Fundamental and valuation analysis.

Never invents missing financial data. Every metric carries status/source.
Sector profiles select which metrics are meaningful (e.g. banks vs industrials).
"""

from nepse_bot.fundamentals.models import (
    Sector,
    CompanyProfile,
    FundamentalRecord,
)
from nepse_bot.fundamentals.store import FundamentalStore
from nepse_bot.fundamentals.engine import (
    FundamentalEngine,
    FundamentalSnapshot,
)
from nepse_bot.fundamentals.loader import load_fundamentals_csv

__all__ = [
    "Sector",
    "CompanyProfile",
    "FundamentalRecord",
    "FundamentalStore",
    "FundamentalEngine",
    "FundamentalSnapshot",
    "load_fundamentals_csv",
]
