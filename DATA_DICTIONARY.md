# Data dictionary

Sources are identified by `source_id` in [data/metadata/source_register.csv](data/metadata/source_register.csv). Units are nominal unless stated otherwise.

## `credit_region_year.csv` — SRC-CREDIT-01

| Column | Definition | Unit |
|---|---|---|
| region | Bihar, Maharashtra, All-India (sum of all states/UTs) | — |
| year | End-March reference year (2011 = 31 March 2011, FY 2010-11) | year |
| agri_direct_outstanding_cr | Amount outstanding, occupation `I. AGRICULTURE` / `1. Direct Finance` (loans to farmers) | ₹ crore |
| agri_indirect_outstanding_cr | Amount outstanding, `2. Indirect Finance` (loans to agri-related institutions/firms) | ₹ crore |
| agri_total_outstanding_cr | Direct + indirect | ₹ crore |
| agri_direct_nonmetro_outstanding_cr | Direct finance excluding metropolitan centres (removes Mumbai-booked lending) | ₹ crore |
| agri_direct_rural_outstanding_cr | Direct finance in rural centres only | ₹ crore |
| agri_direct_limit_cr | Sanctioned credit limit, direct finance (not the same as outstanding) | ₹ crore |
| agri_direct_accounts | Number of direct-finance loan accounts | count |
| nonagri_outstanding_cr | All SCB credit except agriculture | ₹ crore |
| total_outstanding_cr | All SCB credit | ₹ crore |
| agri_share_of_total_pct | Agricultural share of total credit | % |
| *_growth_pct | 100 × [log(Cₜ) − log(Cₜ₋₁)] | % (log points) |

Concept: **stock outstanding at end-March**, scheduled commercial banks incl. RRBs and small finance banks; excludes cooperative banks. Not disbursement.

## `rainfall_region_year.csv` — SRC-RAIN-01/02, SRC-GEO-01

| Column | Definition | Unit |
|---|---|---|
| region_id | `All-India`, `Bihar`, `Maharashtra`, or `State|District` | — |
| state, district | District blank for state/national rows | — |
| year | Calendar year | year |
| annual_mm, jjas_mm | Area-mean total rainfall, Jan–Dec and June–September | mm |
| n_cells | 0.25° grid cells assigned to the region | count |
| jjas_normal_mm, annual_normal_mm | Mean over available years 1971–2020 (`normal_n_years`) | mm |
| jjas_sd_mm | Standard deviation of JJAS rainfall over the normal period | mm |
| jjas_departure_pct | 100 × (JJAS − normal) / normal | % |
| jjas_standardised_anomaly | (JJAS − normal) / SD | SD units |
| annual_departure_pct | As above for annual totals | % |
| jjas_imd_category | IMD bands: Large deficient ≤ −60, Deficient −59…−20, Normal −19…+19, Excess +20…+59, Large excess ≥ +60 | — |
| jjas_below_75pct_lpa | 1 if JJAS < 75% of normal (De & Vij drought definition) | 0/1 |

## `foodgrains_region_year.csv` — SRC-FOOD-01/02/03

| Column | Definition | Unit |
|---|---|---|
| region, crop_year, crop_year_start | Agricultural year July–June; `2015-16` has start 2015 | — |
| foodgrain_production_kt | Total foodgrains production (HBS Table 62) | thousand tonnes |
| foodgrain_area_kha | Area under total foodgrains (Table 71) | thousand hectares |
| foodgrain_yield_kg_ha | Published yield (Table 84) | kg/ha |
| yield_check_kg_ha, yield_check_diff_pct | 1000 × production / area, and % gap from published yield (max 0.24%) | kg/ha, % |
| production_growth_pct, yield_growth_pct | Log growth × 100 | % |

## `credit_agri_long_region_year.csv` — SRC-HBS-01 (Table 157), SRC-CREDIT-01

| Column | Definition | Unit |
|---|---|---|
| agri_total_hbs_cr | HBS Table 157 credit to agriculture by SCBs (rupees ÷ 1e7), end-March year = HBS start year + 1 | ₹ crore |
| agri_total_dbie_cr | DBIE `agri_total_outstanding_cr` | ₹ crore |
| agri_total_long_cr, agri_total_long_source | DBIE where available, else HBS | ₹ crore |
| agri_total_long_growth_pct | Log growth × 100 | % |

## `macro_region_year.csv` — SRC-HBS-01 (Tables 21, 22, 29, 30, 108)

`agri_gsva_current_cr`, `agri_gsva_constant_2011_12_cr`, `gsdp_current_cr`, `gsdp_constant_2011_12_cr` (₹ crore), `agri_share_gsdp_pct` (%), `cpi_inflation_pct` (average annual CPI inflation, %). Keyed by `fiscal_year` / `period_start`.

## `wpi_crop_prices_fy.csv` — SRC-WPI-01

| Column | Definition | Unit |
|---|---|---|
| item | paddy, wheat, maize, gram, arhar, moong, urad, potato, onion, sugarcane, raw_cotton, soyabean, rapeseed_mustard, primary_articles, all_commodities | — |
| wpi_2011_12 | Index rebased to 2011-12 = 100 (2004-05 base linked at 2011-12) | index |
| wpi_source_base | Which published base supplied the value | — |
| real_wpi_2011_12 | 100 × item / all-commodities WPI | index |
| real_price_growth_pct | Log growth × 100 of the real index | % |

## `msp_crop_year.csv` — SRC-MSP-01

`season_type` (KMS/RMS), `marketing_season`, `crop`, `variety`, `msp_rs_per_quintal`, `note` (bonus footnotes), `crop_year` (KMS *t*/*t*+1 and RMS *t*+1/*t*+2 → crop year *t*/*t*+1), `msp_growth_pct`.

## `analysis_panel_state_year.csv`

One row per region × credit year *t*: every `credit_region_year` column; `monsoon_year` (= *t*−1) with `monsoon_*` rainfall columns; `crop_year` (*t*−1)–*t* with foodgrain columns; `agri_total_long_*` (from 2004); `macro_region_year` columns for FY (*t*−1)–*t*; `wpi_all_commodities_2011_12` (deflator) and `agri_total_long_real_cr_2011_12` (real credit, 2011-12 prices); `wpi_real_growth_<crop>_pct` for FY (*t*−1)–*t*; `loan_waiver_year`, `macro_shock_year` (0/1) with the event IDs. Missing inputs stay blank, never zero.

## `shocks_region_year.csv` — built by `src/shock_indicators.py`

One row per region × credit year *t* (2004–2026). Adverse shocks are signed so that larger = worse for farmers.

| Column | Definition | Unit |
|---|---|---|
| rain_departure_pct, rain_shortfall_pct | JJAS departure of monsoon *t*−1 from the 1971–2020 mean; shortfall = −departure | % |
| rain_deficit_pct, rain_excess_pct | max(0, shortfall), max(0, −shortfall) | % |
| drought_flag, drought_flag_75lpa, drought_flag_70lpa | Departure ≤ −20% / ≤ −25% / ≤ −30% (below 80% / 75% / 70% of normal) | 0/1 |
| excess_flag | Departure ≥ +20% | 0/1 |
| rain_standardised_shortfall | −(JJAS total − 1971–2020 mean) ÷ 1971–2020 standard deviation | SD |
| rain_spi_shortfall, spi_drought_flag | −SPI (gamma fit on 1971–2020 JJAS totals); flag = SPI ≤ −1 | SD, 0/1 |
| rain_shortfall_lag2_pct, rain_shortfall_lead_placebo_pct | Shortfall of monsoon *t*−2, and of monsoon *t* (after the credit date — placebo) | % |
| yield_deviation_pct, yield_shortfall_pct | 100 × residual of log foodgrain yield on a region linear trend; shortfall = −deviation | % |
| crop_real_price_growth_pct, price_fall_pct | Area-weighted real WPI growth of the region's crops (2004–07 weights); fall = −growth | % |
| credit_real_growth_pct, credit_nominal_growth_pct | Log growth × 100 of agricultural credit (real = deflated by all-commodities WPI) | % |
| credit_direct_growth_pct, credit_direct_nonmetro_growth_pct | Same for direct and non-metro direct credit (2011 on) | % |
| credit_real_growth_rel_allindia_pct, credit_real_growth_lag1_pct | Region minus All-India; previous year's real growth | pp, % |
| nonagri_real_growth_pct | Real growth of non-agricultural SCB credit (control, 2011 on) | % |
| gsdp_real_growth_pct | Growth of GSDP at constant 2011-12 prices (control, states, FY 2012-13 on) | % |
| loan_waiver_year, macro_shock_year | Policy-event dummies (`data/raw/policy/policy_events.csv`) | 0/1 |

## Status vocabulary (`data_availability_matrix.csv`)

`observed` — value present; `missing` — the source exists but has no value for that year; `not_collected` — no source has been obtained yet.
