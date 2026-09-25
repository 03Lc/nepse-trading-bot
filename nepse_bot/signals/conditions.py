"""Evaluate individual conditions from technical / fundamental / market snapshots."""

from __future__ import annotations

from typing import Optional

from nepse_bot.fundamentals.engine import FundamentalSnapshot
from nepse_bot.indicators.engine import TechnicalSnapshot
from nepse_bot.indicators.types import MetricStatus
from nepse_bot.market_analysis.engine import MarketContext
from nepse_bot.signals.rules import RuleConfig
from nepse_bot.signals.types import ConditionResult, ConditionStatus


def _metric_val(snap, name: str):
    if hasattr(snap, "metric"):
        m = snap.metric(name)
    else:
        m = snap.metrics.get(name)
    if m is None or m.status != MetricStatus.OK or m.value is None:
        return None
    return float(m.value)


def eval_technical(
    tech: Optional[TechnicalSnapshot],
    cfg: RuleConfig,
) -> list[ConditionResult]:
    out: list[ConditionResult] = []
    if tech is None or tech.bars_used == 0:
        return [
            ConditionResult(
                id="tech_data",
                description="Technical data available",
                status=ConditionStatus.UNKNOWN,
                category="technical",
                detail="no technical snapshot",
            )
        ]

    price = tech.price

    ema50 = _metric_val(tech, "ema_50")
    if cfg.require_above_ema50:
        if ema50 is None or price is None:
            out.append(ConditionResult(
                "above_ema50", "Price above 50 EMA", ConditionStatus.UNKNOWN,
                "technical", "ema_50 or price unavailable",
            ))
        else:
            ok = price > ema50
            out.append(ConditionResult(
                "above_ema50", "Price above 50 EMA",
                ConditionStatus.PASSED if ok else ConditionStatus.FAILED,
                "technical", f"price={price:.2f} ema50={ema50:.2f}",
                value=price, threshold=ema50,
            ))

    ema200 = _metric_val(tech, "ema_200")
    if cfg.require_above_ema200:
        if ema200 is None or price is None:
            out.append(ConditionResult(
                "above_ema200", "Price above 200 EMA", ConditionStatus.UNKNOWN,
                "technical", "ema_200 or price unavailable",
            ))
        else:
            ok = price > ema200
            out.append(ConditionResult(
                "above_ema200", "Price above 200 EMA",
                ConditionStatus.PASSED if ok else ConditionStatus.FAILED,
                "technical", f"price={price:.2f} ema200={ema200:.2f}",
                value=price, threshold=ema200,
            ))
    elif ema200 is not None and price is not None:
        ok = price > ema200
        out.append(ConditionResult(
            "above_ema200", "Price above 200 EMA (optional)",
            ConditionStatus.PASSED if ok else ConditionStatus.FAILED,
            "technical", f"price={price:.2f} ema200={ema200:.2f}",
            value=price, threshold=ema200,
        ))

    rsi = _metric_val(tech, "rsi")
    if rsi is None:
        out.append(ConditionResult(
            "rsi_zone", f"RSI between {cfg.rsi_buy_min} and {cfg.rsi_buy_max}",
            ConditionStatus.UNKNOWN, "technical", "rsi unavailable",
        ))
    else:
        ok = cfg.rsi_buy_min <= rsi <= cfg.rsi_buy_max
        out.append(ConditionResult(
            "rsi_zone", f"RSI between {cfg.rsi_buy_min} and {cfg.rsi_buy_max}",
            ConditionStatus.PASSED if ok else ConditionStatus.FAILED,
            "technical", f"rsi={rsi:.1f}", value=rsi, threshold=cfg.rsi_buy_max,
        ))

    rvol = _metric_val(tech, "relative_volume")
    if rvol is None:
        out.append(ConditionResult(
            "relative_volume", f"Relative volume ≥ {cfg.min_relative_volume}x",
            ConditionStatus.UNKNOWN, "technical", "relative_volume unavailable",
        ))
    else:
        ok = rvol >= cfg.min_relative_volume
        out.append(ConditionResult(
            "relative_volume", f"Relative volume ≥ {cfg.min_relative_volume}x",
            ConditionStatus.PASSED if ok else ConditionStatus.FAILED,
            "technical", f"rvol={rvol:.2f}x", value=rvol, threshold=cfg.min_relative_volume,
        ))

    if cfg.prefer_breakout:
        brk = bool(tech.flags.get("breakout"))
        out.append(ConditionResult(
            "breakout", "Breakout detected",
            ConditionStatus.PASSED if brk else ConditionStatus.FAILED,
            "technical", "flag breakout=True" if brk else "no breakout flag",
        ))

    adx = _metric_val(tech, "adx")
    if adx is None:
        out.append(ConditionResult(
            "adx_trend", f"ADX ≥ {cfg.adx_trend_min}",
            ConditionStatus.UNKNOWN, "technical", "adx unavailable",
        ))
    else:
        ok = adx >= cfg.adx_trend_min
        out.append(ConditionResult(
            "adx_trend", f"ADX ≥ {cfg.adx_trend_min}",
            ConditionStatus.PASSED if ok else ConditionStatus.FAILED,
            "technical", f"adx={adx:.1f}", value=adx, threshold=cfg.adx_trend_min,
        ))

    label = (tech.structure or {}).get("label")
    if label in ("uptrend", "bullish_bias"):
        out.append(ConditionResult(
            "trend_structure", "Bullish trend structure",
            ConditionStatus.PASSED, "technical", f"structure={label}",
        ))
    elif label in ("downtrend", "bearish_bias"):
        out.append(ConditionResult(
            "trend_structure", "Bullish trend structure",
            ConditionStatus.FAILED, "technical", f"structure={label}",
        ))
    else:
        out.append(ConditionResult(
            "trend_structure", "Bullish trend structure",
            ConditionStatus.UNKNOWN if not label else ConditionStatus.FAILED,
            "technical", f"structure={label or 'unknown'}",
        ))

    if tech.flags.get("breakdown"):
        out.append(ConditionResult(
            "no_breakdown", "No breakdown flag", ConditionStatus.FAILED,
            "technical", "breakdown flag set",
        ))
    else:
        out.append(ConditionResult(
            "no_breakdown", "No breakdown flag", ConditionStatus.PASSED,
            "technical", "ok",
        ))

    if rsi is not None and rsi >= cfg.rsi_overbought:
        out.append(ConditionResult(
            "not_overbought", f"RSI below overbought ({cfg.rsi_overbought})",
            ConditionStatus.FAILED, "technical", f"rsi={rsi:.1f}",
            value=rsi, threshold=cfg.rsi_overbought,
        ))
    elif rsi is not None:
        out.append(ConditionResult(
            "not_overbought", f"RSI below overbought ({cfg.rsi_overbought})",
            ConditionStatus.PASSED, "technical", f"rsi={rsi:.1f}",
            value=rsi, threshold=cfg.rsi_overbought,
        ))

    return out


def eval_fundamental(
    fund: Optional[FundamentalSnapshot],
    cfg: RuleConfig,
) -> list[ConditionResult]:
    out: list[ConditionResult] = []
    if fund is None:
        return [
            ConditionResult(
                "fund_data", "Fundamental data available", ConditionStatus.UNKNOWN,
                "fundamental", "no fundamental snapshot",
            )
        ]

    def check_positive(metric_name: str, desc: str, enabled: bool) -> None:
        if not enabled:
            return
        m = fund.metric(metric_name)
        if m.status != MetricStatus.OK or m.value is None:
            out.append(ConditionResult(
                metric_name, desc, ConditionStatus.UNKNOWN,
                "fundamental", f"{metric_name} unavailable",
            ))
        else:
            ok = m.value > 0
            out.append(ConditionResult(
                metric_name, desc,
                ConditionStatus.PASSED if ok else ConditionStatus.FAILED,
                "fundamental", f"{metric_name}={m.value:.2f}", value=m.value, threshold=0.0,
            ))

    check_positive("eps_growth_pct", "EPS growth positive", cfg.require_positive_eps_growth)
    check_positive("roe", "ROE positive", cfg.require_positive_roe)

    for name, desc in (("eps_growth_pct", "EPS growth positive (info)"), ("roe", "ROE positive (info)")):
        if any(c.id == name for c in out):
            continue
        m = fund.metric(name)
        if m.status == MetricStatus.OK and m.value is not None:
            out.append(ConditionResult(
                f"info_{name}", desc,
                ConditionStatus.PASSED if m.value > 0 else ConditionStatus.FAILED,
                "fundamental", f"{name}={m.value:.2f}", value=m.value,
            ))

    pe = fund.metric("pe")
    if cfg.max_pe is not None:
        if pe.status != MetricStatus.OK or pe.value is None:
            out.append(ConditionResult(
                "pe_cap", f"P/E ≤ {cfg.max_pe}", ConditionStatus.UNKNOWN,
                "valuation", "pe unavailable",
            ))
        else:
            ok = pe.value <= cfg.max_pe
            out.append(ConditionResult(
                "pe_cap", f"P/E ≤ {cfg.max_pe}",
                ConditionStatus.PASSED if ok else ConditionStatus.FAILED,
                "valuation", f"pe={pe.value:.2f}", value=pe.value, threshold=cfg.max_pe,
            ))

    pb = fund.metric("pb")
    if cfg.max_pb is not None:
        if pb.status != MetricStatus.OK or pb.value is None:
            out.append(ConditionResult(
                "pb_cap", f"P/B ≤ {cfg.max_pb}", ConditionStatus.UNKNOWN,
                "valuation", "pb unavailable",
            ))
        else:
            ok = pb.value <= cfg.max_pb
            out.append(ConditionResult(
                "pb_cap", f"P/B ≤ {cfg.max_pb}",
                ConditionStatus.PASSED if ok else ConditionStatus.FAILED,
                "valuation", f"pb={pb.value:.2f}", value=pb.value, threshold=cfg.max_pb,
            ))

    if pe.status == MetricStatus.OK and pe.value is not None and cfg.max_pe is None:
        out.append(ConditionResult(
            "info_pe", "P/E available (no max gate configured)", ConditionStatus.PASSED,
            "valuation", f"pe={pe.value:.2f}", value=pe.value,
        ))
    if pb.status == MetricStatus.OK and pb.value is not None and cfg.max_pb is None:
        out.append(ConditionResult(
            "info_pb", "P/B available (no max gate configured)", ConditionStatus.PASSED,
            "valuation", f"pb={pb.value:.2f}", value=pb.value,
        ))

    return out


def eval_market(
    market: Optional[MarketContext],
    cfg: RuleConfig,
) -> list[ConditionResult]:
    out: list[ConditionResult] = []
    if market is None:
        return [
            ConditionResult(
                "market_data", "Market context available", ConditionStatus.UNKNOWN,
                "market", "no market snapshot",
            )
        ]

    if cfg.prefer_outperform_nepse_20d:
        rs = None
        for r in market.relative_vs_nepse:
            if r.lookback == 20 and r.relative_pct is not None:
                rs = r.relative_pct
                break
        if rs is None:
            m = market.metrics.get("rs_nepse_20d")
            if m and m.status == MetricStatus.OK and m.value is not None:
                rs = m.value
        if rs is None:
            out.append(ConditionResult(
                "outperform_nepse_20d", "Outperforming NEPSE over 20d",
                ConditionStatus.UNKNOWN, "market", "rs_nepse_20d unavailable",
            ))
        else:
            ok = rs > 0
            out.append(ConditionResult(
                "outperform_nepse_20d", "Outperforming NEPSE over 20d",
                ConditionStatus.PASSED if ok else ConditionStatus.FAILED,
                "market", f"rs_nepse_20d={rs:+.2f}pp", value=rs, threshold=0.0,
            ))

    if cfg.avoid_strong_downtrend_market:
        trend_m = market.metrics.get("nepse_trend")
        label = None
        if trend_m and trend_m.extra:
            label = trend_m.extra.get("trend_label")
        if label is None and market.notes:
            for n in market.notes:
                if n.startswith("NEPSE trend label:"):
                    label = n.split(":", 1)[-1].strip()
        if label is None:
            out.append(ConditionResult(
                "market_not_downtrend", "NEPSE not in strong downtrend",
                ConditionStatus.UNKNOWN, "market", "nepse trend unavailable",
            ))
        else:
            ok = label not in ("downtrend",)
            out.append(ConditionResult(
                "market_not_downtrend", "NEPSE not in strong downtrend",
                ConditionStatus.PASSED if ok else ConditionStatus.FAILED,
                "market", f"nepse_trend={label}",
            ))

    return out
