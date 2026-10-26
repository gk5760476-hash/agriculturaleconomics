# Deployment

**Phase 1 — local (current).** Python 3.12.10 in `.venv`, versions pinned in `requirements.txt`, Windows 11. Rebuild everything with `python src/run_pipeline.py` (add `--skip-ingestion` to reuse `data/interim`). The dashboard is one self-contained file, `app/dashboard.html`: open it in any browser, offline; nothing is re-estimated when you click.

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
