"""ACREWS Credit Monitor - Streamlit front end (design plan s.8, Option B).

Same content and numbers as app/dashboard.html (Option A); both read the saved
pipeline outputs through src/reporting.collect(). Run from the repo root (as
Streamlit Community Cloud does) so the theme in .streamlit/config.toml applies:

    .venv\\Scripts\\streamlit run streamlit_app/app.py --server.address 127.0.0.1
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="ACREWS Credit Monitor", page_icon="🌾", layout="wide")

import views  # noqa: E402  (after set_page_config)
from data import load  # noqa: E402

D = load()

st.title("Agricultural Credit Monitor — Bihar, Maharashtra, All-India")
st.caption("How formal bank credit to agriculture moves with monsoon, yield and crop-price shocks. "
           "Research prototype: associations, not causal proof.")

PAGES = [("Overview", views.overview), ("Credit trends", views.credit), ("Weather & agriculture", views.agriculture),
         ("Results", views.results), ("Early warning", views.early_warning), ("Data & methods", views.methods)]
for tab, (_, page) in zip(st.tabs([name for name, _ in PAGES]), PAGES):
    with tab:
        page(D)

st.divider()
run = f" · model run {D['model_run']}" if D["model_run"] else ""  # run records are git-ignored, so absent on a hosted copy
st.caption(f"Generated {D['generated']} from saved outputs{run} · ACREWS research prototype. "
           "Sources: RBI (DBIE BSR-1, Handbook of Statistics on Indian States), IMD gridded rainfall, "
           "Office of the Economic Adviser (WPI), DES (MSP).")
