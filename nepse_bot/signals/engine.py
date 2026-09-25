"""Signal engine: combine condition results into an explainable SignalReport."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from nepse_bot.fundamentals.engine import FundamentalSnapshot
from nepse_bot.indicators.engine import TechnicalSnapshot
from nepse_bot.indicators.types import MetricStatus
from nepse_bot.market_analysis.engine import MarketContext
from nepse_bot.signals.conditions import eval_fundamental, eval_market, eval_technical
from nepse_bot.signals.rules import RuleConfig, default_rule_config
from nepse_bot.signals.types import ConditionResult, ConditionStatus, SignalState


@dataclass
class SignalReport:
    symbol: str
    state: SignalState
    price: Optional[float]
    as_of: datetime
    conditions: list[ConditionResult] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    unknown: int = 0
    warnings: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    risk: dict[str, Any] = field(default_factory=dict)
    config_snapshot: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "state": self.state.value,
            "price": self.price,
            "as_of": self.as_of.isoformat(),
            "passed": self.passed,
            "failed": self.failed,
            "unknown": self.unknown,
            "conditions": [c.as_dict() for c in self.conditions],
            "warnings": self.warnings,
            "reasons": self.reasons,
            "risk": self.risk,
            "config_snapshot": self.config_snapshot,
        }

    def summary_lines(self) -> list[str]:
        lines = [
            f"{self.symbol}",
            f"SIGNAL: {self.state.value}",
            f"Price: {self.price}",
            f"As of: {self.as_of.isoformat()}",
            f"Conditions: {self.passed} passed, {self.failed} failed, {self.unknown} unknown",
            "",
        ]
        by_cat: dict[str, list[ConditionResult]] = {}
        for c in self.conditions:
            by_cat.setdefault(c.category, []).append(c)
        for cat in ("technical", "fundamental", "valuation", "market", "risk"):
            items = by_cat.get(cat)
            if not items:
                continue
            lines.append(f"{cat.title()}:")
            for c in items:
                extra = f" — {c.detail}" if c.detail else ""
                lines.append(f"  {c.mark} {c.description}{extra}")
            lines.append("")
        if self.risk:
            lines.append("Risk (illustrative, not advice):")
            for k, v in self.risk.items():
                lines.append(f"  {k}: {v}")
            lines.append("")
        if self.reasons:
            lines.append("Reasons:")
            for r in self.reasons:
                lines.append(f"  • {r}")
        if self.warnings:
            lines.append("Warnings:")
            for w in self.warnings:
                lines.append(f"  ⚠ {w}")
        lines.append("")
        lines.append(
            "This is not a profit guarantee. Thresholds are configurable and must be backtested."
        )
        return lines


class SignalEngine:
    def __init__(self, config: Optional[RuleConfig] = None):
        self.config = config or default_rule_config()

    def evaluate(
        self,
        symbol: str,
        *,
        technical: Optional[TechnicalSnapshot] = None,
        fundamental: Optional[FundamentalSnapshot] = None,
        market: Optional[MarketContext] = None,
        price: Optional[float] = None,
    ) -> SignalReport:
        cfg = self.config
        conditions: list[ConditionResult] = []
        conditions.extend(eval_technical(technical, cfg))
        conditions.extend(eval_fundamental(fundamental, cfg))
        conditions.extend(eval_market(market, cfg))

        passed = sum(1 for c in conditions if c.status == ConditionStatus.PASSED)
        failed = sum(1 for c in conditions if c.status == ConditionStatus.FAILED)
        unknown = sum(1 for c in conditions if c.status == ConditionStatus.UNKNOWN)

        warnings: list[str] = []
        reasons: list[str] = []

        if unknown > 0:
            warnings.append(
                f"{unknown} condition(s) unknown due to missing data — "
                "do not treat unknowns as confirmations"
            )

        state = self._classify(passed, failed, conditions, cfg, reasons, warnings)

        px = price
        if px is None and technical is not None:
            px = technical.price
        if px is None and fundamental is not None:
            px = fundamental.price

        risk = self._risk_levels(px, technical, cfg)

        as_of = datetime.now(timezone.utc)
        if technical is not None:
            as_of = technical.as_of
        elif market is not None:
            as_of = market.as_of

        reasons.insert(
            0,
            f"{passed} conditions satisfied, {failed} failed, {unknown} unknown",
        )

        return SignalReport(
            symbol=symbol.upper(),
            state=state,
            price=px,
            as_of=as_of,
            conditions=conditions,
            passed=passed,
            failed=failed,
            unknown=unknown,
            warnings=warnings,
            reasons=reasons,
            risk=risk,
            config_snapshot=cfg.as_dict(),
        )

    def _classify(
        self,
        passed: int,
        failed: int,
        conditions: list[ConditionResult],
        cfg: RuleConfig,
        reasons: list[str],
        warnings: list[str],
    ) -> SignalState:
        stress_ids = {"no_breakdown", "not_overbought", "trend_structure", "above_ema50"}
        stress_fails = sum(
            1
            for c in conditions
            if c.id in stress_ids and c.status == ConditionStatus.FAILED
        )
        breakdown = any(
            c.id == "no_breakdown" and c.status == ConditionStatus.FAILED for c in conditions
        )

        if breakdown or (
            stress_fails >= 3 and failed >= cfg.sell_setup_min_failed_bullish
        ):
            reasons.append("Multiple bullish conditions failed and/or breakdown present")
            return SignalState.SELL_EXIT_SETUP

        if passed >= cfg.buy_setup_min_passed and failed <= cfg.buy_setup_max_failed:
            reasons.append(
                f"Met buy-setup thresholds "
                f"(passed≥{cfg.buy_setup_min_passed}, failed≤{cfg.buy_setup_max_failed})"
            )
            return SignalState.BUY_SETUP

        if passed >= cfg.watch_min_passed:
            reasons.append(
                f"Partial setup (passed≥{cfg.watch_min_passed}) — monitoring"
            )
            return SignalState.WATCH

        if passed > 0 and failed < passed:
            reasons.append("Mixed conditions — no clear new setup")
            return SignalState.HOLD

        reasons.append("Insufficient confirming conditions")
        return SignalState.NO_SIGNAL

    def _risk_levels(
        self,
        price: Optional[float],
        technical: Optional[TechnicalSnapshot],
        cfg: RuleConfig,
    ) -> dict[str, Any]:
        if price is None:
            return {
                "entry": "N/A",
                "stop": "N/A — price unavailable",
                "target_zone": "N/A",
            }
        atr = None
        if technical is not None:
            m = technical.metric("atr")
            if m.status == MetricStatus.OK and m.value is not None:
                atr = m.value
        if atr is None or atr <= 0:
            return {
                "entry": round(price, 2),
                "stop": "N/A — ATR unavailable",
                "target_zone": "N/A — ATR unavailable",
            }
        stop = price - cfg.atr_stop_mult * atr
        target = price + cfg.atr_target_mult * atr
        return {
            "entry": round(price, 2),
            "stop": round(stop, 2),
            "target_zone": round(target, 2),
            "atr": round(atr, 4),
            "note": (
                f"Stop ≈ entry − {cfg.atr_stop_mult}×ATR; "
                f"target ≈ entry + {cfg.atr_target_mult}×ATR (illustrative only)"
            ),
        }
