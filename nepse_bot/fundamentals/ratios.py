"""
Safe ratio helpers — return None when inputs are missing or invalid.
Never substitute zeros for missing denominators.
"""

from __future__ import annotations

from typing import Optional


def safe_div(num: Optional[float], den: Optional[float]) -> Optional[float]:
    if num is None or den is None:
        return None
    if den == 0:
        return None
    return float(num) / float(den)


def growth_pct(current: Optional[float], prior: Optional[float]) -> Optional[float]:
    if current is None or prior is None:
        return None
    if prior == 0:
        return None
    return 100.0 * (float(current) - float(prior)) / float(prior)


def margin_pct(part: Optional[float], whole: Optional[float]) -> Optional[float]:
    r = safe_div(part, whole)
    return None if r is None else 100.0 * r
