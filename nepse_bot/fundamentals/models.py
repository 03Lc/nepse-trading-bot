"""
Company profile, sector taxonomy, and fundamental fact records.

Values are stored only when provided by a source. Missing fields stay None.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Optional


class Sector(str, Enum):
    """NEPSE-oriented sector grouping for metric selection."""

    COMMERCIAL_BANK = "commercial_bank"
    DEVELOPMENT_BANK = "development_bank"
    FINANCE = "finance"
    MICROFINANCE = "microfinance"
    LIFE_INSURANCE = "life_insurance"
    NON_LIFE_INSURANCE = "non_life_insurance"
    HYDROPOWER = "hydropower"
    MANUFACTURING = "manufacturing"
    HOTELS_TOURISM = "hotels_tourism"
    TRADING = "trading"
    INVESTMENT = "investment"
    OTHERS = "others"
    UNKNOWN = "unknown"


SECTOR_PRIMARY_METRICS: dict[Sector, list[str]] = {
    Sector.COMMERCIAL_BANK: [
        "eps", "eps_growth_pct", "roe", "roa", "npl_ratio", "capital_adequacy",
        "net_interest_margin", "book_value_per_share", "dividend_yield", "pe", "pb",
    ],
    Sector.DEVELOPMENT_BANK: [
        "eps", "roe", "roa", "npl_ratio", "capital_adequacy",
        "book_value_per_share", "pe", "pb",
    ],
    Sector.FINANCE: [
        "eps", "roe", "roa", "book_value_per_share", "pe", "pb", "dividend_yield",
    ],
    Sector.MICROFINANCE: [
        "eps", "roe", "roa", "book_value_per_share", "pe", "pb",
    ],
    Sector.LIFE_INSURANCE: [
        "eps", "roe", "book_value_per_share", "pe", "pb", "dividend_yield",
    ],
    Sector.NON_LIFE_INSURANCE: [
        "eps", "roe", "book_value_per_share", "pe", "pb", "dividend_yield",
    ],
    Sector.HYDROPOWER: [
        "revenue", "revenue_growth_pct", "eps", "eps_growth_pct", "net_margin",
        "roe", "debt_to_equity", "interest_coverage", "pe", "pb", "dividend_yield",
    ],
    Sector.MANUFACTURING: [
        "revenue", "revenue_growth_pct", "eps", "eps_growth_pct", "operating_margin",
        "net_margin", "roe", "roa", "roic", "debt_to_equity", "current_ratio",
        "free_cash_flow", "pe", "pb", "ps", "ev_ebitda",
    ],
    Sector.HOTELS_TOURISM: [
        "revenue", "revenue_growth_pct", "eps", "operating_margin", "net_margin",
        "roe", "debt_to_equity", "pe", "pb",
    ],
    Sector.TRADING: [
        "revenue", "eps", "net_margin", "roe", "current_ratio", "pe", "pb", "ps",
    ],
    Sector.INVESTMENT: [
        "eps", "book_value_per_share", "roe", "pe", "pb", "dividend_yield",
    ],
    Sector.OTHERS: ["revenue", "eps", "roe", "pe", "pb"],
    Sector.UNKNOWN: ["eps", "roe", "pe", "pb"],
}


@dataclass
class CompanyProfile:
    symbol: str
    name: Optional[str] = None
    sector: Sector = Sector.UNKNOWN
    listed: bool = True
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "sector": self.sector.value,
            "listed": self.listed,
            "notes": self.notes,
        }


@dataclass
class FundamentalRecord:
    """
    Point-in-time fundamental facts for a symbol.

    All numeric fields are Optional. None means "not provided by source",
    not zero.
    """

    symbol: str
    as_of: date
    source: str = "manual"
    loaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    revenue: Optional[float] = None
    revenue_prior: Optional[float] = None
    net_profit: Optional[float] = None
    net_profit_prior: Optional[float] = None
    operating_profit: Optional[float] = None
    ebitda: Optional[float] = None
    interest_expense: Optional[float] = None

    eps: Optional[float] = None
    eps_prior: Optional[float] = None
    book_value_per_share: Optional[float] = None
    dividend_per_share: Optional[float] = None

    total_assets: Optional[float] = None
    total_equity: Optional[float] = None
    total_debt: Optional[float] = None
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    cash: Optional[float] = None

    operating_cash_flow: Optional[float] = None
    free_cash_flow: Optional[float] = None
    capex: Optional[float] = None

    npl_ratio: Optional[float] = None
    capital_adequacy: Optional[float] = None
    net_interest_margin: Optional[float] = None
    deposits: Optional[float] = None
    loans: Optional[float] = None

    shares_outstanding: Optional[float] = None
    market_cap: Optional[float] = None

    revenue_growth_pct: Optional[float] = None
    eps_growth_pct: Optional[float] = None
    profit_growth_pct: Optional[float] = None

    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["as_of"] = self.as_of.isoformat()
        d["loaded_at"] = self.loaded_at.isoformat()
        return d

    def get_field(self, name: str) -> Optional[float]:
        if not hasattr(self, name):
            return self.extra.get(name)
        val = getattr(self, name)
        if isinstance(val, (int, float)):
            return float(val)
        return None
