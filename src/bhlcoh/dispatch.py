"""Electricity cost per MWh of heat from the electrolysis-dispatch package (``bhed``)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, Sequence

import numpy as np

from bhed.design import design_point
from bhed.metrics import summarise
from bhed.prices import load_prices
from bhed.sizing import storage_hours_to_mol
from bhed.strategies import run_strategy

PRICE_FILE = Path(__file__).resolve().parents[2] / "data" / "de_lu_da_hourly.csv.gz"
ELECTROLYSER_CONFIGS = ("oxy_partial", "oxy_full", "oxy_none_elec")


@lru_cache(maxsize=1)
def prices() -> np.ndarray:
    return load_prices(PRICE_FILE).values


def run_dispatch(config: str, capacity_factor: float, storage_h: float,
                 strategy: str = "O4_rolling_day_ahead",
                 price_series: Sequence[float] | None = None) -> Dict[str, float]:
    """Run one dispatch case; return per-MWh_heat quantities used by the LCOH model."""
    p = np.asarray(prices() if price_series is None else price_series, dtype=float)
    dp = design_point(config)
    cap_w = dp.el_electrolyser_mw * 1e6 * capacity_factor
    h2_mol, o2_mol = storage_hours_to_mol(dp, storage_h)
    df = run_strategy(config, dp, p, strategy, cap_w, h2_mol, o2_mol)
    m = summarise(df, cap_w, heat_mw=dp.heat_mw)
    heat = m["heat_mwh"]
    return {
        "config": config, "strategy": strategy, "capacity_factor": capacity_factor,
        "storage_h": storage_h, "electrolyser_mw": cap_w / 1e6,
        "h2_storage_kg": h2_mol * 2.01588e-3, "o2_storage_kg": o2_mol * 31.998e-3,
        "electricity_eur_per_mwh_heat": m["electricity_cost_eur"] / heat,
        "electricity_mwh_per_mwh_heat": m["electricity_mwh"] / heat,
        "electrolyser_flh_frac": m["electrolyser_flh"] / m["hours"],
        "o2_vent_kg_per_mwh_heat": m["o2_vent_kg"] / heat,
        "h2_unserved_kg": m["h2_unserved_kg"],
        "vwap_eur_mwh": m["volume_weighted_price_eur_mwh"],
    }
