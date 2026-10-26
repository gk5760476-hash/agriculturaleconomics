# Methodology

## Question
Does formal agricultural credit rise (countercyclical), fall (procyclical) or not respond when Bihar and Maharashtra are hit by weather, production and price shocks?

## Timing
Credit year *t* is the amount outstanding at **end-March t**. It is matched to the **June–September monsoon of calendar year t−1**, the **agricultural year (t−1)–t** and **prices of financial year (t−1)–t**, so every shock predates the credit observation (De & Vij 2013).

## Shock definitions (fixed before estimation — `src/shock_indicators.py`)
Every shock is signed so that **larger = worse for farmers**; a positive coefficient therefore means countercyclical credit.

| Shock | Definition |
|---|---|
| Weather | Monsoon shortfall = −(JJAS departure from the 1971–2020 mean), IMD 0.25° grid averaged over the region/district |
| Drought flag | Departure ≤ −20% (IMD "deficient"); robustness: below 75% / 70% of normal (≤ −25% / −30%), SPI ≤ −1 |
| SPI | JJAS total through a gamma distribution fitted on 1971–2020, then the standard-normal quantile |
| Production | Foodgrain yield % below a region-specific linear trend |
| Price | Area-weighted fall in real WPI of the region's crops; weights = 2004-05–2006-07 crop areas (Bihar: 48% rice, 30% wheat; Maharashtra: 34% coarse cereals, 18% oilseeds, 18% pulses, 15% cotton) |

## Two designs

**1. State time series** (`src/models.py`) — Bihar, Maharashtra, All-India, real credit growth 2006–2026 (~20 years). Seven headline and eight pre-specified robustness specifications, plus six more from the design plan (R9–R14) added after the headline results were known. Newey-West (1 lag) standard errors; pooled model clusters by year. P-values from a restricted wild bootstrap (Rademacher, 9,999 draws); Benjamini–Hochberg q-values across headline tests. Binary shocks with < 3 events are refused rather than estimated.

**2. District panel** (`src/district_panel.py`) — 71 districts (38 Bihar, 33 Maharashtra), 2010–2026, 1,207 district-years:

  100·log(credit_dt) = α_d + λ_st + β·shortfall_d,t−1 + ε_dt

District effects absorb permanent differences; **state × year** effects absorb anything common to a state in a year (waivers, national policy, prices, inflation). β is identified only from rainfall differences between districts of the same state in the same year. Standard errors are clustered by district, with wild-cluster-bootstrap p-values. Mumbai and Mumbai Suburban are excluded (metro-booked lending), and Thane + Palghar are merged.

## Results (run of 2026-10-26)

| Finding | Estimate (20-point monsoon shortfall) | Evidence |
|---|---|---|
| No immediate countercyclical rise (both states, D1) | −0.7% credit next March, 90% CI −1.7 to +0.4 | Inconclusive, but excludes De & Vij's +3–5% |
| Bihar: lower credit 2–3 years later (D10) | −3.9% and −4.0% | p ≤ 0.001, q ≈ 0.01 |
| …with district-specific trends (D15) | −2.3% and −2.3% | p = 0.034 / 0.008; q = 0.16 / 0.06 |
| Maharashtra: no delayed effect (D11) | +0.4% / +0.3% | Inconclusive |
| Placebo: the following monsoon (DP) | −0.5% | p = 0.41 (passes) |
| State time series (M4), all shocks | — | 1 of 9 effects significant (Bihar price, p = 0.08); none survives BH |

Bihar had no state loan waiver, so the delayed fall is not a write-off artefact. Because the estimate shrinks by about 40% once district trends are added, it is reported as **suggestive**.

### Stress tests (pre-registered in ROADMAP.md, `src/district_robustness.py`)

| Test | Result |
|---|---|
| Event study, Bihar (E2) | Placebo monsoons t+1 and t: −0.4%, −0.8% (p = 0.66, 0.43) — no pre-trend. Monsoon t−1: −0.5%; t−2: −3.6%; t−3: −2.9%; t−4: −2.9% (p ≤ 0.004) |
| Two-way clustering, district + state-year (I1) | Bihar t−2 / t−3: p = 0.003 / 0.023; pooled: p = 0.08 / 0.09 |
| Mechanism, Bihar, monsoon t−3 (K1–K8, one BH family of 24) | Accounts −4.5% (q = 0.006); average loan size +0.4% (n.s.); sanctioned limit −5.3% (q = 0.005); RRBs −4.7% (q = 0.02); rural branches −3.8% (q = 0.006); public banks −1.0% (n.s.); private banks −1.5% (n.s., noisy) |

So the delayed fall is in the **number of borrowers**, at **regional rural banks** and **rural branches** — not in loan size or private banks, the opposite of De & Vij's national finding. RRBs also show a short-lived rise in the first year (+4.2%, q = 0.11). The mechanism specs carry no district trends (as pre-registered), so they share the D15 caveat.

### Out-of-sample forecasting (`src/forecasting.py`)
Expanding-window one-year-ahead forecasts of real credit growth (2016–2025): **no model beats the naive past-average forecast**. Shock-based models are 4–49% worse; an AR(1) is 11–13% better for All-India and Bihar but not significantly (p ≥ 0.11). Ranking Bihar districts by lagged shortfall gives a mean rank correlation of 0.16 with next year's credit growth (p = 0.10). The relationships are real in levels but too small to forecast with. MAPE is also reported (design plan) but runs to 300–1,000% because growth is often near zero, so MAE is the headline.

### Design-plan checks added 2026-10-26 (plan s.4, s.5.4, s.8)
| Check | Result |
|---|---|
| Drought below 75% of normal (R9) | Bihar −0.4 pp (p = 0.94); Maharashtra and All-India have ≤ 1 such year — not estimated |
| Drought below 70% of normal (R10) | ≤ 1 event in every region — not estimated |
| SPI ≤ −1 flag (R11) / continuous SPI (R12) | All weather effects inconclusive (p ≥ 0.31); SPI correlates 0.998 with the standardised anomaly |
| Control: real non-agricultural credit growth, 2011–2025 (R13) | All shock effects inconclusive; the control matters only for All-India (common credit cycle) |
| Control: real GSDP growth, Bihar 2013–2025 (R14) | Yield and price become procyclical (p = 0.03, 0.05) on 13 years; GSDP includes agriculture, so this is a weak check. Maharashtra has too few degrees of freedom |
| Leave-one-drought-out (8 drought credit years) | Mean absolute error: naive 6.1 pp, monsoon model 5.8, full model 5.4; the full model is closer in 6 of 8 years (sign test p = 0.29). It uses later years, unlike the rolling test |
| Unit roots (ADF + KPSS, 2006–2025) | All shock series stationary; real credit growth stationary for Maharashtra, ambiguous for Bihar and All-India (ADF rejects a unit root, KPSS rejects stationarity — low power at n = 20) |

With these checks, Bihar's price effect is significant with the same sign in 4 of 13 robustness specifications. None of the checks changes the conclusions.

## Early warning (`src/early_warning.py`, thresholds in `config/project_config.yaml`)
Rules-based categories (Normal / Watch / Elevated concern / Data insufficient), each with the indicators that fired. In backtests the signals do **not** anticipate weaker credit growth (district drought → below-median growth: lift 0.9–1.1), so the module is a descriptive monitor, not a forecast.

## Limitations
Credit is a stock (lending, rollovers, restructuring and write-offs are mixed together); the mechanism (supply vs demand) is not identified; crop prices are national; state series are short; policy events are coded by credit year, not month; district rainfall uses grid-cell centres (Mumbai uses the nearest cell).
