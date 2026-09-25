"""
Load fundamental records and company profiles from CSV.

CSV columns are optional; missing columns → None fields (never fabricated).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from nepse_bot.fundamentals.models import CompanyProfile, FundamentalRecord, Sector
from nepse_bot.fundamentals.store import FundamentalStore
from nepse_bot.monitoring import get_logger

log = get_logger("fundamentals.loader")

_NUMERIC_FIELDS = [
    "revenue", "revenue_prior", "net_profit", "net_profit_prior",
    "operating_profit", "ebitda", "interest_expense",
    "eps", "eps_prior", "book_value_per_share", "dividend_per_share",
    "total_assets", "total_equity", "total_debt",
    "current_assets", "current_liabilities", "cash",
    "operating_cash_flow", "free_cash_flow", "capex",
    "npl_ratio", "capital_adequacy", "net_interest_margin",
    "deposits", "loans", "shares_outstanding", "market_cap",
    "revenue_growth_pct", "eps_growth_pct", "profit_growth_pct",
]


def _parse_sector(val: object) -> Sector:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return Sector.UNKNOWN
    s = str(val).strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "bank": Sector.COMMERCIAL_BANK,
        "commercial_banks": Sector.COMMERCIAL_BANK,
        "commercial_bank": Sector.COMMERCIAL_BANK,
        "development_banks": Sector.DEVELOPMENT_BANK,
        "hydro": Sector.HYDROPOWER,
        "hydropower": Sector.HYDROPOWER,
        "insurance": Sector.NON_LIFE_INSURANCE,
        "life_insurance": Sector.LIFE_INSURANCE,
        "non_life_insurance": Sector.NON_LIFE_INSURANCE,
        "microfinance": Sector.MICROFINANCE,
        "finance": Sector.FINANCE,
        "manufacturing": Sector.MANUFACTURING,
        "hotels": Sector.HOTELS_TOURISM,
        "hotels_tourism": Sector.HOTELS_TOURISM,
        "trading": Sector.TRADING,
        "investment": Sector.INVESTMENT,
        "others": Sector.OTHERS,
    }
    if s in aliases:
        return aliases[s]
    try:
        return Sector(s)
    except ValueError:
        return Sector.UNKNOWN


def _f(row: pd.Series, col: str) -> Optional[float]:
    if col not in row.index:
        return None
    val = row[col]
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def load_fundamentals_csv(
    path: str | Path,
    store: FundamentalStore,
    *,
    default_source: str = "csv",
) -> int:
    """
    Load rows into FundamentalStore.

    Expected columns (all optional except symbol, as_of):
      symbol, as_of, source, sector, name, ...numeric fields...
    If sector/name present, upserts CompanyProfile as well.
    """
    path = Path(path)
    df = pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "symbol" not in df.columns or "as_of" not in df.columns:
        raise ValueError("CSV must include symbol and as_of columns")

    count = 0
    for _, row in df.iterrows():
        symbol = str(row["symbol"]).strip().upper()
        as_of_raw = row["as_of"]
        as_of = pd.to_datetime(as_of_raw).date()
        source = (
            str(row["source"]).strip()
            if "source" in df.columns and pd.notna(row.get("source"))
            else default_source
        )

        if "sector" in df.columns or "name" in df.columns:
            profile = CompanyProfile(
                symbol=symbol,
                name=(
                    str(row["name"]).strip()
                    if "name" in df.columns and pd.notna(row.get("name"))
                    else None
                ),
                sector=_parse_sector(row["sector"]) if "sector" in df.columns else Sector.UNKNOWN,
            )
            store.upsert_profile(profile)

        kwargs = {f: _f(row, f) for f in _NUMERIC_FIELDS}
        rec = FundamentalRecord(
            symbol=symbol,
            as_of=as_of if isinstance(as_of, date) else date.fromisoformat(str(as_of)),
            source=source,
            loaded_at=datetime.now(timezone.utc),
            **kwargs,
        )
        store.upsert_record(rec)
        count += 1

    log.info("Loaded %s fundamental rows from %s", count, path)
    return count
