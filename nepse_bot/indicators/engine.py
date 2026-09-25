"""
Technical analysis engine.

Computes a full TechnicalSnapshot from an OHLCV DataFrame.
Designed so a later real-time path can call update_from_bar incrementally
without recalculating the entire universe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from nepse_bot.indicators.core import (
    accumulation_distribution,
    adx,
    atr,
    ema,
    macd,
    momentum,
    obv,
    relative_volume,
    roc,
    rsi,
    sma,
    stochastic,
    vwap,
)
from nepse_bot.indicators.levels import (
    detect_gaps,
    distance_from_extreme,
    rolling_high_low,
    simple_support_resistance,
    trend_structure,
)
from nepse_bot.indicators.types import MetricResult, MetricStatus


DEFAULT_PARAMS: dict[str, Any] = {
    "sma_periods": [20, 50, 200],
    "ema_periods": [9, 21, 50, 200],
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "atr_period": 14,
    "adx_period": 14,
    "stoch_k": 14,
    "stoch_d": 3,
    "roc_period": 12,
    "momentum_period": 10,
    "rvol_period": 20,
    "sr_lookback": 20,
    "week_52_bars": 252,
    "gap_min_pct": 0.5,
}


def _last_valid(series: pd.Series) -> tuple[Optional[float], int]:
    valid = series.dropna()
    if valid.empty:
        return None, 0
    return float(valid.iloc[-1]), len(valid)


@dataclass
class TechnicalSnapshot:
    symbol: str
    as_of: datetime
    bars_used: int
    price: Optional[float]
    metrics: dict[str, MetricResult] = field(default_factory=dict)
    series: dict[str, pd.Series] = field(default_factory=dict)
    flags: dict[str, bool] = field(default_factory=dict)
    structure: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def metric(self, name: str) -> MetricResult:
        return self.metrics.get(name, MetricResult.unavailable(name))

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "as_of": self.as_of.isoformat(),
            "bars_used": self.bars_used,
            "price": self.price,
            "metrics": {k: v.as_dict() for k, v in self.metrics.items()},
            "flags": self.flags,
            "structure": self.structure,
            "notes": self.notes,
        }

    def summary_lines(self) -> list[str]:
        lines = [
            f"{self.symbol}  price={self.price}  bars={self.bars_used}  as_of={self.as_of.isoformat()}",
        ]
        for name in sorted(self.metrics.keys()):
            m = self.metrics[name]
            if m.status == MetricStatus.OK and m.value is not None:
                lines.append(
                    f"  {name}: {m.value:.4f}" if abs(m.value) < 1e6 else f"  {name}: {m.value:.2f}"
                )
            else:
                lines.append(f"  {name}: N/A ({m.status.value})")
        if self.structure:
            lines.append(f"  trend: {self.structure.get('label')}")
        for k, v in self.flags.items():
            if v:
                lines.append(f"  flag: {k}")
        return lines


class TechnicalEngine:
    """Batch technical engine (Phase 3). Incremental path planned for real-time."""

    def __init__(self, params: Optional[dict[str, Any]] = None):
        self.params = {**DEFAULT_PARAMS, **(params or {})}

    def compute(
        self,
        df: pd.DataFrame,
        symbol: Optional[str] = None,
        *,
        include_series: bool = False,
    ) -> TechnicalSnapshot:
        if df is None or df.empty:
            sym = symbol or "UNKNOWN"
            return TechnicalSnapshot(
                symbol=sym,
                as_of=datetime.now(timezone.utc),
                bars_used=0,
                price=None,
                notes=["no OHLCV rows"],
            )

        work = df.copy()
        work.columns = [str(c).strip().lower() for c in work.columns]
        if "symbol" in work.columns and symbol is None:
            symbol = str(work["symbol"].iloc[-1])
        symbol = symbol or "UNKNOWN"

        for col in ("open", "high", "low", "close", "volume"):
            if col not in work.columns:
                raise ValueError(f"OHLCV frame missing column: {col}")

        work = work.sort_values("timestamp" if "timestamp" in work.columns else work.columns[0])
        work = work.reset_index(drop=True)

        o = work["open"].astype(float)
        h = work["high"].astype(float)
        l = work["low"].astype(float)
        c = work["close"].astype(float)
        v = work["volume"].astype(float)

        n = len(work)
        last_price = float(c.iloc[-1])
        as_of = datetime.now(timezone.utc)
        if "timestamp" in work.columns:
            ts = pd.to_datetime(work["timestamp"].iloc[-1], utc=True)
            if not pd.isna(ts):
                as_of = ts.to_pydatetime()

        metrics: dict[str, MetricResult] = {}
        series_out: dict[str, pd.Series] = {}
        flags: dict[str, bool] = {}
        notes: list[str] = []

        for p in self.params["sma_periods"]:
            s = sma(c, int(p))
            val, have = _last_valid(s)
            key = f"sma_{p}"
            if val is not None and have >= p:
                metrics[key] = MetricResult.ok(key, val, period=p, unit="price")
            else:
                metrics[key] = MetricResult.insufficient(key, need=p, have=n)
            if include_series:
                series_out[key] = s

        for p in self.params["ema_periods"]:
            s = ema(c, int(p))
            val, have = _last_valid(s)
            key = f"ema_{p}"
            if val is not None and n >= p:
                metrics[key] = MetricResult.ok(key, val, period=p, unit="price")
            else:
                metrics[key] = MetricResult.insufficient(key, need=p, have=n)
            if include_series:
                series_out[key] = s

        rp = int(self.params["rsi_period"])
        rsi_s = rsi(c, rp)
        val, _ = _last_valid(rsi_s)
        if val is not None and n > rp:
            metrics["rsi"] = MetricResult.ok("rsi", val, period=rp, unit="index")
        else:
            metrics["rsi"] = MetricResult.insufficient("rsi", need=rp + 1, have=n)
        if include_series:
            series_out["rsi"] = rsi_s

        mf, ms, msig = (
            int(self.params["macd_fast"]),
            int(self.params["macd_slow"]),
            int(self.params["macd_signal"]),
        )
        macd_line, signal_line, hist = macd(c, mf, ms, msig)
        for name, ser, need in (
            ("macd", macd_line, ms),
            ("macd_signal", signal_line, ms + msig),
            ("macd_hist", hist, ms + msig),
        ):
            val, _ = _last_valid(ser)
            if val is not None and n >= need:
                metrics[name] = MetricResult.ok(name, val, period=need)
            else:
                metrics[name] = MetricResult.insufficient(name, need=need, have=n)
            if include_series:
                series_out[name] = ser

        ap = int(self.params["atr_period"])
        atr_s = atr(h, l, c, ap)
        val, _ = _last_valid(atr_s)
        if val is not None and n > ap:
            metrics["atr"] = MetricResult.ok("atr", val, period=ap, unit="price")
            if last_price:
                metrics["atr_pct"] = MetricResult.ok(
                    "atr_pct", 100.0 * val / last_price, period=ap, unit="pct"
                )
        else:
            metrics["atr"] = MetricResult.insufficient("atr", need=ap + 1, have=n)
        if include_series:
            series_out["atr"] = atr_s

        adxp = int(self.params["adx_period"])
        adx_s, pdi, mdi = adx(h, l, c, adxp)
        for name, ser in (("adx", adx_s), ("plus_di", pdi), ("minus_di", mdi)):
            val, _ = _last_valid(ser)
            need = adxp * 2
            if val is not None and n >= need:
                metrics[name] = MetricResult.ok(name, val, period=adxp, unit="index")
            else:
                metrics[name] = MetricResult.insufficient(name, need=need, have=n)
            if include_series:
                series_out[name] = ser

        sk, sd = int(self.params["stoch_k"]), int(self.params["stoch_d"])
        k_s, d_s = stochastic(h, l, c, sk, sd)
        for name, ser, need in (("stoch_k", k_s, sk), ("stoch_d", d_s, sk + sd)):
            val, _ = _last_valid(ser)
            if val is not None and n >= need:
                metrics[name] = MetricResult.ok(name, val, period=need, unit="index")
            else:
                metrics[name] = MetricResult.insufficient(name, need=need, have=n)
            if include_series:
                series_out[name] = ser

        rocp = int(self.params["roc_period"])
        roc_s = roc(c, rocp)
        val, _ = _last_valid(roc_s)
        if val is not None and n > rocp:
            metrics["roc"] = MetricResult.ok("roc", val, period=rocp, unit="pct")
        else:
            metrics["roc"] = MetricResult.insufficient("roc", need=rocp + 1, have=n)

        mp = int(self.params["momentum_period"])
        mom_s = momentum(c, mp)
        val, _ = _last_valid(mom_s)
        if val is not None and n > mp:
            metrics["momentum"] = MetricResult.ok("momentum", val, period=mp, unit="price")
        else:
            metrics["momentum"] = MetricResult.insufficient("momentum", need=mp + 1, have=n)

        vwap_s = vwap(h, l, c, v)
        val, _ = _last_valid(vwap_s)
        if val is not None:
            metrics["vwap"] = MetricResult.ok("vwap", val, unit="price")
            metrics["price_vs_vwap_pct"] = MetricResult.ok(
                "price_vs_vwap_pct",
                100.0 * (last_price - val) / val if val else 0.0,
                unit="pct",
            )
        else:
            metrics["vwap"] = MetricResult.insufficient("vwap", need=1, have=n)

        rvp = int(self.params["rvol_period"])
        rvol_s = relative_volume(v, rvp)
        val, _ = _last_valid(rvol_s)
        if val is not None and n >= rvp:
            metrics["relative_volume"] = MetricResult.ok(
                "relative_volume", val, period=rvp, unit="ratio"
            )
            flags["unusual_volume"] = val >= 1.5
        else:
            metrics["relative_volume"] = MetricResult.insufficient(
                "relative_volume", need=rvp, have=n
            )

        obv_s = obv(c, v)
        val, _ = _last_valid(obv_s)
        if val is not None:
            metrics["obv"] = MetricResult.ok("obv", val, unit="volume")
        else:
            metrics["obv"] = MetricResult.insufficient("obv", need=2, have=n)

        ad_s = accumulation_distribution(h, l, c, v)
        val, _ = _last_valid(ad_s)
        if val is not None:
            metrics["acc_dist"] = MetricResult.ok("acc_dist", val)
        else:
            metrics["acc_dist"] = MetricResult.insufficient("acc_dist", need=1, have=n)

        if include_series:
            series_out["vwap"] = vwap_s
            series_out["relative_volume"] = rvol_s
            series_out["obv"] = obv_s
            series_out["acc_dist"] = ad_s

        w52 = int(self.params["week_52_bars"])
        hh52, ll52 = rolling_high_low(h, l, min(w52, n))
        high_52 = float(hh52.iloc[-1]) if n else None
        low_52 = float(ll52.iloc[-1]) if n else None
        all_high = float(h.max()) if n else None
        all_low = float(l.min()) if n else None

        if high_52 is not None:
            metrics["high_52w"] = MetricResult.ok("high_52w", high_52, unit="price")
            d = distance_from_extreme(last_price, high_52)
            if d is not None:
                metrics["dist_52w_high_pct"] = MetricResult.ok(
                    "dist_52w_high_pct", d, unit="pct"
                )
            flags["near_52w_high"] = abs(d) <= 2.0 if d is not None else False
            flags["new_52w_high"] = last_price >= high_52 * 0.9999
        else:
            metrics["high_52w"] = MetricResult.unavailable("high_52w")

        if low_52 is not None:
            metrics["low_52w"] = MetricResult.ok("low_52w", low_52, unit="price")
            d = distance_from_extreme(last_price, low_52)
            if d is not None:
                metrics["dist_52w_low_pct"] = MetricResult.ok(
                    "dist_52w_low_pct", d, unit="pct"
                )
            flags["near_52w_low"] = abs(d) <= 2.0 if d is not None else False
            flags["new_52w_low"] = last_price <= low_52 * 1.0001

        if all_high is not None:
            metrics["all_time_high"] = MetricResult.ok(
                "all_time_high", all_high, unit="price", source="series_max"
            )
            flags["new_all_time_high"] = last_price >= all_high * 0.9999
            notes.append(
                "all_time_high is max of available history only — not guaranteed exchange ATH"
            )
        if all_low is not None:
            metrics["all_time_low"] = MetricResult.ok(
                "all_time_low", all_low, unit="price", source="series_min"
            )

        sr = simple_support_resistance(h, l, c, int(self.params["sr_lookback"]))
        if sr["support"] is not None:
            metrics["support"] = MetricResult.ok("support", sr["support"], unit="price")
        else:
            metrics["support"] = MetricResult.insufficient("support", need=2, have=n)
        if sr["resistance"] is not None:
            metrics["resistance"] = MetricResult.ok(
                "resistance", sr["resistance"], unit="price"
            )
            if n >= 2 and last_price >= sr["resistance"] * 0.999:
                prev = float(c.iloc[-2])
                if prev < sr["resistance"]:
                    flags["breakout"] = True
            if n >= 2 and last_price <= (sr["support"] or 0) * 1.001 and sr["support"]:
                prev = float(c.iloc[-2])
                if prev > sr["support"]:
                    flags["breakdown"] = True
        else:
            metrics["resistance"] = MetricResult.insufficient("resistance", need=2, have=n)

        gaps = detect_gaps(o, h, l, c, float(self.params["gap_min_pct"]))
        last_gap = gaps.iloc[-1] if len(gaps) else None
        if last_gap is not None and not pd.isna(last_gap["gap_pct"]):
            metrics["gap_pct"] = MetricResult.ok(
                "gap_pct", float(last_gap["gap_pct"]), unit="pct"
            )
            flags["gap_up"] = bool(last_gap["gap_up"])
            flags["gap_down"] = bool(last_gap["gap_down"])
        else:
            metrics["gap_pct"] = MetricResult.insufficient("gap_pct", need=2, have=n)

        ema_fast_s = series_out.get("ema_9")
        ema_slow_s = series_out.get("ema_50")
        if ema_fast_s is None:
            ema_fast_s = ema(c, 9)
        if ema_slow_s is None:
            ema_slow_s = ema(c, 50)
        structure = trend_structure(c, h, l, ema_fast_s, ema_slow_s)

        for p in (50, 200):
            m = metrics.get(f"ema_{p}")
            if m and m.status == MetricStatus.OK and m.value is not None:
                flags[f"above_ema_{p}"] = last_price > m.value

        return TechnicalSnapshot(
            symbol=symbol,
            as_of=as_of,
            bars_used=n,
            price=last_price,
            metrics=metrics,
            series=series_out if include_series else {},
            flags=flags,
            structure=structure,
            notes=notes,
        )
