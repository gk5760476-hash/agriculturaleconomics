"""Saved ACREWS outputs and scenario arithmetic for the Streamlit app.

Loads everything through reporting.collect(), the same function that builds
app/dashboard.html, so both front ends show identical numbers. Nothing is
re-estimated on interaction; the only fit is collect()'s one-second refit of the
headline state model for its covariance, cached for the session.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import reporting  # noqa: E402  (needs src on the path)

REGIONS = reporting.REGIONS
STATES = ["Bihar", "Maharashtra"]
WHEN = ["Next March", "2 years on", "3 years on"]
# district-panel estimate behind each horizon (Bihar lags with district trends, as in the paper)
DISTRICT_LAGS = {
    "Bihar": [("D8", "rain_shortfall_pct"), ("D15", "rain_shortfall_lag2_pct"), ("D15", "rain_shortfall_lag3_pct")],
    "Maharashtra": [("D9", "rain_shortfall_pct"), ("D11", "rain_shortfall_lag2_pct"), ("D11", "rain_shortfall_lag3_pct")],
}
STATUS_ICON = {"Normal monitoring": "✅", "Watch": "⚠️", "Watch (lagged credit risk)": "⚠️",
               "Elevated concern": "🛑", "Data insufficient": "❔"}


@st.cache_data(show_spinner="Loading saved model outputs…")
def load() -> dict:
    return reporting.collect()


def frame(d: dict, key: str) -> pd.DataFrame:
    return pd.DataFrame(d[key])


def coef(d: dict, spec: str, term: str) -> pd.Series:
    t = frame(d, "district")
    return t[(t.spec == spec) & (t.term == term)].iloc[0]


# ------------------------------------------------------------------ formatting
def indian(n: float) -> str:
    """Integer with Indian digit grouping: 151808 -> 1,51,808."""
    neg, s = n < 0, str(int(round(abs(n))))
    head, tail = s[:-3], s[-3:]
    while len(head) > 2:
        tail = head[-2:] + "," + tail
        head = head[:-2]
    out = (head + "," + tail) if head else tail
    return ("−" if neg else "") + out


def crore(v) -> str:
    return "—" if v is None or pd.isna(v) else f"₹{indian(v)} cr"


def sign(v, digits: int = 1) -> str:
    if v is None or pd.isna(v):
        return "—"
    return ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v):,.{digits}f}"


def status(cat: str) -> str:
    return f"{STATUS_ICON.get(cat, '❔')} {cat}"


# ------------------------------------------------------------------ scenarios
def district_scenario(d: dict, departure: float) -> pd.DataFrame:
    """Credit vs a normal monsoon, per state and horizon, for a chosen monsoon departure (%)."""
    sf, rows = -departure, []
    for state, lags in DISTRICT_LAGS.items():
        level = d["district_levels"][state]
        for i, (spec, term) in enumerate(lags):
            c = coef(d, spec, term)
            a, b1, b2 = c.coef * sf, c.ci90_low * sf, c.ci90_high * sf
            rows.append({"state": state, "step": i + 1, "when": WHEN[i], "est": a, "lo": min(b1, b2), "hi": max(b1, b2),
                         "p": c.p_wild, "significant": c.classification != "inconclusive",
                         "crore": a / 100 * level["direct_cr"]})
    return pd.DataFrame(rows)


def district_outside(d: dict, departure: float) -> list[str]:
    sf = -departure
    return [s for s in STATES if not d["district_levels"][s]["shortfall_range"][0] <= sf <= d["district_levels"][s]["shortfall_range"][1]]


def state_scenario(d: dict, shocks: dict) -> pd.DataFrame:
    """Headline model M4 per region: effect = x'b with interval from x'Vx; the prediction adds
    the intercept (no waiver year) and the residual variance."""
    rows = []
    for region in REGIONS:
        m = d["scenario"][region]
        b, V = np.array(m["b"]), np.array(m["V"])
        xe = np.array([0.0 if t == "const" else shocks.get(t, 0.0) for t in m["terms"]])
        xp = xe.copy()
        xp[m["terms"].index("const")] = 1.0
        est, se = float(xe @ b), float(np.sqrt(max(xe @ V @ xe, 0)))
        g, se_p = float(xp @ b), float(np.sqrt(max(xp @ V @ xp, 0) + m["sigma2"]))
        outside = [t for t, v in shocks.items() if v and not m["range"][t][0] <= v <= m["range"][t][1]]
        rows.append({"region": region, "effect_pp": est, "lo": est - m["t90"] * se, "hi": est + m["t90"] * se,
                     "growth_pct": g, "growth_lo": g - m["t90"] * se_p, "growth_hi": g + m["t90"] * se_p,
                     "crore": est / 100 * m["credit_cr"], "outside": outside})
    return pd.DataFrame(rows)
