# Testing

```powershell
.venv\Scripts\python.exe -m pytest              # all 29 tests (~1 min, includes the end-to-end run)
.venv\Scripts\python.exe -m pytest -m "not slow" # unit tests only (~2 s)
```

| File | Covers (spec s.24) |
|---|---|
| `tests/test_core.py` | HAC and cluster SEs match statsmodels exactly; wild bootstrap reproducible and powered; BH q-values; classification rule; yield detrending; price weights; rainfall departure, credit growth and WPI splice formulas; shock signs; missing values never zero |
| `tests/test_district.py` | Fixed-effect partialling equals a dummy-variable regression; district units unique (Aurangabad in both states); every district has rainfall |
| `tests/test_early_warning.py` | Every flag has a reason; quiet rows with gaps are "Data insufficient"; the 2015 Maharashtra drought is flagged; backtest rates are probabilities |
| `tests/test_robustness_forecasting.py` | Mechanism family has 24 BH q-values; two-way SEs reported; forecasts use only past data; naive baseline scores 1 |
| `tests/test_integration.py` | Interim data → processed → all models → dashboard, and the dashboard's embedded data is complete. Runs on a scratch copy (`ACREWS_ROOT`), so the real `data/processed`, `reports/` and `app/dashboard.html` are not overwritten |

Data checks run separately (`src/validation.py` → `data/metadata/validation_results.csv`): 19 checks, each PASS / WARN / FAIL; one expected WARN (Mumbai districts use the nearest rainfall cell — any other district needing the fallback is a FAIL).

**Visual check of the dashboard:** headless Edge screenshots at 1200 px and in a 390 px iframe. The JS console must show no `Uncaught` errors on any tab.
