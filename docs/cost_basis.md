# Cost basis and data sources

All money values are **real EUR 2025**. Escalation uses the euro-area HICP (Eurostat
`prc_hicp_aind`, CP00, annual average: 2014 = 99.81, 2016 = 100.23, 2025 = 128.75; CC BY 4.0,
file in `data/sources/`). SEK from Thunman et al. (2019) is converted at the paper's own
9.1 SEK/EUR (2011–2014 project average) before escalation. HICP is a general price index.
Plant and equipment costs rose faster than HICP after 2021, so the escalated CAPEX is more
likely too low than too high (see Limitations in the README).

Labels: **cited** = number taken from the source; **derived** = calculated from cited numbers
in a documented step; **data** = public price data; **assumption** = my own screening value.

## 1. Gasification island, methanation section, O&M: Thunman et al. (2019), GoBiGas

Source: first-of-its-kind 20 MW bio-SNG plant (dual fluidised bed gasifier + methanation),
reference costs with site-specific items removed. Open access, CC BY 4.0.

| Item | Value | Label | Where |
|---|---|---|---|
| Section costs, 20 MW biomethane reference | fuel handling 50.4, gasification + combustion 29.49, primary gas cleaning 23.78, flue gas 18.93, tar adsorption 10.62, compressor 34.59, olefin hydrogenation 9.06, H2S scrubber 9.15, WGS 5.29, premethanation 5.15, CO2 scrubber 17.57, methanation 19.41, drying/odorisation 4.97 MSEK (2014); total 238.41 MSEK | cited | Table 2 |
| Auxiliary equipment and project costs (flare, DCS, power distribution, civil, steel, piping, engineering, construction, start-up…) | 955.06 MSEK (reference, project-specific items removed) | cited | Table 2 |
| External fuel handling, belt dryer (100 MW product) | 280 + 60 MSEK | cited | Table 3 |
| Scale factors | reactor systems 0.68, auxiliary/project 0.44, external fuel handling/dryer 0.67 | cited | Table 4 |
| Reference efficiency | 70 % (dry biomass → biomethane, LHV) | cited | Sect. 2 |
| Development cost | 10 % of investment over the lifetime | cited | Sect. 2 |
| O&M, commercial 20 MW plant at 8000 h | personnel 181, maintenance 89, consumables 55.1, other 26.5 SEK/MWh; SF 0.10 / 0.67 / 1.00 / 0.67 | cited | Table 4 |
| Full-load hours | 8000 h/yr | cited | Sect. 2 |
| Forest residue price (Gothenburg region) | 170 SEK/MWh (as received) | cited | Tables 4–5 |

**How it is used (derived/assumption):**

* *Gasification island* = fuel handling + gasification + gas cleaning + flue gas + tar
  adsorption (133.2 MSEK), scaled on **biomass LHV input** against the reference input
  20 MW / 0.70 = 28.6 MW with SF 0.68. Auxiliary/project costs are allocated pro rata to the
  process-system cost (×955.06/238.41 = ×4.0) and scaled with SF 0.44. External fuel handling +
  dryer are added (SF 0.67). **No steam cycle**: the plant buys electricity. As a check, the
  paper's own Table 4 total for the reference plant, including the steam cycle, comes out at
  1377 MSEK vs the 1375 MSEK reported (unit test).
* The **same island cost is used for air, oxygen and DFB steam gasification** (assumption).
  GoBiGas is a DFB plant. An air-blown fluidised bed is simpler, and an oxygen-blown one needs O2
  handling but no combustor. This is a screening simplification, and it probably overstates
  air-gasifier cost.
* *Methanation section* = compressor + olefin hydrogenation + H2S scrubber + premethanation
  + methanation + drying (82.3 MSEK). WGS and the CO2 scrubber are left out because the plant
  model adds external H2 instead of shifting and does not remove CO2 (plant-model assumption
  A14). It is scaled on fuel-gas LHV output against 20 MW, with the same auxiliary share.
* *O&M* is scaled on product-gas LHV capacity against 20 MW with the cited SFs and allocated by
  the share of process-system cost present (gas island 56 %, island + methanation 90 %).

## 2. Methanation, H2 storage, O2 value: Götz et al. (2016)

| Item | Value | Label | Where |
|---|---|---|---|
| Catalytic methanation investment (Outotec) | 400 EUR/kW_SNG at 5 MW, 130 EUR/kW_SNG at 110 MW (2014, 20 bar) | cited | Sect. 5.3.1.1 |
| PtG plant, 36 MW electrolysis, case 1 | H2 storage 1700 m³ at 30–200 bar = 8.3 MEUR; compressor 1 MEUR | cited | Table 8 |
| O2 price range used for O2 sales | 10 and 70 EUR/t (quoting Vandewalle et al.) | cited | Sect. 5.3.2.1 |

**Derived:** methanation power law through both Outotec points, C = 400·(P/5)^-0.364 EUR/kW,
which gives about 242 EUR/kW at 20 MW. It is used as the **low** methanation case
(`methanation_goetz_weight = 1`). H2 storage cost per usable kg: the 1700 m³ is taken as
geometric volume. Densities come from the truncated virial equation with B ≈ 14 cm³/mol at
25 °C, which gives 14.6 / 2.4 kg/m³ at 200 / 30 bar, so about 20,800 kg usable and
**≈ 400 EUR(2014)/kg H2**. O2 storage is costed at the **same cost per mol stored**
(assumption: same pressure vessels), i.e. ≈ 25 EUR(2014)/kg O2. The storage compressor is
1 MEUR / 36 MW_el, about 28 EUR(2014)/kW_el of electrolyser, and is added whenever storage is
present.

## 3. Electrolyser: Schmidt et al. (2017)

| Item | Value | Label | Where |
|---|---|---|---|
| AEC system capital cost (current at publication) | 1000–1200 EUR(2016)/kW_el | cited | Table 1 |
| PEMEC system capital cost | 1860–2320 EUR(2016)/kW_el | cited | Table 1 |
| AEC 2030 (50th percentile, current R&D, no scale-up) | 750 EUR/kW_el | cited | "Capital costs" |
| AEC stack lifetime | 60,000–90,000 h | cited | Table 1 |

Central 1100 EUR(2016)/kW (AEC midpoint) ≈ 1413 EUR(2025)/kW. Range 750 (AEC 2030) to 2320
(PEMEC upper). Stack life 75,000 h. Stack replacement 40 % of electrolyser CAPEX
(assumption). Fixed O&M 2 %/yr (assumption).

## 4. Prices

| Item | Value | Label | Source / licence |
|---|---|---|---|
| DE-LU day-ahead electricity | hourly, 2025-10-30 → 2026-10-30, mean 110.8 EUR/MWh | data | Energy-Charts.info (Fraunhofer ISE), CC BY 4.0; source Bundesnetzagentur / SMARD.de. Cached copy in `data/` |
| Natural gas, Germany, non-household band I4 (100,000–999,999 GJ/yr), **excl. taxes and levies** | 2026-S1 44.1 EUR/MWh (GCV); range 2019-S2 21.2 / 2022-S2 62.8 | data | Eurostat `nrg_pc_203`, CC BY 4.0 (file in `data/sources/`) |
| Wood chips (forest, 35 % moisture), Germany, annual mean 2025 | 32.40 EUR/MWh gross incl. 7 % VAT → **30.28 net**; north 43.91 gross (41.04 net) | cited | C.A.R.M.E.N. e.V., *Marktpreise Hackschnitzel* (accessed 2026-11-07). Only individual figures are cited; the data set is not redistributed |
| EU ETS allowance (EUA) | 76.02 EUR/t (German auctions, H1 2026 average) | cited | DEHSt, *German Auctioning of Emission Allowances*, quarterly reports Q1/Q2 2026 |

Gas is bought per kWh GCV. The plant model gives NG demand on an LHV basis (1.912 MWh_LHV per
MWh of heat at 1000 °C), so the cost uses the model's GCV/NCV ratio of 1.108 for the
illustrative H-gas composition. The EU ETS price is used as specified. Note: a single 19 MW_th
furnace is below the 20 MW EU ETS 1 combustion threshold, so in Germany it would face the
national fuel-emissions price (BEHG) / EU ETS 2 instead. The 50–200 EUR/t sensitivity covers
that range.

## References

* Götz, M., Lefebvre, J., Mörs, F., McDaniel Koch, A., Graf, F., Bajohr, S., Reimert, R., Kolb, T. (2016). Renewable Power-to-Gas: A technological and economic review. *Renewable Energy* 85, 1371–1390. https://doi.org/10.1016/j.renene.2015.07.066
* Schmidt, O., Gambhir, A., Staffell, I., Hawkes, A., Nelson, J., Few, S. (2017). Future cost and performance of water electrolysis: An expert elicitation study. *International Journal of Hydrogen Energy* 42(52), 30470–30492. https://doi.org/10.1016/j.ijhydene.2017.10.045
* Thunman, H., Gustavsson, C., Larsson, A., Gunnarsson, I., Tengberg, F. (2019). Economic assessment of advanced biofuel production via gasification using cost data from the GoBiGas plant. *Energy Science & Engineering* 7(1), 217–229. https://doi.org/10.1002/ese3.271
* Short, W., Packey, D.J., Holt, T. (1995). *A Manual for the Economic Evaluation of Energy Efficiency and Renewable Energy Technologies*. NREL/TP-462-5173. https://doi.org/10.2172/35391

All four DOIs were checked against api.crossref.org on 2026-11-07.
