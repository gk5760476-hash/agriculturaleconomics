# ACREWS — Agricultural Credit Resilience and Early-Warning System

Does formal agricultural credit respond differently to weather, production and price shocks in **Bihar**, **Maharashtra** and **All-India**? Term-paper research engine; see `docs/design/` for the design plan.

## Run everything

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe src\build_msp_table.py     # MSP transcription
.venv\Scripts\python.exe src\ingestion.py all       # raw -> interim   (~5 min)
.venv\Scripts\python.exe src\transformations.py     # interim -> processed
.venv\Scripts\python.exe src\validation.py          # availability matrix + data checks
.venv\Scripts\python.exe src\shock_indicators.py    # pre-specified shocks
.venv\Scripts\python.exe src\models.py              # state time-series models -> reports/tables
.venv\Scripts\python.exe src\district_panel.py      # district-year panel models
.venv\Scripts\python.exe src\district_robustness.py # pre-registered stress tests + mechanism split
.venv\Scripts\python.exe src\early_warning.py       # monitoring categories + backtests
.venv\Scripts\python.exe src\forecasting.py         # out-of-sample forecast validation
.venv\Scripts\python.exe src\reporting.py           # -> app/dashboard.html (open in any browser)
.venv\Scripts\python.exe -m pytest                  # tests
```

Or all stages in order: `.venv\Scripts\python.exe src\run_pipeline.py [--skip-ingestion]`.

```powershell
```

## Layout

| Path | What |
|---|---|
| `data/` | raw → interim → processed, plus metadata (see [data/README.md](data/README.md)) |
| `src/ingestion.py`, `transformations.py`, `validation.py` | Data pipeline |
| `src/shock_indicators.py` | Adverse-signed weather, production and price shocks (definitions fixed in the module docstring) |
| `src/models.py`, `diagnostics.py` | 7 headline + 8 robustness specifications; Newey-West / year-clustered SEs; restricted wild-bootstrap p-values; Benjamini-Hochberg q-values |
| `reports/tables/` | `model_coefficients.csv`, `cyclicality_summary.csv`, `model_diagnostics.csv`, `model_skipped.csv` |
| `reports/model_runs/` | One JSON per run: specs, input hash, seed, library versions |
| `src/district_panel.py` | 71-district panel, district + state×year fixed effects (De & Vij design); concordance in `data/metadata/district_concordance.csv` |
| `src/early_warning.py`, `config/project_config.yaml` | Rules-based monitoring categories, thresholds, backtests |
| `src/reporting.py`, `app/` | Builds the self-contained dashboard from saved outputs |
| `tests/` | pytest suite (34 tests; see [TESTING.md](TESTING.md)) |
| [docs/user_guide/USER_GUIDE.md](docs/user_guide/USER_GUIDE.md) | One-page dashboard guide with screenshots and worked scenarios |
| `reports/paper/` | Term paper (PDF) |
| `src/district_robustness.py`, `src/forecasting.py` | Pre-registered stress tests and mechanism split; out-of-sample forecast validation |
| `src/run_pipeline.py` | Everything in order: `python src/run_pipeline.py [--skip-ingestion]` |
| [METHODOLOGY.md](METHODOLOGY.md), [MODEL_CARD.md](MODEL_CARD.md) | Design, results, limitations, intended use |
| [ROADMAP.md](ROADMAP.md), [PRD.md](PRD.md), [POLICY_FRAMEWORK.md](POLICY_FRAMEWORK.md), [TESTING.md](TESTING.md), [DEPLOYMENT.md](DEPLOYMENT.md), [SECURITY_PRIVACY.md](SECURITY_PRIVACY.md) | Plan and audit, requirement status, policy reading, tests, running and maintenance, privacy |
| [DATA_DICTIONARY.md](DATA_DICTIONARY.md) | Every processed variable |

## Reading the results

Shocks are signed so that **positive = worse conditions**. A positive coefficient therefore means credit grows faster after an adverse shock (**countercyclical**), and a negative one means it slows (**procyclical**). A wild-bootstrap p ≥ 0.10 is reported as **inconclusive**. Estimates are conditional associations from about 20 annual observations per region, not causal effects.
