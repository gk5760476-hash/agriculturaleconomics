# PRD status

The requirements are in the project master documentation (spec s.14). This file tracks how each is met.

| Req | Status | Where |
|---|---|---|
| FR-01 Data ingestion | Done | `src/ingestion.py` (Excel, CSV, NetCDF, GRD, GeoJSON) |
| FR-02 Validation | Done | `src/validation.py` → `data/metadata/validation_results.csv` |
| FR-03 Transformations | Done | `src/transformations.py`, `src/shock_indicators.py` |
| FR-04 Exploratory analysis | Done | Dashboard: Credit trends, Weather & agriculture |
| FR-05 Estimation within sample limits | Done | `src/models.py` refuses specs with < 8 residual df or < 3 events; `src/district_panel.py` |
| FR-06 Uncertainty | Done | 90% intervals, wild-bootstrap p, BH q on every estimate |
| FR-07 Early-warning indicators shown | Done | `src/early_warning.py`; every flag lists its indicators |
| FR-08 Provenance | Done | Source register, download manifest (SHA-256), cleaning log, model-run JSON |
| FR-09 Export | Done | CSV download on every dashboard table; all tables in `reports/tables/` |
| FR-10 Reproducibility | Done | `src/run_pipeline.py`, pinned `requirements.txt`, run JSON with versions and seed |
| Version control (s.16.1) | **Pending** | Git not installed on this machine |
| Out of scope (s.14.4) | Respected | No individual scoring, no automated decisions, no causal claims without identification |
