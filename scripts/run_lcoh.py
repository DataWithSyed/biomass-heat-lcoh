"""Run the full LCOH study: sizing grid, central results, scenarios, tornado, Monte Carlo, scale."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bhlcoh import costs as C                                         # noqa: E402
from bhlcoh.chains import chain_inputs, lcoh_breakdown, grouped, LABELS  # noqa: E402
from bhlcoh.dispatch import run_dispatch, prices, ELECTROLYSER_CONFIGS  # noqa: E402
from bhlcoh.reference import ng_lcoh, ng_design, breakeven_co2_price, breakeven_gas_price  # noqa
from bhlcoh.sensitivity import tornado, monte_carlo, mc_summary       # noqa: E402

RES, FIG = ROOT / "results", ROOT / "figures"
RES.mkdir(exist_ok=True); FIG.mkdir(exist_ok=True)
BASE = C.central_inputs()
MEAN_P = float(np.mean(prices()))
FLAT = ("air", "oxy_none", "steam_dfb")
ORDER = ["air", "oxy_none", "steam_dfb", "oxy_none_elec", "oxy_partial", "oxy_full"]
N_MC = 10_000

print(f"mean DA price {MEAN_P:.1f} EUR/MWh, n={len(prices())}")
print("NG reference:", {k: round(v, 2) for k, v in ng_lcoh(BASE).items()}, ng_design())

# ---- 1. electrolyser sizing grid (O4 realisable strategy; O1 1x reference) -----------------------
grid = []
for cfg in ELECTROLYSER_CONFIGS:
    d = run_dispatch(cfg, 1.0, 0.0, "O1_follow_demand")
    b = lcoh_breakdown(chain_inputs(cfg, MEAN_P, d), BASE)
    grid.append({**d, **b})
    for cf in (1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0):
        for sh in (0.0, 3.0, 6.0, 12.0, 24.0, 48.0):
            d = run_dispatch(cfg, cf, sh, "O4_rolling_day_ahead")
            if d["h2_unserved_kg"] > 1.0:
                continue
            b = lcoh_breakdown(chain_inputs(cfg, MEAN_P, d), BASE)
            grid.append({**d, **b})
    print(f"sizing grid {cfg} done", flush=True)
grid = pd.DataFrame(grid)
grid.to_csv(RES / "sizing_grid_O4.csv", index=False)
best_disp = {}
for cfg in ELECTROLYSER_CONFIGS:
    g = grid[(grid.config == cfg) & (grid.strategy == "O4_rolling_day_ahead")]
    r = g.loc[g.total.idxmin()]
    best_disp[cfg] = run_dispatch(cfg, float(r.capacity_factor), float(r.storage_h))
    print(f"  LCOH-optimal {cfg}: {r.capacity_factor}x, {r.storage_h} h -> {r.total:.1f}")

# ---- 2. central results -------------------------------------------------------------------------
def build_chains(base_disp=best_disp, heat_mw=10.0):
    out = {}
    for cfg in ORDER:
        d = base_disp.get(cfg)
        if d is not None and heat_mw != 10.0:
            s = heat_mw / 10.0
            d = {**d, "electrolyser_mw": d["electrolyser_mw"] * s,
                 "h2_storage_kg": d["h2_storage_kg"] * s, "o2_storage_kg": d["o2_storage_kg"] * s}
        out[cfg] = chain_inputs(cfg, MEAN_P, d, heat_mw=heat_mw)
    return out

CH = build_chains()
SCEN = {
    "central": BASE,
    "integrated": BASE.with_(aux_project_mult=0.5, personnel_mult=0.5),
    "integrated_low_cost": BASE.with_(aux_project_mult=0.5, personnel_mult=0.5,
                                      methanation_goetz_weight=1.0,
                                      electrolyser_eur2016_kw=C.SCHMIDT_AEC_2030_MEDIAN,
                                      biomass_eur_mwh=C.thunman_forest_residue_eur2025()),
}
def capex_for_parity(ch, c, co2):
    """Total up-front CAPEX (MEUR, incl. development) at which the chain matches NG heat cost,
    keeping all non-CAPEX costs; negative = cannot match even with free plant."""
    from bhlcoh.chains import CAPEX_KEYS
    from bhlcoh.finance import crf
    b = lcoh_breakdown(ch, c)
    non_capex = b["total"] - sum(b[k] for k in CAPEX_KEYS)
    room = ng_lcoh(c.with_(co2_eur_t=co2))["total"] - non_capex
    return room * ch.heat_mw * c.flh / crf(c.discount_rate, c.lifetime_y) / 1e6


rows = []
for sname, c in SCEN.items():
    ng = ng_lcoh(c)
    for cfg, ch in CH.items():
        b = lcoh_breakdown(ch, c)
        rows.append(dict(scenario=sname, config=cfg, label=ch.label, strategy=ch.strategy,
                         capacity_factor=ch.capacity_factor, storage_h=ch.storage_h,
                         lcoh=b["total"], capex_meur=b["capex_total_meur"],
                         **{f"g_{k}": v for k, v in grouped(b).items()},
                         ng_lcoh=ng["total"], gap_to_ng=b["total"] - ng["total"],
                         breakeven_co2_eur_t=breakeven_co2_price(b["total"], c),
                         breakeven_gas_eur_mwh_gcv=breakeven_gas_price(b["total"], c),
                         capex_parity_meur_eua_central=capex_for_parity(ch, c, c.co2_eur_t),
                         capex_parity_meur_eua_200=capex_for_parity(ch, c, 200.0),
                         biomass_mwh_per_mwh=ch.biomass_mwh_per_mwh,
                         electricity_mwh_per_mwh=ch.electricity_mwh_per_mwh_heat))
res = pd.DataFrame(rows)
res.to_csv(RES / "lcoh_results.csv", index=False)
full = []
for cfg, ch in CH.items():
    full.append({"config": cfg, **lcoh_breakdown(ch, BASE)})
pd.DataFrame(full).to_csv(RES / "lcoh_breakdown_central.csv", index=False)
print(res[["scenario", "config", "lcoh", "capex_meur", "gap_to_ng", "breakeven_co2_eur_t"]]
      .round(1).to_string(index=False))

# ---- 3. tornado on the gap to NG ------------------------------------------------------------------
cen = res[res.scenario == "central"].set_index("config")
best = cen.lcoh.idxmin()
torn = {}
for cfg in dict.fromkeys([best, "oxy_full"]):
    t = tornado(CH[cfg], BASE)
    t.insert(0, "config", cfg)
    torn[cfg] = t
pd.concat(torn.values()).to_csv(RES / "tornado_gap_to_ng.csv", index=False)

# ---- 4. Monte Carlo --------------------------------------------------------------------------------
mc = monte_carlo(CH.values(), BASE, n=N_MC, seed=7)
summ = mc_summary(mc, ORDER)
summ.to_csv(RES / "monte_carlo_summary.csv", index=False)
print(summ.round(3).to_string(index=False))
mc.describe(percentiles=[0.1, 0.5, 0.9]).to_csv(RES / "monte_carlo_describe.csv")

# ---- 5. scale sweep ---------------------------------------------------------------------------------
scale = []
for hmw in (5.0, 10.0, 20.0, 50.0, 100.0):
    chs = build_chains(heat_mw=hmw)
    for sname in ("central", "integrated"):
        c = SCEN[sname]
        for cfg, ch in chs.items():
            b = lcoh_breakdown(ch, c)
            scale.append(dict(heat_mw=hmw, scenario=sname, config=cfg, lcoh=b["total"],
                              breakeven_co2_eur_t=breakeven_co2_price(b["total"], c)))
scale = pd.DataFrame(scale)
scale.to_csv(RES / "scale_sweep.csv", index=False)

# ---- 6. meta ----------------------------------------------------------------------------------------
gas = C.eurostat_gas_series()
meta = {
    "cost_inputs_central": asdict(BASE),
    "integrated_overrides": {"aux_project_mult": 0.5, "personnel_mult": 0.5},
    "mean_da_price_eur_mwh": MEAN_P, "n_hours": int(len(prices())),
    "ng": ng_design(), "ng_lcoh_central": ng_lcoh(BASE),
    "eurostat_gas_DE_I4_X_TAX_eur_mwh_gcv": gas,
    "hicp_ea": C.HICP_EA,
    "h2_storage_eur2014_per_kg_derived": C.goetz_h2_storage_eur2014_per_kg(),
    "lcoh_optimal_sizing_O4": {k: {"capacity_factor": v["capacity_factor"],
                                   "storage_h": v["storage_h"]} for k, v in best_disp.items()},
    "n_monte_carlo": N_MC,
    "attribution": [
        "Day-ahead prices (DE-LU): Energy-Charts.info (Fraunhofer ISE), CC BY 4.0; source SMARD.de",
        "Gas prices and HICP: Eurostat (nrg_pc_203, prc_hicp_aind), CC BY 4.0",
    ],
}
(RES / "run_meta.json").write_text(json.dumps(meta, indent=2, default=float))

# ---- figures ----------------------------------------------------------------------------------------
COL = {"CAPEX": "#1f5f8b", "O&M": "#6c8ebf", "Biomass": "#4c9a6a", "Electricity": "#e07b39",
       "O2 sales": "#999999"}
fig, ax = plt.subplots(figsize=(10.5, 5.2))
x = np.arange(len(ORDER))
bottom = np.zeros(len(ORDER))
for g in ("CAPEX", "O&M", "Biomass", "Electricity"):
    v = np.array([cen.loc[k, f"g_{g}"] for k in ORDER])
    ax.bar(x, v, 0.6, bottom=bottom, label=g, color=COL[g]); bottom += v
integ = res[res.scenario == "integrated"].set_index("config")
ax.scatter(x, [integ.loc[k, "lcoh"] for k in ORDER], marker="D", color="k", zorder=5,
           label="total, integrated site (aux/project and staff x0.5)")
for co2, ls in ((BASE.co2_eur_t, "--"), (200.0, ":")):
    v = ng_lcoh(BASE.with_(co2_eur_t=co2))["total"]
    ax.axhline(v, color="#8c3a22", ls=ls, lw=1.4,
               label=f"natural gas + CO2 {co2:.0f} EUR/t: {v:.0f}")
for i, k in enumerate(ORDER):
    ax.text(i, bottom[i] + 8, f"{bottom[i]:.0f}", ha="center", fontsize=8)
lab = [LABELS[k].replace(", ", ",\n").replace(" + ", " +\n") for k in ORDER]
ax.set_xticks(x); ax.set_xticklabels(lab, fontsize=7.5)
ax.set_ylabel("LCOH (EUR 2025 / MWh process heat)")
ax.set_title("LCOH at 10 MW / 1000 degC vs natural gas (central case, electrolyser chains at "
             "LCOH-optimal O4 sizing)", fontsize=9.5)
ax.legend(fontsize=7.5, loc="upper left"); ax.grid(axis="y", alpha=0.3)
fig.tight_layout(); fig.savefig(FIG / "01_lcoh_breakdown_vs_ng.png", dpi=140); plt.close()

# CO2 price sweep
co2 = np.linspace(0, 1500, 151)
fig, ax = plt.subplots(figsize=(8.5, 4.6))
ngv = [ng_lcoh(BASE.with_(co2_eur_t=p))["total"] for p in co2]
ax.plot(co2, ngv, color="#8c3a22", lw=2.2, label="natural gas (Eurostat DE I4 2026-S1)")
cmap = plt.get_cmap("tab10")
for i, k in enumerate(ORDER):
    ax.axhline(cen.loc[k, "lcoh"], color=cmap(i), lw=1.2, ls="-",
               label=f"{k}: {cen.loc[k, 'lcoh']:.0f} (break-even {cen.loc[k, 'breakeven_co2_eur_t']:.0f} EUR/t)")
ax.axvline(BASE.co2_eur_t, color="#555", ls=":", lw=1)
ax.text(BASE.co2_eur_t + 12, 610, f"EUA H1 2026\n{BASE.co2_eur_t:.0f} EUR/t", fontsize=7)
ax.set_xlabel("CO2 price (EUR/t)"); ax.set_ylabel("EUR / MWh_heat")
ax.set_title("Break-even CO2 price (central case)", fontsize=10)
ax.legend(fontsize=6.8); ax.grid(alpha=0.3); ax.set_xlim(0, 1500)
fig.tight_layout(); fig.savefig(FIG / "02_breakeven_co2.png", dpi=140); plt.close()

# tornado
fig, axs = plt.subplots(1, len(torn), figsize=(12, 5))
axs = np.atleast_1d(axs)
for ax, (cfg, t) in zip(axs, torn.items()):
    t = t[t.swing > 0.05].iloc[::-1]
    y = np.arange(len(t))
    base = t.base.iloc[0]
    ax.barh(y, t.y_low - base, left=base, color="#4c9a6a", label="parameter at low value")
    ax.barh(y, t.y_high - base, left=base, color="#e07b39", label="parameter at high value")
    ax.axvline(base, color="k", lw=1); ax.axvline(0, color="#8c3a22", ls="--", lw=1)
    ax.set_yticks(y); ax.set_yticklabels(t.parameter, fontsize=7.5)
    ax.set_xlabel("LCOH minus natural-gas heat cost (EUR/MWh_heat)")
    ax.set_title(f"{cfg}: gap to NG {base:.0f} EUR/MWh (central)", fontsize=9)
    ax.legend(fontsize=7); ax.grid(axis="x", alpha=0.3)
fig.tight_layout(); fig.savefig(FIG / "03_tornado_gap_to_ng.png", dpi=140); plt.close()

# Monte Carlo
fig, ax = plt.subplots(figsize=(9, 4.6))
data = [mc[k].values for k in ORDER] + [mc["ng"].values]
bp = ax.boxplot(data, whis=(10, 90), showfliers=False, patch_artist=True)
for patch, colr in zip(bp["boxes"], [cmap(i) for i in range(len(ORDER))] + ["#8c3a22"]):
    patch.set_facecolor(colr); patch.set_alpha(0.55)
ax.set_xticks(range(1, len(ORDER) + 2)); ax.set_xticklabels(ORDER + ["natural gas"], fontsize=8,
                                                             rotation=15)
ax.set_ylabel("EUR / MWh_heat")
ax.set_title(f"Monte Carlo ({N_MC:,} draws, triangular inputs incl. CO2 50-200 EUR/t); "
             "whiskers P10-P90", fontsize=9)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout(); fig.savefig(FIG / "04_monte_carlo.png", dpi=140); plt.close()

# sizing heatmap oxy_full
g = grid[(grid.config == "oxy_full") & (grid.strategy == "O4_rolling_day_ahead")]
pv = g.pivot(index="storage_h", columns="capacity_factor", values="total")
fig, ax = plt.subplots(figsize=(6.4, 4.2))
im = ax.imshow(pv.values, cmap="viridis_r", aspect="auto", origin="lower")
ax.set_xticks(range(pv.shape[1])); ax.set_xticklabels([f"{v:g}x" for v in pv.columns])
ax.set_yticks(range(pv.shape[0])); ax.set_yticklabels([f"{v:g} h" for v in pv.index])
for i in range(pv.shape[0]):
    for j in range(pv.shape[1]):
        if np.isfinite(pv.values[i, j]):
            ax.text(j, i, f"{pv.values[i, j]:.0f}", ha="center", va="center", fontsize=7,
                    color="w")
ax.set_xlabel("Electrolyser capacity (x design)"); ax.set_ylabel("H2/O2 storage")
ax.set_title("oxy_full LCOH (EUR/MWh_heat), O4 rolling day-ahead", fontsize=9)
fig.colorbar(im, ax=ax); fig.tight_layout()
fig.savefig(FIG / "05_sizing_oxy_full.png", dpi=140); plt.close()

# scale
fig, ax = plt.subplots(figsize=(8, 4.4))
for i, k in enumerate(["air", "oxy_none", "steam_dfb", "oxy_none_elec", "oxy_full"]):
    s = scale[(scale.config == k) & (scale.scenario == "central")]
    ax.plot(s.heat_mw, s.lcoh, "o-", color=cmap(ORDER.index(k)), label=k)
    s2 = scale[(scale.config == k) & (scale.scenario == "integrated")]
    ax.plot(s2.heat_mw, s2.lcoh, "o--", color=cmap(ORDER.index(k)), alpha=0.6)
ax.axhline(ng_lcoh(BASE)["total"], color="#8c3a22", lw=1.6, label="NG + EUA 76")
ax.axhline(ng_lcoh(BASE.with_(co2_eur_t=200))["total"], color="#8c3a22", ls=":", label="NG + 200 EUR/t")
ax.set_xscale("log"); ax.set_xticks([5, 10, 20, 50, 100]); ax.set_xticklabels(["5", "10", "20", "50", "100"])
ax.set_xlabel("Process heat duty (MW)"); ax.set_ylabel("LCOH (EUR/MWh_heat)")
ax.set_title("Economies of scale (solid: central, dashed: integrated site)", fontsize=9.5)
ax.legend(fontsize=7); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(FIG / "06_scale.png", dpi=140); plt.close()
print("done")
