# ACREWS Credit Monitor — Streamlit app

The interactive web version of `app/dashboard.html` (design plan s.8, Option B). Same six tabs, same numbers: both front ends read the saved pipeline outputs through `src/reporting.py`, so nothing is re-estimated when you move a slider.

## Run it on this computer

From the repo root:

```powershell
.venv\Scripts\streamlit run streamlit_app/app.py --server.address 127.0.0.1
```

It opens at http://127.0.0.1:8501 and is reachable only from this computer. The theme lives in the repo-root `.streamlit/config.toml`, which is why the command runs from the root. Light or dark follows your system; switch it under ⋮ → Settings.

Refresh the numbers after new data with `.venv\Scripts\python.exe src\run_pipeline.py --skip-ingestion`, then press **R** in the app (or restart it) to clear its cache.

## Host it on Streamlit Community Cloud

1. Push `main` to GitHub (the app reads only files that are committed: `data/processed/`, `reports/tables/`, `data/metadata/`).
2. At [share.streamlit.io](https://share.streamlit.io), **Create app → Deploy a public app from GitHub**: repository `gk5760476-hash/agriculturaleconomics`, branch `main`, main file path `streamlit_app/app.py`.
3. Under **Advanced settings**, choose **Python 3.12**. No secrets are needed.
4. **Deploy.** Cloud installs `streamlit_app/requirements.txt` (the slim app list, not the pipeline's) and applies `.streamlit/config.toml`.

Every push to `main` redeploys the app. To publish new numbers: re-run the pipeline locally, commit the changed `data/processed/` and `reports/tables/` files, push.

## Files

| File | What |
|---|---|
| `app.py` | Entry point: page setup, the six tabs, footer |
| `data.py` | Loads the outputs once per session (`reporting.collect()`), number formatting, scenario arithmetic |
| `views.py` | One function per tab |
| `charts.py` | Altair charts: region colours and chart chrome match the HTML dashboard |
| `requirements.txt` | The app's own dependencies, used by Streamlit Community Cloud |
| `../.streamlit/config.toml` | Light and dark themes, usage statistics off |

`tests/test_streamlit_app.py` runs every tab headlessly and checks the scenario arithmetic.
