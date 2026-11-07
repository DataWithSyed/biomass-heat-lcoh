"""Cost and price inputs with their sources.

Every number carries a label:

* ``cited``    - taken directly from the referenced publication or data set;
* ``derived``  - calculated from cited numbers with a documented step;
* ``data``     - real public price data (licence noted);
* ``assumption`` - an engineering assumption chosen by the author for screening.

Monetary values are converted to **EUR 2025** with the euro-area HICP (Eurostat
``prc_hicp_aind``, CP00, annual average index; CC BY 4.0). SEK values from Thunman et al.
(2019) are first converted at the 9.1 SEK/EUR average rate that the paper itself uses for its
2011-2014 project period.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict

DATA = Path(__file__).resolve().parents[2] / "data" / "sources"

# --- price index (Eurostat prc_hicp_aind, euro area, CP00, INX_A_AVG, 2015 = 100) -------------
HICP_EA = {2014: 99.81, 2016: 100.23, 2025: 128.75}   # data (file in data/sources)
SEK_PER_EUR_THUNMAN = 9.1                              # cited: Thunman et al. 2019, sect. 2


def to_eur2025(value: float, year: int) -> float:
    """Escalate a EUR value from ``year`` to 2025 with the euro-area HICP."""
    return value * HICP_EA[2025] / HICP_EA[year]


def ksek2014_to_eur2025(ksek: float) -> float:
    return to_eur2025(ksek * 1e3 / SEK_PER_EUR_THUNMAN, 2014)


# --- Thunman et al. (2019), GoBiGas, Tables 2-4 (kSEK 2014, 20 MW biomethane, eta 70 %) -----------
# cited: section costs of the 20 MW reference plant (Table 2, "Reference cost" column)
THUNMAN_SECTIONS_KSEK = {
    "fuel_handling_internal": 50_400,
    "gasification_combustion": 29_490,
    "primary_gas_cleaning": 23_780,
    "flue_gas_system": 18_930,
    "tar_adsorption": 10_620,
    "compressor": 34_590,
    "olefin_hydrogenation": 9_060,
    "h2s_scrubber": 9_150,
    "water_gas_shift": 5_290,
    "premethanation": 5_150,
    "co2_scrubber": 17_570,
    "methanation": 19_410,
    "drying_odorization": 4_970,
}
THUNMAN_PROCESS_TOTAL_KSEK = 238_410          # cited, Table 2
THUNMAN_AUX_PROJECT_REF_KSEK = 955_056        # cited, Table 2 (site-specific items removed)
THUNMAN_P_REF_MW = 20.0                       # cited, biomethane output
THUNMAN_ETA = 0.70                            # cited, dry biomass -> biomethane (LHV)
THUNMAN_SF_PROCESS = 0.68                     # cited, Table 4 "reactor systems"
THUNMAN_SF_AUX = 0.44                         # cited, Table 4 "auxiliary equipment and project"
THUNMAN_SF_EXT = 0.67                         # cited, Table 4 "steam cycle, ext. fuel handling, drying"
# cited, Table 3: external fuel handling 280 MSEK + belt dryer 60 MSEK at 100 MW product
THUNMAN_EXT_FUEL_DRYER_KSEK = 280_000 + 60_000
THUNMAN_EXT_P_REF_MW = 100.0
THUNMAN_DEV_FRAC = 0.10                       # cited: development cost = 10 % of investment
# cited, Table 4 (estimated commercial 20 MW plant, 8000 FLH), SEK per MWh biomethane
THUNMAN_OPEX_SEK_MWH = {"personnel": 181.0, "maintenance": 89.0, "consumables": 55.1,
                        "other": 26.5}
THUNMAN_OPEX_SF = {"personnel": 0.10, "maintenance": 0.67, "consumables": 1.00, "other": 0.67}
THUNMAN_FLH = 8000.0                          # cited
# cited, Table 5 / Table 4: forest residue 170 SEK/MWh (as received, Gothenburg region)
THUNMAN_FOREST_RESIDUE_SEK_MWH = 170.0

GAS_ISLAND_SECTIONS = ("fuel_handling_internal", "gasification_combustion",
                       "primary_gas_cleaning", "flue_gas_system", "tar_adsorption")
# Methanation subset used here: the plant model adds external H2 instead of shifting and has no
# CO2 removal (plant-model assumption A14), so WGS and the CO2 scrubber are left out (assumption).
METHANATION_SECTIONS = ("compressor", "olefin_hydrogenation", "h2s_scrubber", "premethanation",
                        "methanation", "drying_odorization")


def section_sum(keys) -> float:
    return float(sum(THUNMAN_SECTIONS_KSEK[k] for k in keys))


# --- Goetz et al. (2016) -----------------------------------------------------------------------
# cited (sect. 5.3.1.1, quoting Outotec): methanation 400 EUR/kW_SNG at 5 MW and 130 EUR/kW_SNG
# at 110 MW (2014, 20 bar)
GOETZ_METH_POINTS = ((5.0, 400.0), (110.0, 130.0))
# cited (Table 8, case 1): 36 MW electrolysis, H2 storage 1700 m3 at 30-200 bar = 8.3 MEUR,
# compressor 1 MEUR (EUR 2014 assumed = publication data year)
GOETZ_H2_STORAGE_MEUR = 8.3
GOETZ_H2_STORAGE_M3 = 1700.0
GOETZ_P_MIN_BAR, GOETZ_P_MAX_BAR = 30.0, 200.0
GOETZ_COMPRESSOR_MEUR = 1.0
GOETZ_ELECTROLYSIS_MW = 36.0
# cited (sect. 5.3.2.1, quoting Vandewalle et al.): O2 prices of 10 and 70 EUR/t
GOETZ_O2_PRICE_RANGE = (10.0, 70.0)


def h2_density_kg_m3(p_bar: float, t_k: float = 298.15, b_cm3_mol: float = 14.0) -> float:
    """H2 density from the truncated virial equation Z = 1 + B p / (R T).

    B ~ 14 cm3/mol for H2 near room temperature (assumption, standard order of magnitude);
    accurate to a few per cent up to ~200 bar, which is enough for a cost per kg.
    """
    r = 8.314462618
    p = p_bar * 1e5
    z = 1.0 + b_cm3_mol * 1e-6 * p / (r * t_k)
    return p * 2.01588e-3 / (z * r * t_k)


def goetz_h2_storage_eur2014_per_kg() -> float:
    """Derived: Goetz Table 8 storage cost per kg of usable H2 (30-200 bar swing, 25 degC)."""
    usable = (h2_density_kg_m3(GOETZ_P_MAX_BAR) - h2_density_kg_m3(GOETZ_P_MIN_BAR)) \
        * GOETZ_H2_STORAGE_M3
    return GOETZ_H2_STORAGE_MEUR * 1e6 / usable


def goetz_methanation_eur2014_per_kw(p_mw: float) -> float:
    """Power law through the two Outotec points quoted by Goetz et al. (derived)."""
    import math
    (p1, c1), (p2, c2) = GOETZ_METH_POINTS
    b = math.log(c2 / c1) / math.log(p2 / p1)
    return c1 * (p_mw / p1) ** b


# --- Schmidt et al. (2017), Table 1 and Appendix D (EUR 2016 / kW_el) ---------------------------
SCHMIDT_AEC_CAPEX_2016 = (1000.0, 1200.0)     # cited, Table 1 (AEC, current)
SCHMIDT_PEM_CAPEX_2016 = (1860.0, 2320.0)     # cited, Table 1 (PEMEC, current)
SCHMIDT_AEC_2030_MEDIAN = 750.0               # cited, sect. "Capital costs" (AEC 2030, 50th)
SCHMIDT_AEC_STACK_LIFE_H = (60_000.0, 90_000.0)  # cited, Table 1

# --- prices --------------------------------------------------------------------------------------
# C.A.R.M.E.N. e.V., Marktpreise Hackschnitzel, forest wood chips 35 % moisture, annual mean 2025,
# EUR/MWh (LHV of the delivered fuel), gross incl. 7 % VAT. Individual figures cited.
CARMEN_2025_GROSS = {"germany": 32.40, "south": 29.74, "north": 43.91}
CARMEN_VAT = 0.07
# Eurostat nrg_pc_203, DE, band I4 (100 000-999 999 GJ), excl. taxes and levies, EUR/kWh (GCV)
EUROSTAT_GAS_FILE = DATA / "eurostat_nrg_pc_203_DE_I4_X_TAX.json"
# DEHSt German EUA auctions, H1 2026 average (quarterly reports Q1/Q2 2026), EUR/t
DEHST_EUA_H1_2026 = 76.02


def eurostat_gas_series() -> Dict[str, float]:
    """Semi-annual DE I4 gas price excl. taxes/levies, EUR/MWh on a GCV basis (data)."""
    d = json.loads(EUROSTAT_GAS_FILE.read_text())
    idx = {i: k for k, i in d["dimension"]["time"]["category"]["index"].items()}
    return {idx[int(k)]: 1000.0 * v for k, v in d["value"].items()}


@dataclass(frozen=True)
class CostInputs:
    """All economic inputs in EUR 2025 (real). Defaults are the central case."""

    discount_rate: float = 0.07          # assumption (docs/scenarios.md of the umbrella repo)
    lifetime_y: int = 20                 # assumption; Thunman also uses 20 y
    flh: float = THUNMAN_FLH             # h/yr at 10 MW heat; cited from Thunman (8000 h)
    # gasification island (Thunman-scaled)
    sf_process: float = THUNMAN_SF_PROCESS
    sf_aux: float = THUNMAN_SF_AUX
    aux_project_mult: float = 1.0        # 1 = full GoBiGas aux/project share; < 1 = site integration
    personnel_mult: float = 1.0          # 1 = GoBiGas staffing scaled by Thunman SF 0.10
    # methanation CAPEX: 0 = Thunman sections + aux share (central), 1 = Goetz/Outotec power law
    methanation_goetz_weight: float = 0.0
    # electrolyser (Schmidt 2017), EUR 2016 / kW_el system
    electrolyser_eur2016_kw: float = sum(SCHMIDT_AEC_CAPEX_2016) / 2.0
    stack_life_h: float = sum(SCHMIDT_AEC_STACK_LIFE_H) / 2.0
    stack_replacement_frac: float = 0.40   # assumption
    electrolyser_fom_frac: float = 0.02    # assumption, of capex per year
    # storage (Goetz 2016 derived)
    h2_storage_eur2014_kg: float = field(default_factory=goetz_h2_storage_eur2014_per_kg)
    storage_fom_frac: float = 0.015        # assumption
    # ASU (assumption, no cited source yet - see docs/assumptions.md L-A4)
    asu_eur_per_kg_h: float = 3000.0       # EUR 2025 per (kg O2/h) installed
    asu_fom_frac: float = 0.02             # assumption
    # prices
    biomass_eur_mwh: float = CARMEN_2025_GROSS["germany"] / (1 + CARMEN_VAT)
    electricity_price_mult: float = 1.0   # scales the real 2025-26 DE-LU day-ahead series
    electricity_adder_eur_mwh: float = 0.0  # assumption: grid fees/levies on top of DA price
    gas_eur_mwh_gcv: float = 44.1          # data: Eurostat DE I4 2026-S1 excl. taxes/levies
    co2_eur_t: float = DEHST_EUA_H1_2026   # data: DEHSt H1 2026 average auction price
    o2_price_eur_t: float = 0.0            # central: surplus O2 vented (no market assumed)

    def with_(self, **kw) -> "CostInputs":
        return replace(self, **kw)


def central_inputs() -> CostInputs:
    gas = eurostat_gas_series()
    return CostInputs(gas_eur_mwh_gcv=gas["2026-S1"])


def thunman_forest_residue_eur2025() -> float:
    """Low biomass case: Thunman's 170 SEK/MWh forest residue (2014) in EUR 2025 (derived)."""
    return to_eur2025(THUNMAN_FOREST_RESIDUE_SEK_MWH / SEK_PER_EUR_THUNMAN, 2014)


# Tornado / Monte Carlo ranges: (low, high, label, source). Central value from CostInputs.
def parameter_ranges() -> Dict[str, tuple]:
    gas = eurostat_gas_series()
    return {
        "discount_rate": (0.05, 0.10, "assumption", "umbrella docs/scenarios.md"),
        "flh": (7000.0, 8500.0, "assumption", "around Thunman's 8000 h"),
        "biomass_eur_mwh": (thunman_forest_residue_eur2025(),
                            CARMEN_2025_GROSS["north"] / (1 + CARMEN_VAT), "cited",
                            "Thunman 2019 forest residue (escalated) / C.A.R.M.E.N. 2025 north, net"),
        "aux_project_mult": (0.5, 1.0, "assumption",
                             "site integration can cut project costs (Thunman sect. 3)"),
        "sf_process": (THUNMAN_SF_PROCESS - 0.1, THUNMAN_SF_PROCESS + 0.1, "cited",
                       "Thunman Table 2 SF +/- 0.1"),
        "personnel_mult": (0.5, 1.0, "assumption", "shared staff at an industrial site"),
        "methanation_goetz_weight": (1.0, 0.0, "cited",
                                     "Goetz 2016 (Outotec) / Thunman 2019 sections + aux"),
        "electrolyser_eur2016_kw": (SCHMIDT_AEC_2030_MEDIAN, SCHMIDT_PEM_CAPEX_2016[1], "cited",
                                    "Schmidt 2017 AEC 2030 median / PEMEC Table 1 upper"),
        "electricity_price_mult": (0.7, 1.3, "assumption", "+/-30 % on the real DA series"),
        "electricity_adder_eur_mwh": (0.0, 30.0, "assumption", "grid fees and levies"),
        "asu_eur_per_kg_h": (1500.0, 6000.0, "assumption", "order of magnitude, unsourced"),
        "o2_price_eur_t": (0.0, GOETZ_O2_PRICE_RANGE[1], "cited",
                           "Goetz 2016 quoting Vandewalle: 10-70 EUR/t"),
        "gas_eur_mwh_gcv": (gas["2019-S2"], gas["2022-S2"], "data",
                            "Eurostat DE I4 2019-S2 / 2022-S2"),
        "co2_eur_t": (50.0, 200.0, "assumption", "umbrella docs/scenarios.md"),
    }
