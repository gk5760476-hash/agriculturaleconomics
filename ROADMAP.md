# Roadmap — next course of action (2026-10-26)

## Where we are
Phases 1–7 of the master spec are built: data pipeline, shocks, state models, district panel, early warning, dashboard, METHODOLOGY / MODEL_CARD, 24 tests. Headline finding: **no immediate countercyclical response; Bihar credit lower 2–3 years after a district monsoon shortfall (suggestive)**.

## Candidate work, ranked

| # | Work | Why | Spec / plan ref | Effort |
|---|---|---|---|---|
| 1 | **Stress-test the Bihar finding**: two-way clustered SEs (district + state-year), event study with leads, mechanism split (accounts vs average loan size; bank groups; rural vs other) | The headline result rests on one specification family; reviewers will ask about spatial correlation, pre-trends and mechanism. De & Vij found the rise was in loan size and private banks — we can test the same | spec 20.1–20.4; design plan 2 | M |
| 2 | **Stage-2 forecasting validation**: rolling-origin out-of-sample test of credit growth vs a naive trend, plus leave-one-drought-out | Design plan s.5.2–5.4 promises it; the scenario slider currently has no out-of-sample check | design plan 5.2–5.4; spec 20.3 | M |
| 3 | **Verification**: spot-check HBS mirror values against RBI PDFs; re-cite press-sourced policy events; resolve EV-10 | Two documented data caveats | spec 6.2, 22.1 | S–M (RBI site blocks scripts) |
| 4 | **Engineering hygiene**: `git init` + first commit, raw→dashboard integration test, CSV export buttons, remaining spec docs (PRD, POLICY_FRAMEWORK, SECURITY_PRIVACY, TESTING, DEPLOYMENT) | FR-08/09/10, spec 16.1, 24.2 | S |
| 5 | **Term paper draft** | Main deliverable — but should wait until 1–2 settle the results | design plan 9–10 | L |

## Audit of this plan

| Check | Finding | Action |
|---|---|---|
| Does #1 risk a specification search? | Yes — adding outcomes until something is significant would overstate evidence | Specs pre-registered below **before** running; all reported; mechanism outcomes form their own BH family |
| Is the data for #1 available? | Yes: `data/interim/credit/...parquet` has district × bank group × population group × accounts × limit, 2010–2026 | — |
| Is #1 inside scope? | Yes — aggregate district data, no individual inference (spec 5.6, 22.3) | — |
| Two-way clustering with 17 years | Few year clusters (34 state-years) — CGM variance can be unstable | Report alongside district clustering, not instead of it |
| Does #2 add value given no-skill early warning? | It answers the design plan's question honestly; a "no better than naive" result is still a result | Do it, report against naive baseline |
| #3 feasibility | rbi.org.in blocks scripted download; manual check needed | Prepare a spot-check sheet for the user; do not fabricate verification |
| #4 git | Local only, reversible; no remote push without asking | Init locally; large raw files already git-ignored |
| #5 timing | Writing before #1–2 would need rewriting | Do last; draft as a shareable document when results are final |
| Overall order | 1 → 2 → 4 → 3 (needs user) → 5 | — |

## Status (2026-10-26, end of session)
| # | Status | Outcome |
|---|---|---|
| 1 | **Done** | Bihar lag survives event study (clean placebos) and two-way clustering; mechanism = fewer borrowers at RRBs and rural branches. `reports/tables/district_robustness.csv` |
| 2 | **Done** | No model beats the naive forecast; district ranking weak (ρ = 0.16). `reports/tables/forecast_*.csv` |
| 3 | **Done** (verified by hand 2026-10-26) | `data/metadata/manual_verification_checklist.csv`; Maharashtra waivers still lack GR numbers |
| 4 | **Done except git** | `src/run_pipeline.py`, integration test (29 tests), CSV export, PRD / POLICY_FRAMEWORK / SECURITY_PRIVACY / TESTING / DEPLOYMENT. Git is not installed on this machine |
| 5 | **Drafted** | Term paper doc: https://claude.ai/artifact/PEtRG5xh4X95DEstbkZjFh (open question: De & Vij 2013 publication venue) |

## Pre-registered specifications for #1 (fixed 2026-10-26, before estimation)
All: district + state×year fixed effects, 2010–2026, Mumbai excluded, Thane+Palghar merged; shortfall = −(monsoon departure); effects reported per 20-point shortfall.

| ID | Outcome | Regressors | Sample | Question |
|---|---|---|---|---|
| E1 | log direct credit | event-time shortfall: monsoon *t+1*, *t* (both after the credit date — placebos), *t−1 … t−4* | Both | Pre-trends and dynamics |
| E2 | as E1 | as E1 | Bihar | Same, Bihar |
| I1 | D2 and D10 re-estimated with two-way clustered SEs (district, state-year) | — | Both / Bihar | Robust to cross-district correlation within a year? |
| K1 | log number of direct accounts | shortfall t−1, t−2, t−3 | Bihar | Fewer borrowers… |
| K2 | log average direct loan (outstanding / accounts) | same | Bihar | …or smaller loans? |
| K3 | log direct credit limit (sanctioned) | same | Bihar | Sanctions vs outstanding |
| K4 | log direct credit, public sector banks | same | Bihar | Which lenders? |
| K5 | log direct credit, private sector banks | same | Bihar | |
| K6 | log direct credit, regional rural banks | same | Bihar | |
| K7 | log direct credit, rural branches | same | Bihar | Where? |
| K8 | log direct credit, semi-urban + urban branches | same | Bihar | |

Mechanism specs K1–K8 form one Benjamini–Hochberg family (24 tests).
