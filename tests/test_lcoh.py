import math

import numpy as np
import pytest

from bhlcoh import costs as C
from bhlcoh.chains import chain_inputs, lcoh_breakdown, capex_gas_island, CAPEX_KEYS, OM_KEYS
from bhlcoh.costs import CostInputs, central_inputs
from bhlcoh.finance import crf, replacement_annuity, annualise
from bhlcoh.reference import ng_lcoh, ng_design, breakeven_co2_price, breakeven_gas_price
from bhlcoh.sensitivity import tornado, sample_inputs, monte_carlo, mc_summary

MEAN_P = 110.8


@pytest.fixture(scope="module")
def base():
    return central_inputs()


@pytest.fixture(scope="module")
def dfb():
    return chain_inputs("steam_dfb", MEAN_P)


@pytest.fixture(scope="module")
def oxy_full_flat():
    """oxy_full at 1x follow-demand on a flat price, built without the LP (fast)."""
    from biomass_heat import Plant
    dp = Plant("oxy_full").design_point(10e6, 1273.15)
    disp = dict(electrolyser_mw=dp["el_electrolyser_MW"], capacity_factor=1.0, storage_h=0.0,
                h2_storage_kg=0.0, o2_storage_kg=0.0, electrolyser_flh_frac=1.0,
                electricity_eur_per_mwh_heat=dp["electricity_MWh_per_MWh"] * MEAN_P,
                electricity_mwh_per_mwh_heat=dp["electricity_MWh_per_MWh"],
                o2_vent_kg_per_mwh_heat=50.0, strategy="O1_follow_demand")
    return chain_inputs("oxy_full", MEAN_P, disp)


# --- finance ----------------------------------------------------------------------------------
def test_crf_known_values():
    assert crf(0.07, 20) == pytest.approx(0.0943929, rel=1e-6)
    assert crf(0.0, 20) == pytest.approx(0.05)
    assert annualise(1e6, 0.05, 10) == pytest.approx(129_504.57, rel=1e-6)


def test_replacement_annuity():
    assert replacement_annuity(100.0, 0.07, 20, 25.0) == 0.0
    assert replacement_annuity(100.0, 0.07, 20, 20.0) == 0.0    # at end of life: not counted
    one = replacement_annuity(100.0, 0.07, 20, 10.0)
    assert one == pytest.approx(100.0 / 1.07 ** 10 * crf(0.07, 20))
    assert replacement_annuity(100.0, 0.07, 20, 5.0) > one


# --- cost data ----------------------------------------------------------------------------------
def test_thunman_tables_consistent():
    assert C.section_sum(C.THUNMAN_SECTIONS_KSEK) == C.THUNMAN_PROCESS_TOTAL_KSEK
    gas = C.section_sum(C.GAS_ISLAND_SECTIONS)
    meth = C.section_sum(C.METHANATION_SECTIONS)
    assert gas == 133_220 and meth == 82_330
    # Table 4 total for the 20 MW reference plant: 238 + 955 + 182 = 1375 MSEK, where 182 is
    # Table 3 (fuel handling + dryer + steam cycle, 540 MSEK at 100 MW) scaled with SF 0.67.
    # This model keeps fuel handling + dryer and leaves out the steam cycle.
    ext20 = (C.THUNMAN_EXT_FUEL_DRYER_KSEK + 200_000) * (20 / 100) ** C.THUNMAN_SF_EXT
    assert (238_410 + 955_056 + ext20) / 1e3 == pytest.approx(1375, abs=3)


def test_currency_and_index():
    assert C.ksek2014_to_eur2025(9_100) == pytest.approx(1e6 * 128.75 / 99.81)
    assert C.to_eur2025(100.0, 2016) == pytest.approx(100 * 128.75 / 100.23)


def test_goetz_methanation_power_law_hits_both_points():
    assert C.goetz_methanation_eur2014_per_kw(5.0) == pytest.approx(400.0)
    assert C.goetz_methanation_eur2014_per_kw(110.0) == pytest.approx(130.0)


def test_h2_storage_derivation_plausible():
    assert 13.5 < C.h2_density_kg_m3(200.0) < 15.5
    assert 2.2 < C.h2_density_kg_m3(30.0) < 2.6
    assert 300 < C.goetz_h2_storage_eur2014_per_kg() < 500


def test_eurostat_gas_series_parsed():
    gas = C.eurostat_gas_series()
    assert gas["2026-S1"] == pytest.approx(44.1)
    assert gas["2022-S2"] > gas["2019-S2"]
    assert central_inputs().gas_eur_mwh_gcv == pytest.approx(44.1)


def test_gas_island_capex_at_reference_size():
    c = CostInputs()
    ch = chain_inputs("steam_dfb", MEAN_P)
    ref = ch.__class__(**{**ch.asdict(), "biomass_lhv_mw": 20 / 0.7})
    gas = C.section_sum(C.GAS_ISLAND_SECTIONS)
    ext = C.THUNMAN_EXT_FUEL_DRYER_KSEK * 0.2 ** C.THUNMAN_SF_EXT
    expect = C.ksek2014_to_eur2025(gas * (1 + 955_056 / 238_410) + ext)
    assert capex_gas_island(ref, c) == pytest.approx(expect)


# --- natural gas reference and break-even -----------------------------------------------------
def test_ng_reference(base):
    d = ng_design()
    assert 1.10 < d["gcv_over_ncv"] < 1.12
    assert d["co2_t_per_mwh"] == pytest.approx(0.386, abs=0.002)
    ng = ng_lcoh(base)
    assert ng["fuel"] == pytest.approx(d["ng_mwh_lhv_per_mwh"] * d["gcv_over_ncv"] * 44.1)
    assert ng["co2"] == pytest.approx(d["co2_t_per_mwh"] * base.co2_eur_t)


def test_breakeven_prices_close_the_gap(base, dfb):
    lc = lcoh_breakdown(dfb, base)["total"]
    p = breakeven_co2_price(lc, base)
    assert ng_lcoh(base.with_(co2_eur_t=p))["total"] == pytest.approx(lc)
    g = breakeven_gas_price(lc, base)
    assert ng_lcoh(base.with_(gas_eur_mwh_gcv=g))["total"] == pytest.approx(lc)


# --- LCOH build-up ------------------------------------------------------------------------------
def test_breakdown_sums_and_scope(base, dfb):
    b = lcoh_breakdown(dfb, base)
    parts = [b[k] for k in CAPEX_KEYS + OM_KEYS + ("biomass", "electricity", "o2_revenue")]
    assert sum(parts) == pytest.approx(b["total"])
    assert b["capex_electrolyser"] == b["capex_storage"] == b["capex_asu"] == 0.0
    assert b["biomass"] == pytest.approx(dfb.biomass_mwh_per_mwh * base.biomass_eur_mwh)
    asu = lcoh_breakdown(chain_inputs("oxy_none", MEAN_P), base)
    assert asu["capex_asu"] > 0


def test_electrolyser_chain_requires_dispatch():
    with pytest.raises(ValueError):
        chain_inputs("oxy_full", MEAN_P)


def test_monotonic_responses(base, dfb, oxy_full_flat):
    f = lambda ch, **kw: lcoh_breakdown(ch, base.with_(**kw))["total"]
    b0 = f(dfb)
    assert f(dfb, biomass_eur_mwh=40.0) > b0
    assert f(dfb, discount_rate=0.10) > b0
    assert f(dfb, flh=8500.0) < b0
    assert f(dfb, aux_project_mult=0.5) < b0
    o0 = f(oxy_full_flat)
    assert f(oxy_full_flat, electrolyser_eur2016_kw=2000.0) > o0
    assert f(oxy_full_flat, methanation_goetz_weight=1.0) < o0
    assert f(oxy_full_flat, o2_price_eur_t=70.0) == pytest.approx(o0 - 50.0 * 0.070)


def test_electricity_multiplier_and_adder_exact(base, oxy_full_flat):
    e0 = lcoh_breakdown(oxy_full_flat, base)["electricity"]
    e1 = lcoh_breakdown(oxy_full_flat, base.with_(electricity_price_mult=1.3,
                                                  electricity_adder_eur_mwh=10.0))["electricity"]
    assert e1 == pytest.approx(1.3 * e0 + 10.0 * oxy_full_flat.electricity_mwh_per_mwh_heat)


def test_stack_replacement_counts_with_hours(base, oxy_full_flat):
    hi = lcoh_breakdown(oxy_full_flat, base)["om_electrolyser"]
    lo = lcoh_breakdown(oxy_full_flat.__class__(**{**oxy_full_flat.asdict(),
                                                   "electrolyser_flh_frac": 0.3}),
                        base)["om_electrolyser"]
    assert hi > lo   # 8000 h/yr -> one replacement inside 20 y; 2400 h/yr -> none


def test_scale_economies(base):
    small = lcoh_breakdown(chain_inputs("steam_dfb", MEAN_P, heat_mw=5.0), base)["total"]
    large = lcoh_breakdown(chain_inputs("steam_dfb", MEAN_P, heat_mw=50.0), base)["total"]
    assert large < small


# --- dispatch coupling --------------------------------------------------------------------------
def test_dispatch_flat_price_matches_design_electricity():
    from bhlcoh.dispatch import run_dispatch
    from biomass_heat import Plant
    p = np.full(72, 80.0)
    d = run_dispatch("oxy_full", 1.0, 0.0, "O1_follow_demand", price_series=p)
    el = Plant("oxy_full").design_point(10e6, 1273.15)["electricity_MWh_per_MWh"]
    assert d["electricity_eur_per_mwh_heat"] == pytest.approx(el * 80.0, rel=1e-6)
    assert d["h2_unserved_kg"] < 1e-6


# --- sensitivity --------------------------------------------------------------------------------
def test_tornado_sorted_and_irrelevant_params_zero(base, dfb):
    t = tornado(dfb, base)
    assert (np.diff(t.swing.values) <= 1e-12).all()
    row = t.set_index("parameter").loc["electrolyser_eur2016_kw"]
    assert row.swing == pytest.approx(0.0, abs=1e-9)
    assert t.set_index("parameter").loc["co2_eur_t"].y_high < t.base.iloc[0]


def test_monte_carlo_reproducible_and_bounded(base, dfb):
    s = sample_inputs(base, 500, seed=3)
    co2 = np.array([c.co2_eur_t for c in s])
    assert co2.min() >= 50 and co2.max() <= 200
    a = monte_carlo([dfb], base, n=200, seed=11)
    b = monte_carlo([dfb], base, n=200, seed=11)
    assert np.allclose(a.values, b.values)
    summ = mc_summary(a, ["steam_dfb"]).set_index("chain")
    assert summ.loc["steam_dfb", "p10"] <= summ.loc["steam_dfb", "p50"] <= summ.loc["steam_dfb", "p90"]
