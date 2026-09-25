"""
SQLite-backed OHLCV storage.

Schema:
  ohlcv(symbol, timestamp, open, high, low, close, volume, turnover, trades)
  UNIQUE(symbol, timestamp)

Timestamps stored as ISO-8601 UTC strings.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd

from nepse_bot.data.schema import validate_ohlcv_frame
from nepse_bot.monitoring import get_logger

log = get_logger("data.storage")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ohlcv (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    turnover REAL,
    trades INTEGER,
    UNIQUE(symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_ts ON ohlcv(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_ohlcv_ts ON ohlcv(timestamp);
"""


class SQLiteOHLCVStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
        log.debug("SQLite store ready | path=%s", self.db_path)

    def upsert(self, df: pd.DataFrame) -> int:
        clean = validate_ohlcv_frame(df, require_symbol=True)
        if clean.empty:
            return 0

        rows = []
        for r in clean.itertuples(index=False):
            ts = pd.Timestamp(r.timestamp)
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            else:
                ts = ts.tz_convert("UTC")
            turnover = getattr(r, "turnover", None)
            trades = getattr(r, "trades", None)
            rows.append(
                (
                    str(r.symbol).upper(),
                    ts.isoformat(),
                    float(r.open),
                    float(r.high),
                    float(r.low),
                    float(r.close),
                    float(r.volume),
                    float(turnover) if turnover is not None and pd.notna(turnover) else None,
                    int(trades) if trades is not None and pd.notna(trades) else None,
                )
            )

        sql = """
        INSERT INTO ohlcv (symbol, timestamp, open, high, low, close, volume, turnover, trades)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, timestamp) DO UPDATE SET
            open=excluded.open,
            high=excluded.high,
            low=excluded.low,
            close=excluded.close,
            volume=excluded.volume,
            turnover=excluded.turnover,
            trades=excluded.trades
        """
        with self._connect() as conn:
            conn.executemany(sql, rows)
            conn.commit()
        log.info("Upserted %d OHLCV rows into %s", len(rows), self.db_path.name)
        return len(rows)

    def get(
        self,
        symbol: str,
        start: Optional[str | pd.Timestamp] = None,
        end: Optional[str | pd.Timestamp] = None,
    ) -> pd.DataFrame:
        symbol = symbol.upper()
        clauses = ["symbol = ?"]
        params: list = [symbol]

        if start is not None:
            ts = pd.Timestamp(start)
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            clauses.append("timestamp >= ?")
            params.append(ts.tz_convert("UTC").isoformat())
        if end is not None:
            ts = pd.Timestamp(end)
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            clauses.append("timestamp <= ?")
            params.append(ts.tz_convert("UTC").isoformat())

        where = " AND ".join(clauses)
        sql = f"""
        SELECT symbol, timestamp, open, high, low, close, volume, turnover, trades
        FROM ohlcv
        WHERE {where}
        ORDER BY timestamp ASC
        """
        with self._connect() as conn:
            df = pd.read_sql_query(sql, conn, params=params)
        if df.empty:
            return df
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df

    def list_symbols(self) -> list[str]:
        with self._connect() as conn:
            cur = conn.execute("SELECT DISTINCT symbol FROM ohlcv ORDER BY symbol")
            return [r[0] for r in cur.fetchall()]

    def count(self, symbol: Optional[str] = None) -> int:
        with self._connect() as conn:
            if symbol:
                cur = conn.execute(
                    "SELECT COUNT(*) FROM ohlcv WHERE symbol = ?", (symbol.upper(),)
                )
            else:
                cur = conn.execute("SELECT COUNT(*) FROM ohlcv")
            return int(cur.fetchone()[0])

    def delete_symbol(self, symbol: str) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM ohlcv WHERE symbol = ?", (symbol.upper(),))
            conn.commit()
            return cur.rowcount
