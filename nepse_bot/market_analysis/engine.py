"""Market analysis engine: relative performance vs NEPSE / sector, market regime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from nepse_bot.fundamentals.models import Sector
from nepse_bot.indicators.types import MetricResult, MetricStatus
from nepse_bot.market_analysis.benchmarks import (
    NEPSE_INDEX,
    BenchmarkStore,
    sector_to_benchmark_id,
)
from nepse_bot.market_analysis.breadth import BreadthSnapshot, compute_breadth
from nepse_bot.market_analysis.relative import (
    align_closes,
    period_return,
    realized_volatility,
    simple_trend_label,
)

DEFAULT_LOOKBACKS = (5, 20, 60)
_TREND_SCORE = {
    "uptrend": 1.0,
    "bullish_bias": 0.5,
    "sideways": 0.0,
    "bearish_bias": -0.5,
    "downtrend": -1.0,
    "unknown": 0.0,
}


@dataclass
class RelativePerformance:
    symbol: str
    lookback: int
    stock_return_pct: Optional[float]
    bench_return_pct: Optional[float]
    relative_pct: Optional[float]
    benchmark_id: str
    status: MetricStatus

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "lookback": self.lookback,
            "stock_return_pct": self.stock_return_pct,
            "bench_return_pct": self.bench_return_pct,
            "relative_pct": self.relative_pct,
            "benchmark_id": self.benchmark_id,
            "status": self.status.value,
        }


@dataclass
class MarketContext:
    symbol: Optional[str]
    sector: Optional[str]
    as_of: datetime
    metrics: dict[str, MetricResult] = field(default_factory=dict)
    relative_vs_nepse: list[RelativePerformance] = field(default_factory=list)
    relative_vs_sector: list[RelativePerformance] = field(default_factory=list)
    breadth: Optional[BreadthSnapshot] = None
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "sector": self.sector,
            "as_of": self.as_of.isoformat(),
            "metrics": {k: v.as_dict() for k, v in self.metrics.items()},
            "relative_vs_nepse": [r.as_dict() for r in self.relative_vs_nepse],
            "relative_vs_sector": [r.as_dict() for r in self.relative_vs_sector],
            "breadth": (
                {
                    "symbols_counted": self.breadth.symbols_counted,
                    "advancers": self.breadth.advancers,
                    "decliners": self.breadth.decliners,
                    "unchanged": self.breadth.unchanged,
                    "advance_decline_ratio": self.breadth.advance_decline_ratio,
                    "pct_above_sma20": self.breadth.pct_above_sma20,
                    "pct_above_sma50": self.breadth.pct_above_sma50,
                    "notes": self.breadth.notes,
                }
                if self.breadth
                else None
            ),
            "notes": self.notes,
        }

    def summary_lines(self) -> list[str]:
        lines = [
            f"Market context  symbol={self.symbol or 'MARKET'}  "
            f"sector={self.sector or 'N/A'}  as_of={self.as_of.isoformat()}",
        ]
        for name in sorted(self.metrics.keys()):
            m = self.metrics[name]
            if m.status == MetricStatus.OK and m.value is not None:
                if m.unit == "pct":
                    lines.append(f"  {name}: {m.value:.2f}%")
                elif m.unit == "label":
                    label = m.extra.get("trend_label", m.value)
                    lines.append(f"  {name}: {label}")
                else:
                    lines.append(f"  {name}: {m.value:.4f}")
            else:
                lines.append(f"  {name}: N/A — {m.status.value}")
        for r in self.relative_vs_nepse:
            if r.status == MetricStatus.OK and r.relative_pct is not None:
                flag = "OUTPERFORM" if r.relative_pct > 0 else "UNDERPERFORM"
                lines.append(
                    f"  vs NEPSE ({r.lookback}d): RS={r.relative_pct:+.2f}pp [{flag}]"
                )
            else:
                lines.append(f"  vs NEPSE ({r.lookback}d): N/A")
        for r in self.relative_vs_sector:
            if r.status == MetricStatus.OK and r.relative_pct is not None:
                flag = "OUTPERFORM" if r.relative_pct > 0 else "UNDERPERFORM"
                lines.append(
                    f"  vs {r.benchmark_id} ({r.lookback}d): "
                    f"RS={r.relative_pct:+.2f}pp [{flag}]"
                )
            else:
                lines.append(f"  vs sector ({r.lookback}d): N/A — {r.status.value}")
        if self.breadth:
            b = self.breadth
            lines.append(
                f"  breadth: n={b.symbols_counted} "
                f"adv={b.advancers} dec={b.decliners} unc={b.unchanged}"
            )
            if b.pct_above_sma20 is not None:
                lines.append(f"  % above SMA20: {b.pct_above_sma20:.1f}%")
            if b.pct_above_sma50 is not None:
                lines.append(f"  % above SMA50: {b.pct_above_sma50:.1f}%")
        for n in self.notes:
            lines.append(f"  note: {n}")
        return lines


class MarketAnalysisEngine:
    def __init__(
        self,
        benchmarks: Optional[BenchmarkStore] = None,
        lookbacks: tuple[int, ...] = DEFAULT_LOOKBACKS,
    ):
        self.benchmarks = benchmarks or BenchmarkStore()
        self.lookbacks = lookbacks

    def _rel_list(
        self,
        symbol: str,
        stock_close: pd.Series,
        work: pd.DataFrame,
        bench_bars: pd.DataFrame,
        benchmark_id: str,
    ) -> list[RelativePerformance]:
        out: list[RelativePerformance] = []
        b_close = bench_bars["close"].astype(float)
        for lb in self.lookbacks:
            s_ret = period_return(stock_close, lb)
            b_ret = period_return(b_close, lb)
            try:
                sc, bc = align_closes(work, bench_bars)
                if len(sc) > lb:
                    s_ret = period_return(sc, lb)
                    b_ret = period_return(bc, lb)
            except Exception:
                pass
            if s_ret is None or b_ret is None:
                out.append(
                    RelativePerformance(
                        symbol=symbol,
                        lookback=lb,
                        stock_return_pct=s_ret,
                        bench_return_pct=b_ret,
                        relative_pct=None,
                        benchmark_id=benchmark_id,
                        status=MetricStatus.INSUFFICIENT_DATA,
                    )
                )
            else:
                out.append(
                    RelativePerformance(
                        symbol=symbol,
                        lookback=lb,
                        stock_return_pct=s_ret,
                        bench_return_pct=b_ret,
                        relative_pct=s_ret - b_ret,
                        benchmark_id=benchmark_id,
                        status=MetricStatus.OK,
                    )
                )
        return out

    def analyze_symbol(
        self,
        symbol: str,
        stock_bars: pd.DataFrame,
        *,
        sector: Optional[Sector | str] = None,
        universe_frames: Optional[dict[str, pd.DataFrame]] = None,
    ) -> MarketContext:
        symbol = symbol.upper()
        sector_val = sector.value if isinstance(sector, Sector) else sector

        notes: list[str] = []
        metrics: dict[str, MetricResult] = {}
        as_of = datetime.now(timezone.utc)

        if stock_bars is None or stock_bars.empty:
            notes.append("no stock bars")
            return MarketContext(symbol=symbol, sector=sector_val, as_of=as_of, notes=notes)

        work = stock_bars.copy()
        work.columns = [str(c).strip().lower() for c in work.columns]
        if "timestamp" in work.columns:
            ts = pd.to_datetime(work["timestamp"].iloc[-1], utc=True)
            if not pd.isna(ts):
                as_of = ts.to_pydatetime()

        stock_close = work["close"].astype(float)

        for lb in self.lookbacks:
            ret = period_return(stock_close, lb)
            key = f"stock_return_{lb}d"
            if ret is None:
                metrics[key] = MetricResult.insufficient(key, need=lb + 1, have=len(stock_close))
            else:
                metrics[key] = MetricResult.ok(key, ret, period=lb, unit="pct")

        vol = realized_volatility(stock_close, 20)
        if vol is None:
            metrics["stock_volatility_20d"] = MetricResult.insufficient(
                "stock_volatility_20d", need=21, have=len(stock_close)
            )
        else:
            metrics["stock_volatility_20d"] = MetricResult.ok(
                "stock_volatility_20d", vol, period=20, unit="pct"
            )

        rel_nepse: list[RelativePerformance] = []
        nepse = self.benchmarks.get_series(NEPSE_INDEX)
        if nepse.empty:
            notes.append("NEPSE index bars unavailable")
            metrics["nepse_trend"] = MetricResult.unavailable("nepse_trend", "no NEPSE bars")
            metrics["nepse_volatility_20d"] = MetricResult.unavailable(
                "nepse_volatility_20d", "no NEPSE bars"
            )
            for lb in self.lookbacks:
                rel_nepse.append(
                    RelativePerformance(
                        symbol=symbol,
                        lookback=lb,
                        stock_return_pct=None,
                        bench_return_pct=None,
                        relative_pct=None,
                        benchmark_id=NEPSE_INDEX,
                        status=MetricStatus.UNAVAILABLE,
                    )
                )
        else:
            b_close = nepse.bars["close"].astype(float)
            trend = simple_trend_label(b_close)
            metrics["nepse_trend"] = MetricResult.ok(
                "nepse_trend",
                _TREND_SCORE.get(trend, 0.0),
                unit="label",
                trend_label=trend,
            )
            notes.append(f"NEPSE trend label: {trend}")
            nvol = realized_volatility(b_close, 20)
            if nvol is None:
                metrics["nepse_volatility_20d"] = MetricResult.insufficient(
                    "nepse_volatility_20d", need=21, have=len(b_close)
                )
            else:
                metrics["nepse_volatility_20d"] = MetricResult.ok(
                    "nepse_volatility_20d", nvol, period=20, unit="pct"
                )
            rel_nepse = self._rel_list(symbol, stock_close, work, nepse.bars, NEPSE_INDEX)
            for r in rel_nepse:
                if r.status == MetricStatus.OK and r.relative_pct is not None:
                    metrics[f"rs_nepse_{r.lookback}d"] = MetricResult.ok(
                        f"rs_nepse_{r.lookback}d", r.relative_pct, period=r.lookback, unit="pct"
                    )

        rel_sector: list[RelativePerformance] = []
        bench_id = sector_to_benchmark_id(sector_val) if sector_val else None
        if not bench_id:
            notes.append("no sector mapping — sector relative performance skipped")
            for lb in self.lookbacks:
                rel_sector.append(
                    RelativePerformance(
                        symbol=symbol,
                        lookback=lb,
                        stock_return_pct=None,
                        bench_return_pct=None,
                        relative_pct=None,
                        benchmark_id="SECTOR_UNKNOWN",
                        status=MetricStatus.UNAVAILABLE,
                    )
                )
        else:
            sec = self.benchmarks.get_series(bench_id)
            if sec.empty:
                notes.append(f"sector benchmark {bench_id} bars unavailable")
                for lb in self.lookbacks:
                    rel_sector.append(
                        RelativePerformance(
                            symbol=symbol,
                            lookback=lb,
                            stock_return_pct=None,
                            bench_return_pct=None,
                            relative_pct=None,
                            benchmark_id=bench_id,
                            status=MetricStatus.UNAVAILABLE,
                        )
                    )
            else:
                sec_trend = simple_trend_label(sec.bars["close"].astype(float))
                notes.append(f"sector {bench_id} trend: {sec_trend}")
                metrics["sector_trend"] = MetricResult.ok(
                    "sector_trend",
                    _TREND_SCORE.get(sec_trend, 0.0),
                    unit="label",
                    trend_label=sec_trend,
                    benchmark_id=bench_id,
                )
                rel_sector = self._rel_list(symbol, stock_close, work, sec.bars, bench_id)
                for r in rel_sector:
                    if r.status == MetricStatus.OK and r.relative_pct is not None:
                        metrics[f"rs_sector_{r.lookback}d"] = MetricResult.ok(
                            f"rs_sector_{r.lookback}d",
                            r.relative_pct,
                            period=r.lookback,
                            unit="pct",
                            benchmark_id=bench_id,
                        )

        breadth = compute_breadth(universe_frames) if universe_frames else None
        if not universe_frames:
            notes.append("breadth not computed — pass universe_frames to enable")

        return MarketContext(
            symbol=symbol,
            sector=sector_val,
            as_of=as_of,
            metrics=metrics,
            relative_vs_nepse=rel_nepse,
            relative_vs_sector=rel_sector,
            breadth=breadth,
            notes=notes,
        )

    def analyze_market(
        self,
        universe_frames: dict[str, pd.DataFrame],
    ) -> MarketContext:
        notes: list[str] = []
        metrics: dict[str, MetricResult] = {}
        as_of = datetime.now(timezone.utc)

        nepse = self.benchmarks.get_series(NEPSE_INDEX)
        if nepse.empty:
            notes.append("NEPSE index bars unavailable")
            metrics["nepse_trend"] = MetricResult.unavailable("nepse_trend")
        else:
            b_close = nepse.bars["close"].astype(float)
            if "timestamp" in nepse.bars.columns:
                ts = pd.to_datetime(nepse.bars["timestamp"].iloc[-1], utc=True)
                if not pd.isna(ts):
                    as_of = ts.to_pydatetime()
            trend = simple_trend_label(b_close)
            notes.append(f"NEPSE trend label: {trend}")
            metrics["nepse_trend"] = MetricResult.ok(
                "nepse_trend",
                _TREND_SCORE.get(trend, 0.0),
                unit="label",
                trend_label=trend,
            )
            for lb in self.lookbacks:
                ret = period_return(b_close, lb)
                key = f"nepse_return_{lb}d"
                if ret is None:
                    metrics[key] = MetricResult.insufficient(key, need=lb + 1, have=len(b_close))
                else:
                    metrics[key] = MetricResult.ok(key, ret, period=lb, unit="pct")
            nvol = realized_volatility(b_close, 20)
            if nvol is not None:
                metrics["nepse_volatility_20d"] = MetricResult.ok(
                    "nepse_volatility_20d", nvol, period=20, unit="pct"
                )

        breadth = compute_breadth(universe_frames) if universe_frames else None
        if not universe_frames:
            notes.append("no universe for breadth")

        return MarketContext(
            symbol=None,
            sector=None,
            as_of=as_of,
            metrics=metrics,
            breadth=breadth,
            notes=notes,
        )
