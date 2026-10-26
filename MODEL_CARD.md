# Model card — ACREWS

**Version:** 0.1 (2026-10-26) · **Code:** `src/models.py`, `src/district_panel.py`, `src/early_warning.py` · **Run records:** `reports/model_runs/`

## Intended use
Aggregate research and monitoring of how bank credit to agriculture moves with monsoon, yield and crop-price shocks in Bihar, Maharashtra and All-India; identifying periods and districts worth closer examination.

## Not intended for
Individual credit scoring, loan approval or rejection, eligibility decisions, automatic allocation of public funds, causal claims about bank behaviour, or forecasts of distress or default.

## Inputs
RBI DBIE BSR-1 credit (district, 2010–2026) and RBI Handbook Table 157 (state, 2004–2009); IMD 0.25° gridded rainfall 1971–2025; RBI Handbook foodgrain and crop tables; WPI (Office of the Economic Adviser); DES MSPs; hand-coded policy events. See `data/metadata/source_register.csv`.

## Outputs
Coefficients with 90% intervals, wild-bootstrap p-values and BH q-values (`reports/tables/`); cyclicality labels (countercyclical / procyclical / inconclusive); monitoring categories with reasons; `app/dashboard.html`.

## Performance and validation
- Estimation core matches statsmodels (HAC, cluster) exactly — `tests/test_core.py`.
- Placebo (later monsoon): passes in the district panel (p = 0.41); **fails for Maharashtra in the state series (p = 0.035)**, a reminder that state-level estimates can be chance.
- Early-warning backtest: no predictive skill (district lift 0.9–1.1; state precision 0.25–0.75 against a base rate of 0.5).
- Out-of-sample credit-growth forecasts (2016–2025): no model beats the naive past-average forecast; shock models are 4–49% worse. **Do not use the scenario tool as a forecast.**
- The Bihar lagged effect survives an event-study pre-trend check and two-way clustering, but shrinks by about 40% with district-specific trends.
- Leave-one-drought-out (8 drought years): full model MAE 5.4 pp vs naive 6.1 pp, closer in 6 of 8 years (not significant; uses later years). MAPE is reported but meaningless near zero growth.
- Alternative drought definitions (75% / 70% of normal, SPI) and controls (non-agricultural credit, GSDP) leave every weather effect inconclusive. ADF/KPSS: shocks stationary; credit growth ambiguous for Bihar and All-India.
- The state scenario tool's prediction intervals are 30–60 pp wide: they show how little a year's credit growth is pinned down by shocks.

## Known failure cases
- Maharashtra state credit includes metro-booked lending (Mumbai), which swings by ₹ thousands of crore a year.
- Loan-waiver years (2008; Maharashtra 2018 and 2020) produce large credit falls unrelated to new lending.
- A Bihar rainfall deficit against the 1971–2020 normal is common in recent years, so Bihar is often on "Watch".
- Scenarios beyond the observed district rainfall range, or beyond a region's 2006–2025 monsoon, yield or price range in the state tool, are flagged as extrapolation (All-India never had a monsoon below −15% in that window).

## Human oversight
A qualified analyst must review data quality, uncertainty and local context before any policy use. A flag means "verify on the ground", never "act".
