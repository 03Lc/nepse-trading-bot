"""Concurrent universe scanner (Phase 7)."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from nepse_bot.alerts.base import Alert, AlertManager
from nepse_bot.fundamentals.engine import FundamentalEngine, FundamentalSnapshot
from nepse_bot.fundamentals.store import FundamentalStore
from nepse_bot.indicators.engine import TechnicalEngine, TechnicalSnapshot
from nepse_bot.market_analysis.benchmarks import BenchmarkStore
from nepse_bot.market_analysis.engine import MarketAnalysisEngine, MarketContext
from nepse_bot.providers.base import DataProvider
from nepse_bot.signals.engine import SignalEngine, SignalReport
from nepse_bot.signals.rules import RuleConfig
from nepse_bot.signals.types import SignalState


@dataclass
class ScanResult:
    symbol: str
    signal: Optional[SignalReport]
    technical: Optional[TechnicalSnapshot]
    fundamental: Optional[FundamentalSnapshot]
    market: Optional[MarketContext]
    latency_ms: float
    error: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "signal": self.signal.state.value if self.signal else None,
            "price": self.signal.price if self.signal else None,
            "passed": self.signal.passed if self.signal else None,
            "failed": self.signal.failed if self.signal else None,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


@dataclass
class ScanReport:
    as_of: datetime
    results: list[ScanResult] = field(default_factory=list)
    total_ms: float = 0.0
    symbols_scanned: int = 0
    errors: int = 0

    def by_signal(self, state: SignalState) -> list[ScanResult]:
        return [r for r in self.results if r.signal and r.signal.state == state]

    def summary_lines(self) -> list[str]:
        lines = [
            f"Scan report  symbols={self.symbols_scanned}  errors={self.errors}  "
            f"total_ms={self.total_ms:.1f}  as_of={self.as_of.isoformat()}",
        ]
        counts: dict[str, int] = {}
        for r in self.results:
            if r.signal:
                counts[r.signal.state.value] = counts.get(r.signal.state.value, 0) + 1
        for k, v in sorted(counts.items()):
            lines.append(f"  {k}: {v}")
        for r in sorted(
            [x for x in self.results if x.signal],
            key=lambda x: -(x.signal.passed if x.signal else 0),
        )[:20]:
            assert r.signal
            lines.append(
                f"  {r.symbol:8s}  {r.signal.state.value:16s}  "
                f"P={r.signal.passed} F={r.signal.failed}  px={r.signal.price}  {r.latency_ms:.1f}ms"
            )
        return lines


class ConcurrentScanner:
    def __init__(
        self,
        provider: DataProvider,
        *,
        signal_engine: Optional[SignalEngine] = None,
        technical_engine: Optional[TechnicalEngine] = None,
        fundamental_store: Optional[FundamentalStore] = None,
        benchmark_store: Optional[BenchmarkStore] = None,
        alert_manager: Optional[AlertManager] = None,
        max_workers: int = 8,
        rule_config: Optional[RuleConfig] = None,
    ):
        self.provider = provider
        self.technical_engine = technical_engine or TechnicalEngine()
        self.signal_engine = signal_engine or SignalEngine(rule_config or RuleConfig())
        self.fundamental_store = fundamental_store
        self.benchmark_store = benchmark_store
        self.alert_manager = alert_manager
        self.max_workers = max(1, max_workers)

    def _scan_one(self, symbol: str) -> ScanResult:
        t0 = time.perf_counter()
        try:
            bars = self.provider.get_ohlcv(symbol)
            if bars is None or bars.empty:
                return ScanResult(
                    symbol=symbol, signal=None, technical=None, fundamental=None,
                    market=None, latency_ms=(time.perf_counter() - t0) * 1000, error="no bars",
                )
            tech = self.technical_engine.compute(bars, symbol=symbol)
            fund = None
            if self.fundamental_store is not None:
                try:
                    fund = FundamentalEngine(self.fundamental_store).compute(symbol, price=tech.price)
                except Exception:
                    fund = None
            market = None
            if self.benchmark_store is not None:
                try:
                    sector = None
                    if self.fundamental_store is not None:
                        prof = self.fundamental_store.get_profile(symbol)
                        if prof:
                            sector = prof.sector.value
                    market = MarketAnalysisEngine(benchmarks=self.benchmark_store).analyze_symbol(
                        symbol, bars, sector=sector
                    )
                except Exception:
                    market = None
            report = self.signal_engine.evaluate(
                symbol, technical=tech, fundamental=fund, market=market
            )
            latency = (time.perf_counter() - t0) * 1000
            if self.alert_manager and report.state in (SignalState.BUY_SETUP, SignalState.SELL_EXIT_SETUP):
                self.alert_manager.emit(
                    Alert(
                        symbol=symbol,
                        title=report.state.value,
                        body="\n".join(report.reasons),
                        priority="high",
                        price=report.price,
                        signal=report.state.value,
                    )
                )
            return ScanResult(
                symbol=symbol, signal=report, technical=tech, fundamental=fund,
                market=market, latency_ms=latency,
            )
        except Exception as e:
            return ScanResult(
                symbol=symbol, signal=None, technical=None, fundamental=None,
                market=None, latency_ms=(time.perf_counter() - t0) * 1000, error=str(e),
            )

    def scan(self, symbols: Optional[list[str]] = None) -> ScanReport:
        symbols = symbols or self.provider.list_symbols()
        symbols = [s.upper() for s in symbols]
        t0 = time.perf_counter()
        results: list[ScanResult] = []
        workers = min(self.max_workers, max(1, len(symbols)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self._scan_one, s): s for s in symbols}
            for fut in as_completed(futures):
                results.append(fut.result())
        results.sort(key=lambda r: r.symbol)
        return ScanReport(
            as_of=datetime.now(timezone.utc),
            results=results,
            total_ms=(time.perf_counter() - t0) * 1000,
            symbols_scanned=len(symbols),
            errors=sum(1 for r in results if r.error),
        )
