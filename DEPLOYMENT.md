# Deployment

**Phase 1 — local (current).** Python 3.12.10 in `.venv`, versions pinned in `requirements.txt`, Windows 11. Rebuild everything with `python src/run_pipeline.py` (add `--skip-ingestion` to reuse `data/interim`). The dashboard is one self-contained file, `app/dashboard.html`: open it in any browser, offline; nothing is re-estimated when you click.

**Interactive web app (design plan Option B).** `streamlit_app/` serves the same six tabs with Streamlit: from the repo root, `.venv\Scripts\streamlit run streamlit_app/app.py --server.address 127.0.0.1`, then open http://127.0.0.1:8501 (this computer only; no usage statistics, `.streamlit/config.toml`). It reads the same saved outputs through `src/reporting.py`. After re-running the pipeline, press **R** in the app to reload the numbers.

**Hosted web app (Streamlit Community Cloud).** Deploy from GitHub with main file `streamlit_app/app.py`, branch `main`, Python 3.12; Cloud installs the slim `streamlit_app/requirements.txt`. The hosted app serves the same aggregate tables that are already public in the repository, so it adds no new exposure; keep the "research prototype" labelling. Each push to `main` redeploys it — publish new numbers by committing the refreshed `data/processed/` and `reports/tables/` files.

**Phase 2 — sharing.** Send `app/dashboard.html` as an attachment, or publish it as a private link. It embeds only aggregate, published data (no personal data), so it is safe to share.

**Phase 3 — controlled hosting.** Any static host works (no server code). Before hosting: confirm the data licences of RBI, IMD, OEA and DES allow redistribution of the derived tables, and keep the "research prototype" labelling.

**Maintenance (spec s.26 Phase 4)**
| Task | When | How |
|---|---|---|
| New credit year (DBIE BSR-1, end-March) | Annually, ~Dec | Re-export the DBIE workbook to `data/raw/credit/`, re-run the pipeline |
| New monsoon (IMD) | After September | `imdlib.get_data('rain', YEAR, YEAR, fn_format='yearwise')` → `data/raw/rainfall/imd_0p25_grd/Rainfall_ind{YEAR}_rfp25.grd` |
| WPI / HBS / MSP | Annually | Same download URLs (`data/metadata/source_register.csv`); append MSP rows in `src/build_msp_table.py` |
| Thresholds | Only with a written reason | `config/project_config.yaml` + an entry in `data/metadata/cleaning_log.md` |
| Model change | Any | New run JSON is written to `reports/model_runs/` automatically |

Do not call the system "real-time": the slowest input (BSR-1 credit) arrives about nine months after its reference date.
