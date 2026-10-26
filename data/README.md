# Data — ACREWS (Bihar, Maharashtra, All-India)

All files were pulled from the project Google Drive folder on 2026-10-24
(`data/metadata/download_manifest.csv` records Drive path, file ID, size, SHA-256 and retrieval time for every file).

Rebuild everything below `interim/` and `processed/` from `raw/` with:

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe src\build_msp_table.py    # MSP transcription -> raw/prices/msp/*.csv
.venv\Scripts\python.exe src\ingestion.py all      # raw -> interim  (~5 min, credit workbook is 2.2M rows)
.venv\Scripts\python.exe src\transformations.py    # interim -> processed
.venv\Scripts\python.exe src\validation.py         # availability matrix + checks
```

## Layout

| Folder | Contents | Rule |
|---|---|---|
| `raw/credit/` | RBI DBIE BSR-1 workbook: SCB credit by district × population group × bank group × occupation, 2010–2026 (127 MB) | Never edited |
| `raw/rainfall/imd_0p25_netcdf/` | IMD 0.25° daily gridded rainfall, NetCDF3 (1971–72, 1994, 1996–2000, 2010–21, 2023–25) | Never edited |
| `raw/rainfall/imd_0p25_grd/` | Same IMD product in native binary `.grd` (1973–80, 1983–93, 1995) | Never edited |
| `raw/state_handbook/` | RBI Handbook of Statistics on Indian States 2024-25: 47 tables — foodgrains (62/71/84), crops by type (58–87), GSDP/GSVA incl. agriculture (21–32), irrigation (55–56), sub-division rainfall (102), CPI (108–109), SCB credit/deposits incl. **agri credit from 2003-04 (157)** | Never edited |
| `raw/prices/wpi/` | WPI financial-year and monthly indices, bases 2004-05, 2011-12, 2022-23 (Office of the Economic Adviser) | Never edited |
| `raw/prices/msp/` | DES MSP table 1995-96 to 2026-27 (PDF, git-ignored: p.1 has personal data) and its transcription `des_msp_2004-05_to_2026-27_transcribed.csv` | Rebuild CSV with `src/build_msp_table.py` |
| `raw/policy/` | `policy_events.csv` — 13 hand-coded events with source URL and verification status | Edit by hand, cite every change |
| `raw/geo/` | Survey of India / NWIC district boundaries (EPSG:7755) | Never edited |
| `interim/credit/` | `bsr1_scb_credit_district_long.parquet` — the workbook's three data sheets stacked into one tidy table, labels as published | Reproducible |
| `interim/rainfall/` | `region_grid_masks.csv` (grid cell → All-India / state / district), `imd_region_monthly_rainfall.csv` (region × year × month, mm) | Reproducible |
| `interim/foodgrains/` | Tables 62/71/84 merged, all states | Reproducible |
| `interim/prior_work/` | `panel.csv`, `stage1_results.csv` from an earlier pipeline (code not supplied) — kept as a reconciliation reference, **not** used as input | Reference only |
| `processed/` | Analysis-ready tables (see below) | Reproducible |
| `metadata/` | Source register, download manifest, availability matrix, validation results, cleaning log, the two source-index workbooks | |

## Processed tables

| File | Grain | Notes |
|---|---|---|
| `credit_region_year.csv` | Bihar / Maharashtra / All-India × end-March year, 2010–2026 | Agri direct, indirect, total, direct non-metro, direct rural, limit, accounts, non-agri, total; log growth (%) |
| `credit_state_year_detail.csv` | All states × year × population group × bank group × occupation | District sums, labels harmonised |
| `credit_agri_district_year_focus.csv` | Bihar & Maharashtra districts × year × direct/indirect | Historical DBIE district names; matched to boundary-file districts via `metadata/district_concordance.csv` (built by `src/district_panel.py`; 71 analysis units) |
| `rainfall_region_year.csv` | All-India, Bihar, Maharashtra and their 74 districts × calendar year | JJAS & annual totals, departure from 1971–2020 normal, standardised anomaly, IMD category, <75% LPA flag |
| `foodgrains_region_year.csv` | Bihar / Maharashtra / All-India × crop year | Production, area, yield, growth, yield cross-check |
| `credit_agri_long_region_year.csv` | Region × end-March year, 2004–2026 | Total agri credit: HBS Table 157 for 2004–2009, DBIE from 2010 (agree within 0.003% on overlap) |
| `macro_region_year.csv` | Region × FY | Agri GSVA and GSDP (current and constant 2011-12, ₹ crore), agri share of GSDP, CPI inflation |
| `wpi_crop_prices_fy.csv` | Crop item × FY, 2004-05–2025-26 | WPI spliced to 2011-12 = 100, real index (÷ all-commodities WPI), real price growth |
| `msp_crop_year.csv` | Crop × crop year | MSP ₹/quintal, growth, bonus notes |
| `analysis_panel_state_year.csv` | Region × credit year *t* | Credit at end-March *t* (long series from 2004); monsoon of calendar year *t−1*; crop year (*t−1*)–*t*; FY (*t−1*)–*t* GSVA, WPI deflator, real crop-price growth; loan-waiver and macro-shock dummies |

## Timing alignment

Credit year *t* = amount outstanding at **end-March t** (FY *t−1*/*t*). It is matched to the **June–September monsoon of calendar year t−1** and the **agricultural year (t−1)–t**, following De & Vij (2013) and the design plan, so every shock predates the credit observation.

## Known gaps and caveats

Closed on 2026-10-24: rainfall now 1971–2025 with no missing years; WPI crop prices and deflator, MSPs, agricultural GSVA, CPI and policy events added; agricultural credit extended back to March 2004 (about 21 growth years per region).

| Remaining gap | Effect | How to close |
|---|---|---|
| Crop prices are **national** WPI, not state prices | Price shocks are identical for both states (only crop mix differs); state comparison of price shocks rests on crop weights | Agmarknet state mandi prices (no bulk download; needs scraping or data.gov.in API key) |
| Longer credit (2004–2009) is **total** agri only | Direct/indirect and non-metro splits start 2010 | Older DBIE BSR-1 exports, if needed |
| Agri GSVA (base 2011-12) starts **2011-12** | Control unavailable for credit years 2004–2011 | Splice with the 2004-05-base files already in `raw/state_handbook/*-2004.csv` |
| CPI inflation (Table 108) starts **2014-15** | Use WPI all-commodities as the deflator for the full span | — |
| HBS mirror values spot-checked against RBI (2026-10-26, `metadata/manual_verification_checklist.csv`) | — | — |
| Policy events verified (2026-10-26): every event now cites an official source (Lok Sabha, RBI, PIB/PMO, Maharashtra GRs for EV-08 and EV-12, Bihar Cooperative Department for EV-10) | EV-10's kharif-2018 start rests on a PTI report quoting the Cooperative Department; no Bihar notification found online | Add the Bihar cabinet resolution if it turns up |
| `Data/Model/grd` on Drive is a **0-byte file** | Nothing lost locally; recorded in manifest | Ask the uploader what it was meant to be |
