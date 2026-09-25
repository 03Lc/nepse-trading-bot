"""
SQLite storage for company profiles and fundamental records.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from nepse_bot.fundamentals.models import CompanyProfile, FundamentalRecord, Sector
from nepse_bot.monitoring import get_logger

log = get_logger("fundamentals.store")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS company_profiles (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT NOT NULL,
    listed INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fundamental_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    as_of TEXT NOT NULL,
    source TEXT NOT NULL,
    loaded_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    UNIQUE(symbol, as_of, source)
);

CREATE INDEX IF NOT EXISTS idx_fund_symbol ON fundamental_records(symbol);
CREATE INDEX IF NOT EXISTS idx_fund_as_of ON fundamental_records(as_of);
"""

_PAYLOAD_FIELDS = [
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


class FundamentalStore:
    def __init__(self, db_path: str | Path = "data/storage/nepse_fundamentals.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def upsert_profile(self, profile: CompanyProfile) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO company_profiles (symbol, name, sector, listed, notes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    name=excluded.name,
                    sector=excluded.sector,
                    listed=excluded.listed,
                    notes=excluded.notes,
                    updated_at=excluded.updated_at
                """,
                (
                    profile.symbol.upper(),
                    profile.name,
                    profile.sector.value,
                    1 if profile.listed else 0,
                    profile.notes,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        log.info("Upserted profile %s sector=%s", profile.symbol, profile.sector.value)

    def get_profile(self, symbol: str) -> Optional[CompanyProfile]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM company_profiles WHERE symbol = ?",
                (symbol.upper(),),
            ).fetchone()
        if not row:
            return None
        try:
            sector = Sector(row["sector"])
        except ValueError:
            sector = Sector.UNKNOWN
        return CompanyProfile(
            symbol=row["symbol"],
            name=row["name"],
            sector=sector,
            listed=bool(row["listed"]),
            notes=row["notes"] or "",
        )

    def list_profiles(self) -> list[CompanyProfile]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM company_profiles ORDER BY symbol"
            ).fetchall()
        out: list[CompanyProfile] = []
        for row in rows:
            try:
                sector = Sector(row["sector"])
            except ValueError:
                sector = Sector.UNKNOWN
            out.append(
                CompanyProfile(
                    symbol=row["symbol"],
                    name=row["name"],
                    sector=sector,
                    listed=bool(row["listed"]),
                    notes=row["notes"] or "",
                )
            )
        return out

    def upsert_record(self, rec: FundamentalRecord) -> None:
        payload = {k: getattr(rec, k) for k in _PAYLOAD_FIELDS}
        if rec.extra:
            payload["extra"] = rec.extra
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO fundamental_records (symbol, as_of, source, loaded_at, payload)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(symbol, as_of, source) DO UPDATE SET
                    loaded_at=excluded.loaded_at,
                    payload=excluded.payload
                """,
                (
                    rec.symbol.upper(),
                    rec.as_of.isoformat(),
                    rec.source,
                    rec.loaded_at.isoformat(),
                    json.dumps(payload),
                ),
            )
        log.info(
            "Upserted fundamentals %s as_of=%s source=%s",
            rec.symbol,
            rec.as_of,
            rec.source,
        )

    def get_latest_record(
        self,
        symbol: str,
        source: Optional[str] = None,
    ) -> Optional[FundamentalRecord]:
        q = "SELECT * FROM fundamental_records WHERE symbol = ?"
        params: list[Any] = [symbol.upper()]
        if source:
            q += " AND source = ?"
            params.append(source)
        q += " ORDER BY as_of DESC LIMIT 1"
        with self._connect() as conn:
            row = conn.execute(q, params).fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def get_records(
        self,
        symbol: str,
        limit: int = 20,
    ) -> list[FundamentalRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM fundamental_records
                WHERE symbol = ?
                ORDER BY as_of DESC
                LIMIT ?
                """,
                (symbol.upper(), limit),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def _row_to_record(self, row: sqlite3.Row) -> FundamentalRecord:
        payload = json.loads(row["payload"])
        extra = payload.pop("extra", {}) or {}
        kwargs = {k: payload.get(k) for k in _PAYLOAD_FIELDS}
        return FundamentalRecord(
            symbol=row["symbol"],
            as_of=date.fromisoformat(row["as_of"]),
            source=row["source"],
            loaded_at=datetime.fromisoformat(row["loaded_at"]),
            extra=extra,
            **kwargs,
        )
