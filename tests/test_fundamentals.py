"""Phase 4 — fundamental + valuation tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from nepse_bot.fundamentals.engine import FundamentalEngine
from nepse_bot.fundamentals.loader import load_fundamentals_csv
from nepse_bot.fundamentals.models import (
    CompanyProfile,
    FundamentalRecord,
    Sector,
)
from nepse_bot.fundamentals.ratios import growth_pct, safe_div
from nepse_bot.fundamentals.store import FundamentalStore
from nepse_bot.indicators.types import MetricStatus


@pytest.fixture
def store(tmp_path: Path) -> FundamentalStore:
    return FundamentalStore(db_path=tmp_path / "fund.db")


def test_safe_div_and_growth():
    assert safe_div(10, 2) == 5.0
    assert safe_div(10, 0) is None
    assert safe_div(None, 2) is None
    assert growth_pct(110, 100) == pytest.approx(10.0)
    assert growth_pct(110, 0) is None
    assert growth_pct(None, 100) is None


def test_profile_and_record_roundtrip(store: FundamentalStore):
    store.upsert_profile(
        CompanyProfile(
            symbol="NABIL",
            name="Nabil Bank",
            sector=Sector.COMMERCIAL_BANK,
        )
    )
    p = store.get_profile("nabil")
    assert p is not None
    assert p.sector == Sector.COMMERCIAL_BANK

    rec = FundamentalRecord(
        symbol="NABIL",
        as_of=date(2024, 7, 15),
        source="test",
        eps=42.5,
        eps_prior=38.0,
        book_value_per_share=280.0,
        total_equity=65e9,
        net_profit=10e9,
        shares_outstanding=270e6,
        npl_ratio=1.2,
        capital_adequacy=13.5,
    )
    store.upsert_record(rec)
    got = store.get_latest_record("NABIL")
    assert got is not None
    assert got.eps == 42.5
    assert got.npl_ratio == 1.2


def test_engine_bank_with_price(store: FundamentalStore):
    store.upsert_profile(
        CompanyProfile(symbol="NABIL", sector=Sector.COMMERCIAL_BANK, name="Nabil")
    )
    store.upsert_record(
        FundamentalRecord(
            symbol="NABIL",
            as_of=date(2024, 7, 15),
            source="test",
            eps=40.0,
            eps_prior=35.0,
            book_value_per_share=200.0,
            dividend_per_share=10.0,
            total_equity=50e9,
            net_profit=8e9,
            total_assets=400e9,
            shares_outstanding=200e6,
            npl_ratio=1.5,
            capital_adequacy=12.0,
        )
    )
    eng = FundamentalEngine(store)
    snap = eng.compute("NABIL", price=400.0)

    assert snap.sector == Sector.COMMERCIAL_BANK
    assert snap.metrics["eps"].status == MetricStatus.OK
    assert snap.metrics["eps"].value == 40.0
    assert snap.metrics["pe"].status == MetricStatus.OK
    assert snap.metrics["pe"].value == pytest.approx(10.0)
    assert snap.metrics["pb"].status == MetricStatus.OK
    assert snap.metrics["pb"].value == pytest.approx(2.0)
    assert snap.metrics["roe"].status == MetricStatus.OK
    assert snap.metrics["eps_growth_pct"].status == MetricStatus.OK
    assert snap.metrics["dividend_yield"].status == MetricStatus.OK
    assert snap.metrics["net_margin"].status == MetricStatus.UNAVAILABLE
    assert any("banking" in n.lower() or "finance" in n.lower() for n in snap.notes)


def test_engine_never_invents(store: FundamentalStore):
    eng = FundamentalEngine(store)
    snap = eng.compute("MISSING", price=100.0)
    assert snap.as_of is None
    for m in snap.metrics.values():
        if m.status != MetricStatus.OK:
            assert m.value is None


def test_engine_manufacturing_ratios(store: FundamentalStore):
    store.upsert_profile(
        CompanyProfile(symbol="MFG", sector=Sector.MANUFACTURING)
    )
    store.upsert_record(
        FundamentalRecord(
            symbol="MFG",
            as_of=date(2024, 1, 1),
            source="test",
            revenue=1_000_000,
            revenue_prior=800_000,
            net_profit=100_000,
            operating_profit=150_000,
            ebitda=200_000,
            eps=5.0,
            book_value_per_share=50.0,
            total_equity=500_000,
            total_debt=200_000,
            total_assets=800_000,
            current_assets=300_000,
            current_liabilities=150_000,
            cash=50_000,
            interest_expense=20_000,
            shares_outstanding=20_000,
        )
    )
    eng = FundamentalEngine(store)
    snap = eng.compute("MFG", price=100.0)
    assert snap.metrics["revenue_growth_pct"].value == pytest.approx(25.0)
    assert snap.metrics["net_margin"].status == MetricStatus.OK
    assert snap.metrics["debt_to_equity"].status == MetricStatus.OK
    assert snap.metrics["current_ratio"].status == MetricStatus.OK
    assert snap.metrics["interest_coverage"].status == MetricStatus.OK
    assert snap.metrics["pe"].value == pytest.approx(20.0)
    assert snap.metrics["ev_ebitda"].status == MetricStatus.OK


def test_csv_loader(store: FundamentalStore, tmp_path: Path):
    sample = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "samples"
        / "NABIL_fundamentals_sample.csv"
    )
    if not sample.exists():
        pytest.skip("sample csv not present")
    n = load_fundamentals_csv(sample, store)
    assert n >= 1
    p = store.get_profile("NABIL")
    assert p is not None
    assert p.sector == Sector.COMMERCIAL_BANK
    rec = store.get_latest_record("NABIL")
    assert rec is not None
    assert rec.eps == 42.5

    eng = FundamentalEngine(store)
    snap = eng.compute("NABIL", price=500.0)
    assert snap.metrics["pe"].status == MetricStatus.OK
    lines = snap.summary_lines()
    assert any("NABIL" in x for x in lines)
