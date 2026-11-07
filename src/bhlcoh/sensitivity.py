"""One-at-a-time (tornado) and Monte Carlo sensitivity of LCOH and of the gap to natural gas."""
from __future__ import annotations

from dataclasses import replace
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd

from .chains import ChainInputs, lcoh_breakdown
from .costs import CostInputs, parameter_ranges
from .reference import ng_lcoh


def gap(ch: ChainInputs, c: CostInputs) -> float:
    """Biomass-chain LCOH minus natural-gas heat cost (EUR/MWh_heat); < 0 means biomass wins."""
    return lcoh_breakdown(ch, c)["total"] - ng_lcoh(c)["total"]


def tornado(ch: ChainInputs, base: CostInputs, ranges: Dict[str, tuple] | None = None,
            metric: str = "gap") -> pd.DataFrame:
    """Swing of ``metric`` ('gap' or 'lcoh') when each parameter moves to its low/high value."""
    ranges = ranges or parameter_ranges()
    f = gap if metric == "gap" else (lambda ch_, c_: lcoh_breakdown(ch_, c_)["total"])
    y0 = f(ch, base)
    rows = []
    for name, (lo, hi, label, source) in ranges.items():
        y_lo = f(ch, replace(base, **{name: type(getattr(base, name))(lo)}))
        y_hi = f(ch, replace(base, **{name: type(getattr(base, name))(hi)}))
        rows.append(dict(parameter=name, low=lo, central=getattr(base, name), high=hi,
                         y_low=y_lo, y_high=y_hi, swing=abs(y_hi - y_lo), base=y0,
                         label=label, source=source))
    return pd.DataFrame(rows).sort_values("swing", ascending=False).reset_index(drop=True)


def sample_inputs(base: CostInputs, n: int, seed: int = 7,
                  ranges: Dict[str, tuple] | None = None) -> List[CostInputs]:
    """Independent triangular draws (low, central, high) for every ranged parameter."""
    ranges = ranges or parameter_ranges()
    rng = np.random.default_rng(seed)
    cols = {}
    for name, (lo, hi, _, _) in ranges.items():
        mode = float(getattr(base, name))
        a, b = min(lo, hi, mode), max(lo, hi, mode)
        cols[name] = rng.triangular(a, mode, b, size=n) if b > a else np.full(n, mode)
    out = []
    for i in range(n):
        kw = {k: v[i] for k, v in cols.items()}
        out.append(replace(base, **kw))
    return out


def monte_carlo(chains: Iterable[ChainInputs], base: CostInputs, n: int = 10_000,
                seed: int = 7) -> pd.DataFrame:
    """LCOH of every chain and of NG for the same parameter draws (common random numbers)."""
    draws = sample_inputs(base, n, seed)
    chains = list(chains)
    rec = {"ng": np.empty(n)}
    for ch in chains:
        rec[ch.config] = np.empty(n)
    for i, c in enumerate(draws):
        rec["ng"][i] = ng_lcoh(c)["total"]
        for ch in chains:
            rec[ch.config][i] = lcoh_breakdown(ch, c)["total"]
    df = pd.DataFrame(rec)
    df["co2_eur_t"] = [c.co2_eur_t for c in draws]
    df["gas_eur_mwh_gcv"] = [c.gas_eur_mwh_gcv for c in draws]
    return df


def mc_summary(df: pd.DataFrame, chains: Iterable[str]) -> pd.DataFrame:
    rows = []
    for k in list(chains) + ["ng"]:
        x = df[k].values
        rows.append(dict(chain=k, p10=np.percentile(x, 10), p50=np.percentile(x, 50),
                         p90=np.percentile(x, 90), mean=x.mean(),
                         p_cheaper_than_ng=float(np.mean(x < df["ng"].values)) if k != "ng"
                         else np.nan))
    return pd.DataFrame(rows)
