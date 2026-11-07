# Assumptions register (LCOH v0.1)

Numbered L-A1… for this repo. Plant-model assumptions A1–A23 (`biomass-heat-plant-model`
docs/assumptions.md) and dispatch assumptions A-D1… (`biomass-heat-electrolysis-dispatch`)
still apply. Cited inputs and data are listed in [cost_basis.md](cost_basis.md). Everything
below is an **engineering assumption for screening**, not a measured or quoted value.

| ID | Item | Central | Range in sensitivity | Why |
|---|---|---|---|---|
| L-A1 | Discount rate (real) | 7 % | 5–10 % | umbrella docs/scenarios.md |
| L-A2 | Economic lifetime | 20 y | - | as in Thunman (2019) |
| L-A3 | Full-load hours at 10 MW heat | 8000 h/yr (Thunman's value) | 7000–8500 | constant-duty process |
| L-A4 | **ASU CAPEX** | 3000 EUR(2025) per kg O2/h | 1500–6000 | **unsourced order of magnitude**. Only affects `oxy_none` (≈ 5.5 MEUR, ≈ 6.5 EUR/MWh_heat). To be replaced with a cited value in the scenarios step |
| L-A5 | ASU, electrolyser, storage fixed O&M | 2 %, 2 %, 1.5 % of CAPEX per year | - | typical screening values |
| L-A6 | Stack replacement cost | 40 % of electrolyser CAPEX, every 75,000 operating h | - | stack life cited (Schmidt Table 1), cost share assumed |
| L-A7 | Same gasification-island cost for air / O2 / DFB steam gasifiers | - | via `aux_project_mult`, `sf_process` | only cost study with real plant data available here |
| L-A8 | Thunman O&M allocated by process-cost share (island 56 %, + methanation 90 %) | - | `personnel_mult` 0.5–1.0 | GoBiGas staffing (~28 FTE) is for a stand-alone plant |
| L-A9 | "Integrated site" scenario | auxiliary/project costs ×0.5, personnel ×0.5 | MC range 0.5–1.0 | Thunman (2019, Sect. 3) notes that integration with existing infrastructure and shared staff cut costs; the 0.5 factor is my assumption |
| L-A10 | Electricity cost | real DE-LU DA cost from the dispatch run, no grid fees or levies | price ×0.7–1.3, adder 0–30 EUR/MWh | network-charge exemptions for new electrolysers exist in Germany; other site charges vary |
| L-A11 | Non-electrolyser chains buy power flat | time-weighted mean DA price | as above | constant small load |
| L-A12 | Biomass priced per MWh LHV of the plant-model feed | 30.28 EUR/MWh net | 24.1–41.0 | drying from 35 % to 15 % moisture uses process waste heat (dryer CAPEX included) |
| L-A13 | Surplus electrolyser O2 | vented, 0 EUR/t | 0–70 EUR/t (Götz range) | needs a local buyer and logistics |
| L-A14 | Natural-gas reference | existing furnace, no CAPEX/O&M; fuel + CO2 only | gas 21.2–62.8 EUR/MWh_GCV (Eurostat), CO2 50–200 | the biomass chains feed the same furnace; burner retrofit cost is **not** included |
| L-A15 | Biogenic CO2 | zero-rated | - | EU ETS treatment of sustainable biomass |
| L-A16 | Electrolyser chains sized on the LCOH-optimal O4 point of a 7 × 6 grid (1–4× capacity, 0–48 h storage) | 2.5×, 24 h | fixed in MC | flat optimum: 1.5–2.5× with 12–24 h are within ~1.5 % |
| L-A17 | Monte Carlo | 10,000 independent triangular draws (low, central, high), common random numbers across chains | - | no correlations modelled (e.g. gas and power prices) |
| L-A18 | Scale sweep | all quantities linear in heat duty except CAPEX/O&M scale factors; ASU linear | 5–100 MW heat | Thunman's SFs are meant for roughly 20–200 MW product; 5 MW and 100 MW heat are extrapolations |
