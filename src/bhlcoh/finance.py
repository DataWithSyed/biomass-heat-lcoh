"""Discounting helpers (real terms, end-of-year cash flows)."""
from __future__ import annotations


def crf(rate: float, years: int) -> float:
    """Capital recovery factor r(1+r)^n / ((1+r)^n - 1); 1/n at r = 0."""
    if years <= 0:
        raise ValueError("years must be positive")
    if abs(rate) < 1e-12:
        return 1.0 / years
    f = (1.0 + rate) ** years
    return rate * f / (f - 1.0)


def pv_single(amount: float, rate: float, year: float) -> float:
    """Present value of a single payment in ``year``."""
    return amount / (1.0 + rate) ** year


def annualise(capex: float, rate: float, years: int) -> float:
    """Equivalent annual cost of an up-front investment."""
    return capex * crf(rate, years)


def replacement_annuity(cost: float, rate: float, years: int, interval_years: float) -> float:
    """Annuity of repeated replacements every ``interval_years`` inside the lifetime.

    Replacements falling at or after the end of life are not counted (no salvage value).
    """
    if interval_years <= 0:
        return 0.0
    pv = 0.0
    k = 1
    while k * interval_years < years - 1e-9:
        pv += pv_single(cost, rate, k * interval_years)
        k += 1
    return pv * crf(rate, years)
