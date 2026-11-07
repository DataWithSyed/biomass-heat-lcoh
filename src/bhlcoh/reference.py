"""Natural-gas reference (existing furnace) and break-even prices."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict

from biomass_heat import Plant, natural_gas

from .costs import CostInputs


@lru_cache(maxsize=4)
def ng_design(heat_mw: float = 10.0, t_process_c: float = 1000.0) -> Dict[str, float]:
    dp = Plant("air").design_point(heat_mw * 1e6, t_process_c + 273.15)
    ng = natural_gas()
    return {"ng_mwh_lhv_per_mwh": dp["ng_MWh_per_MWh"],
            "co2_t_per_mwh": dp["ng_avoided_co2_t_per_MWh"],
            "gcv_over_ncv": ng.hhv_power / ng.lhv_power}


def ng_lcoh(c: CostInputs, heat_mw: float = 10.0, t_process_c: float = 1000.0) -> Dict[str, float]:
    """NG heat cost: fuel (Eurostat price is per kWh GCV) + EU ETS CO2. Furnace already exists."""
    d = ng_design(heat_mw, t_process_c)
    fuel = d["ng_mwh_lhv_per_mwh"] * d["gcv_over_ncv"] * c.gas_eur_mwh_gcv
    co2 = d["co2_t_per_mwh"] * c.co2_eur_t
    return {"fuel": fuel, "co2": co2, "total": fuel + co2}


def breakeven_co2_price(lcoh_bio: float, c: CostInputs) -> float:
    """EUA price at which NG heat costs the same as the biomass chain (biogenic CO2 = 0)."""
    d = ng_design()
    fuel = d["ng_mwh_lhv_per_mwh"] * d["gcv_over_ncv"] * c.gas_eur_mwh_gcv
    return (lcoh_bio - fuel) / d["co2_t_per_mwh"]


def breakeven_gas_price(lcoh_bio: float, c: CostInputs) -> float:
    """Gas price (EUR/MWh GCV, excl. taxes) at which NG heat equals the biomass chain."""
    d = ng_design()
    co2 = d["co2_t_per_mwh"] * c.co2_eur_t
    return (lcoh_bio - co2) / (d["ng_mwh_lhv_per_mwh"] * d["gcv_over_ncv"])
