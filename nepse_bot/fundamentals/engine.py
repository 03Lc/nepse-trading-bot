"""
Fundamental + valuation engine.

Produces an explainable FundamentalSnapshot from stored facts + optional price.
Sector determines which metrics are highlighted; missing data stays N/A.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from nepse_bot.fundamentals.models import (
    SECTOR_PRIMARY_METRICS,
    CompanyProfile,
    FundamentalRecord,
    Sector,
)
from nepse_bot.fundamentals.ratios import growth_pct, margin_pct, safe_div
from nepse_bot.fundamentals.store import FundamentalStore
from nepse_bot.indicators.types import MetricResult, MetricStatus


@dataclass
class FundamentalSnapshot:
    symbol: str
    sector: Sector
    as_of: Optional[str]
    source: Optional[str]
    price: Optional[float]
    metrics: dict[str, MetricResult] = field(default_factory=dict)
    primary_metric_names: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def metric(self, name: str) -> MetricResult:
        return self.metrics.get(name, MetricResult.unavailable(name))

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "sector": self.sector.value,
            "as_of": self.as_of,
            "source": self.source,
            "price": self.price,
            "metrics": {k: v.as_dict() for k, v in self.metrics.items()},
            "primary_metric_names": self.primary_metric_names,
            "notes": self.notes,
        }

    def summary_lines(self) -> list[str]:
        lines = [
            f"{self.symbol}  sector={self.sector.value}  "
            f"as_of={self.as_of or 'N/A'}  source={self.source or 'N/A'}  "
            f"price={self.price}",
        ]
        shown = set()
        for name in self.primary_metric_names:
            m = self.metrics.get(name)
            if m:
                lines.append(self._fmt(m))
                shown.add(name)
        for name in sorted(self.metrics.keys()):
            if name in shown:
                continue
            m = self.metrics[name]
            if m.status == MetricStatus.OK:
                lines.append(self._fmt(m))
        for name in sorted(self.metrics.keys()):
            if name in shown:
                continue
            m = self.metrics[name]
            if m.status != MetricStatus.OK:
                lines.append(self._fmt(m))
        for n in self.notes:
            lines.append(f"  note: {n}")
        return lines

    @staticmethod
    def _fmt(m: MetricResult) -> str:
        if m.status == MetricStatus.OK and m.value is not None:
            if m.unit == "pct":
                return f"  {m.name}: {m.value:.2f}%"
            if m.unit == "ratio":
                return f"  {m.name}: {m.value:.3f}x"
            if abs(m.value) >= 1e6:
                return f"  {m.name}: {m.value:,.0f}"
            return f"  {m.name}: {m.value:.4f}"
        return f"  {m.name}: N/A — {m.status.value}"


class FundamentalEngine:
    def __init__(self, store: Optional[FundamentalStore] = None):
        self.store = store or FundamentalStore()

    def compute(
        self,
        symbol: str,
        *,
        price: Optional[float] = None,
        record: Optional[FundamentalRecord] = None,
        profile: Optional[CompanyProfile] = None,
    ) -> FundamentalSnapshot:
        symbol = symbol.upper()
        profile = profile or self.store.get_profile(symbol)
        sector = profile.sector if profile else Sector.UNKNOWN
        rec = record or self.store.get_latest_record(symbol)

        notes: list[str] = []
        if profile is None:
            notes.append("no company profile — sector treated as unknown")
        if rec is None:
            notes.append("no fundamental records — all metrics unavailable")
            primary = SECTOR_PRIMARY_METRICS.get(sector, [])
            metrics = {
                name: MetricResult.unavailable(name, "no fundamental record")
                for name in primary
            }
            for name in ("pe", "pb", "ps", "ev_ebitda", "dividend_yield"):
                metrics.setdefault(
                    name, MetricResult.unavailable(name, "no fundamental record")
                )
            return FundamentalSnapshot(
                symbol=symbol,
                sector=sector,
                as_of=None,
                source=None,
                price=price,
                metrics=metrics,
                primary_metric_names=list(primary),
                notes=notes,
            )

        metrics = self._build_metrics(rec, price=price, sector=sector)
        primary = SECTOR_PRIMARY_METRICS.get(
            sector, SECTOR_PRIMARY_METRICS[Sector.UNKNOWN]
        )

        if sector in (
            Sector.COMMERCIAL_BANK,
            Sector.DEVELOPMENT_BANK,
            Sector.FINANCE,
            Sector.MICROFINANCE,
        ):
            notes.append(
                "banking/finance sector: prefer ROE/ROA/NPL/CAR over industrial EV/EBITDA"
            )
        if rec.shares_outstanding is None and price is not None:
            notes.append(
                "shares_outstanding missing — market_cap/ratios needing shares may be N/A"
            )

        return FundamentalSnapshot(
            symbol=symbol,
            sector=sector,
            as_of=rec.as_of.isoformat(),
            source=rec.source,
            price=price,
            metrics=metrics,
            primary_metric_names=list(primary),
            notes=notes,
        )

    def _build_metrics(
        self,
        rec: FundamentalRecord,
        *,
        price: Optional[float],
        sector: Sector,
    ) -> dict[str, MetricResult]:
        src = rec.source
        ts = rec.loaded_at
        m: dict[str, MetricResult] = {}

        def put_raw(name: str, val: Optional[float], unit: Optional[str] = None) -> None:
            if val is None:
                m[name] = MetricResult.unavailable(name, f"field not in source ({src})")
            else:
                m[name] = MetricResult.ok(
                    name, val, unit=unit, source=src, timestamp=ts
                )

        def put_computed(
            name: str,
            val: Optional[float],
            unit: Optional[str] = None,
            need: str = "",
        ) -> None:
            if val is None:
                m[name] = MetricResult.unavailable(
                    name, need or "insufficient inputs to compute"
                )
            else:
                m[name] = MetricResult.ok(
                    name, val, unit=unit, source=f"computed:{src}", timestamp=ts
                )

        put_raw("revenue", rec.revenue, "npr")
        put_raw("net_profit", rec.net_profit, "npr")
        put_raw("operating_profit", rec.operating_profit, "npr")
        put_raw("ebitda", rec.ebitda, "npr")
        put_raw("eps", rec.eps, "npr")
        put_raw("book_value_per_share", rec.book_value_per_share, "npr")
        put_raw("dividend_per_share", rec.dividend_per_share, "npr")
        put_raw("total_assets", rec.total_assets, "npr")
        put_raw("total_equity", rec.total_equity, "npr")
        put_raw("total_debt", rec.total_debt, "npr")
        put_raw("operating_cash_flow", rec.operating_cash_flow, "npr")
        put_raw("free_cash_flow", rec.free_cash_flow, "npr")
        put_raw("shares_outstanding", rec.shares_outstanding)
        put_raw("npl_ratio", rec.npl_ratio, "pct")
        put_raw("capital_adequacy", rec.capital_adequacy, "pct")
        put_raw("net_interest_margin", rec.net_interest_margin, "pct")

        rev_g = rec.revenue_growth_pct
        if rev_g is None:
            rev_g = growth_pct(rec.revenue, rec.revenue_prior)
        put_computed(
            "revenue_growth_pct",
            rev_g,
            "pct",
            need="need revenue and revenue_prior (or source growth)",
        )

        eps_g = rec.eps_growth_pct
        if eps_g is None:
            eps_g = growth_pct(rec.eps, rec.eps_prior)
        put_computed(
            "eps_growth_pct",
            eps_g,
            "pct",
            need="need eps and eps_prior (or source growth)",
        )

        profit_g = rec.profit_growth_pct
        if profit_g is None:
            profit_g = growth_pct(rec.net_profit, rec.net_profit_prior)
        put_computed(
            "profit_growth_pct",
            profit_g,
            "pct",
            need="need net_profit and net_profit_prior (or source growth)",
        )

        put_computed(
            "operating_margin",
            margin_pct(rec.operating_profit, rec.revenue),
            "pct",
            need="need operating_profit and revenue",
        )
        put_computed(
            "net_margin",
            margin_pct(rec.net_profit, rec.revenue),
            "pct",
            need="need net_profit and revenue",
        )
        put_computed(
            "roe",
            margin_pct(rec.net_profit, rec.total_equity),
            "pct",
            need="need net_profit and total_equity",
        )
        put_computed(
            "roa",
            margin_pct(rec.net_profit, rec.total_assets),
            "pct",
            need="need net_profit and total_assets",
        )

        nopat = rec.operating_profit
        invested = None
        if rec.total_equity is not None:
            invested = rec.total_equity + (rec.total_debt or 0.0)
        put_computed(
            "roic",
            margin_pct(nopat, invested) if nopat is not None else None,
            "pct",
            need="need operating_profit and total_equity (+ debt optional)",
        )

        put_computed(
            "debt_to_equity",
            safe_div(rec.total_debt, rec.total_equity),
            "ratio",
            need="need total_debt and total_equity",
        )
        put_computed(
            "current_ratio",
            safe_div(rec.current_assets, rec.current_liabilities),
            "ratio",
            need="need current_assets and current_liabilities",
        )
        put_computed(
            "interest_coverage",
            safe_div(rec.operating_profit, rec.interest_expense),
            "ratio",
            need="need operating_profit and interest_expense",
        )

        market_cap = rec.market_cap
        if market_cap is None and price is not None and rec.shares_outstanding is not None:
            market_cap = price * rec.shares_outstanding
        put_computed(
            "market_cap",
            market_cap,
            "npr",
            need="need market_cap from source or price × shares_outstanding",
        )

        put_computed(
            "pe",
            safe_div(price, rec.eps) if price is not None else None,
            "ratio",
            need="need price and eps",
        )
        put_computed(
            "pb",
            safe_div(price, rec.book_value_per_share) if price is not None else None,
            "ratio",
            need="need price and book_value_per_share",
        )
        put_computed(
            "ps",
            safe_div(market_cap, rec.revenue),
            "ratio",
            need="need market_cap and revenue",
        )

        ev = None
        if market_cap is not None:
            ev = market_cap + (rec.total_debt or 0.0) - (rec.cash or 0.0)
        put_computed(
            "enterprise_value",
            ev,
            "npr",
            need="need market_cap (debt/cash optional)",
        )
        put_computed(
            "ev_ebitda",
            safe_div(ev, rec.ebitda),
            "ratio",
            need="need enterprise_value and ebitda",
        )

        put_computed(
            "dividend_yield",
            margin_pct(rec.dividend_per_share, price) if price is not None else None,
            "pct",
            need="need dividend_per_share and price",
        )
        put_computed(
            "payout_ratio",
            safe_div(rec.dividend_per_share, rec.eps),
            "ratio",
            need="need dividend_per_share and eps",
        )

        if sector in (
            Sector.COMMERCIAL_BANK,
            Sector.DEVELOPMENT_BANK,
            Sector.FINANCE,
            Sector.MICROFINANCE,
            Sector.LIFE_INSURANCE,
            Sector.NON_LIFE_INSURANCE,
        ):
            if m.get("ev_ebitda") and m["ev_ebitda"].status == MetricStatus.OK:
                m["ev_ebitda"] = MetricResult(
                    name="ev_ebitda",
                    value=m["ev_ebitda"].value,
                    status=MetricStatus.OK,
                    source=m["ev_ebitda"].source,
                    timestamp=ts,
                    unit="ratio",
                    extra={"warning": "less meaningful for banks/insurers"},
                )

        return m
