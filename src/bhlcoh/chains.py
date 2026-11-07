"""Per-chain technical inputs (plant model + dispatch) and the LCOH cost build-up."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Optional

import numpy as np

from biomass_heat import Plant

from . import costs as C
from .costs import CostInputs
from .finance import annualise, replacement_annuity

LABELS = {
    "air": "Air gasification",
    "oxy_none": "Oxyfuel, O2 from ASU",
    "oxy_partial": "Oxyfuel + partial methanation",
    "oxy_full": "Oxyfuel + full methanation",
    "oxy_none_elec": "Oxyfuel, O2 from electrolyser, H2 blended",
    "steam_dfb": "Steam gasification (DFB)",
}
METHANATION = {"oxy_partial", "oxy_full"}


@dataclass(frozen=True)
class ChainInputs:
    config: str
    label: str
    heat_mw: float
    biomass_lhv_mw: float
    biomass_mwh_per_mwh: float
    fuel_lhv_mw: float
    has_methanation: bool
    asu_o2_kg_h: float
    electrolyser_mw: float
    capacity_factor: float
    storage_h: float
    h2_storage_kg: float
    o2_storage_kg: float
    electrolyser_flh_frac: float
    electricity_eur_per_mwh_heat: float   # at real DA prices, before multiplier/adder
    electricity_mwh_per_mwh_heat: float
    o2_vent_kg_per_mwh_heat: float
    strategy: str

    def asdict(self) -> dict:
        return asdict(self)


def chain_inputs(config: str, mean_price: float, dispatch: Optional[Dict] = None,
                 heat_mw: float = 10.0, t_process_c: float = 1000.0) -> ChainInputs:
    """Build inputs from the plant-model design point; electrolyser chains need ``dispatch``."""
    dp = Plant(config).design_point(heat_mw * 1e6, t_process_c + 273.15)
    if dispatch is None:
        if dp["el_electrolyser_MW"] > 1e-6:
            raise ValueError(f"{config} has an electrolyser: pass a dispatch result")
        el = dp["electricity_MWh_per_MWh"]
        disp = dict(electrolyser_mw=0.0, capacity_factor=0.0, storage_h=0.0, h2_storage_kg=0.0,
                    o2_storage_kg=0.0, electrolyser_flh_frac=0.0,
                    electricity_eur_per_mwh_heat=el * mean_price,
                    electricity_mwh_per_mwh_heat=el, o2_vent_kg_per_mwh_heat=0.0,
                    strategy="flat")
    else:
        disp = {k: dispatch[k] for k in ("electrolyser_mw", "capacity_factor", "storage_h",
                                         "h2_storage_kg", "o2_storage_kg",
                                         "electrolyser_flh_frac", "electricity_eur_per_mwh_heat",
                                         "electricity_mwh_per_mwh_heat",
                                         "o2_vent_kg_per_mwh_heat", "strategy")}
    return ChainInputs(config=config, label=LABELS.get(config, config), heat_mw=heat_mw,
                       biomass_lhv_mw=dp["biomass_lhv_MW"],
                       biomass_mwh_per_mwh=dp["biomass_MWh_per_MWh"],
                       fuel_lhv_mw=dp["fuel_lhv_MW"], has_methanation=config in METHANATION,
                       asu_o2_kg_h=dp["o2_asu_kg_h"], **disp)


# --- CAPEX blocks (EUR 2025) ---------------------------------------------------------------------
def capex_gas_island(ch: ChainInputs, c: CostInputs) -> float:
    p_ref_in = C.THUNMAN_P_REF_MW / C.THUNMAN_ETA
    s = ch.biomass_lhv_mw / p_ref_in
    gas = C.section_sum(C.GAS_ISLAND_SECTIONS)
    proc = gas * s ** c.sf_process
    aux = C.THUNMAN_AUX_PROJECT_REF_KSEK * gas / C.THUNMAN_PROCESS_TOTAL_KSEK \
        * s ** c.sf_aux * c.aux_project_mult
    ext = C.THUNMAN_EXT_FUEL_DRYER_KSEK * (ch.biomass_lhv_mw /
                                           (C.THUNMAN_EXT_P_REF_MW / C.THUNMAN_ETA)) \
        ** C.THUNMAN_SF_EXT
    return C.ksek2014_to_eur2025(proc + aux + ext)


def capex_methanation(ch: ChainInputs, c: CostInputs) -> float:
    if not ch.has_methanation:
        return 0.0
    goetz = C.to_eur2025(C.goetz_methanation_eur2014_per_kw(ch.fuel_lhv_mw)
                         * ch.fuel_lhv_mw * 1e3, 2014)
    s = ch.fuel_lhv_mw / C.THUNMAN_P_REF_MW
    meth = C.section_sum(C.METHANATION_SECTIONS)
    proc = meth * s ** c.sf_process
    aux = C.THUNMAN_AUX_PROJECT_REF_KSEK * meth / C.THUNMAN_PROCESS_TOTAL_KSEK \
        * s ** c.sf_aux * c.aux_project_mult
    thunman = C.ksek2014_to_eur2025(proc + aux)
    w = c.methanation_goetz_weight
    return (1.0 - w) * thunman + w * goetz


def capex_electrolyser(ch: ChainInputs, c: CostInputs) -> float:
    return C.to_eur2025(c.electrolyser_eur2016_kw, 2016) * ch.electrolyser_mw * 1e3


def capex_storage(ch: ChainInputs, c: CostInputs) -> float:
    if ch.h2_storage_kg <= 0 and ch.o2_storage_kg <= 0:
        return 0.0
    h2_kg = C.to_eur2025(c.h2_storage_eur2014_kg, 2014)
    o2_kg = h2_kg * 2.01588 / 31.998       # assumption: same vessel cost per mol stored
    comp = C.to_eur2025(C.GOETZ_COMPRESSOR_MEUR * 1e6 / C.GOETZ_ELECTROLYSIS_MW, 2014) \
        * ch.electrolyser_mw
    return ch.h2_storage_kg * h2_kg + ch.o2_storage_kg * o2_kg + comp


def capex_asu(ch: ChainInputs, c: CostInputs) -> float:
    return c.asu_eur_per_kg_h * ch.asu_o2_kg_h


def thunman_share(ch: ChainInputs) -> float:
    keys = C.GAS_ISLAND_SECTIONS + (C.METHANATION_SECTIONS if ch.has_methanation else ())
    return C.section_sum(keys) / C.THUNMAN_PROCESS_TOTAL_KSEK


def lcoh_breakdown(ch: ChainInputs, c: CostInputs) -> Dict[str, float]:
    """LCOH components in EUR per MWh of process heat (real EUR 2025)."""
    r, n = c.discount_rate, c.lifetime_y
    heat = ch.heat_mw * c.flh
    cap_gas = capex_gas_island(ch, c)
    cap_meth = capex_methanation(ch, c)
    cap_el = capex_electrolyser(ch, c)
    cap_sto = capex_storage(ch, c)
    cap_asu = capex_asu(ch, c)
    out = {
        "capex_gasification": annualise(cap_gas, r, n) / heat,
        "capex_methanation": annualise(cap_meth, r, n) / heat,
        "capex_development": annualise(C.THUNMAN_DEV_FRAC * (cap_gas + cap_meth), r, n) / heat,
        "capex_electrolyser": annualise(cap_el, r, n) / heat,
        "capex_storage": annualise(cap_sto, r, n) / heat,
        "capex_asu": annualise(cap_asu, r, n) / heat,
    }
    # Thunman O&M (allocated to the sections present), scaled on product-gas LHV capacity
    share = thunman_share(ch)
    s = ch.fuel_lhv_mw / C.THUNMAN_P_REF_MW
    ref_mwh = C.THUNMAN_P_REF_MW * C.THUNMAN_FLH
    sek = lambda x: C.ksek2014_to_eur2025(x / 1e3)  # SEK -> EUR 2025
    fixed = {}
    for k in ("personnel", "maintenance", "other"):
        annual_ref = C.THUNMAN_OPEX_SEK_MWH[k] * ref_mwh
        fixed[k] = sek(annual_ref * s ** C.THUNMAN_OPEX_SF[k]) * share
    fixed["personnel"] *= c.personnel_mult
    out["om_personnel"] = fixed["personnel"] / heat
    out["om_maintenance"] = fixed["maintenance"] / heat
    out["om_other"] = fixed["other"] / heat
    # consumables: per MWh of product gas (SF 1.0 = proportional to production)
    out["consumables"] = sek(C.THUNMAN_OPEX_SEK_MWH["consumables"]) * share \
        * ch.fuel_lhv_mw / ch.heat_mw
    # electrolyser / storage / ASU fixed O&M and stack replacement
    el_hours = ch.electrolyser_flh_frac * c.flh
    interval = c.stack_life_h / el_hours if el_hours > 0 else 0.0
    out["om_electrolyser"] = (c.electrolyser_fom_frac * cap_el
                              + replacement_annuity(c.stack_replacement_frac * cap_el, r, n,
                                                    interval)) / heat
    out["om_storage_asu"] = (c.storage_fom_frac * cap_sto + c.asu_fom_frac * cap_asu) / heat
    out["biomass"] = ch.biomass_mwh_per_mwh * c.biomass_eur_mwh
    out["electricity"] = ch.electricity_eur_per_mwh_heat * c.electricity_price_mult \
        + ch.electricity_mwh_per_mwh_heat * c.electricity_adder_eur_mwh
    out["o2_revenue"] = -ch.o2_vent_kg_per_mwh_heat / 1e3 * c.o2_price_eur_t
    out["total"] = float(sum(out.values()))
    out["capex_total_meur"] = (cap_gas * (1 + C.THUNMAN_DEV_FRAC) + cap_meth * (1 + C.THUNMAN_DEV_FRAC)
                               + cap_el + cap_sto + cap_asu) / 1e6
    return out


CAPEX_KEYS = ("capex_gasification", "capex_methanation", "capex_development",
              "capex_electrolyser", "capex_storage", "capex_asu")
OM_KEYS = ("om_personnel", "om_maintenance", "om_other", "consumables", "om_electrolyser",
           "om_storage_asu")


def grouped(b: Dict[str, float]) -> Dict[str, float]:
    return {
        "CAPEX": sum(b[k] for k in CAPEX_KEYS),
        "O&M": sum(b[k] for k in OM_KEYS),
        "Biomass": b["biomass"],
        "Electricity": b["electricity"],
        "O2 sales": b["o2_revenue"],
    }
