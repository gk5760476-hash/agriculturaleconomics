"""Streamlit front end: every tab renders without an exception, sliders re-run cleanly, and the
scenario arithmetic reproduces the saved model tables."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "streamlit_app"
sys.path.insert(0, str(APP_DIR))

import data  # noqa: E402  (streamlit_app/data.py)

from models import REPORTS  # noqa: E402


@pytest.fixture(scope="module")
def d():
    return data.load()


def test_indian_grouping():
    assert data.indian(151808) == "1,51,808" and data.indian(2768495) == "27,68,495" and data.indian(-636) == "−636"
    assert data.crore(69087.5) == "₹69,088 cr"


def test_district_scenario_scales_the_saved_coefficients(d):
    dc = pd.read_csv(REPORTS / "tables" / "district_coefficients.csv").set_index(["spec", "term"])
    s = data.district_scenario(d, -30).set_index(["state", "step"])
    assert np.isclose(s.loc[("Bihar", 3), "est"], 30 * dc.loc[("D15", "rain_shortfall_lag3_pct"), "coef"])
    assert np.isclose(s.loc[("Maharashtra", 1), "est"], 30 * dc.loc[("D9", "rain_shortfall_pct"), "coef"])
    assert (s.lo <= s.est).all() and (s.est <= s.hi).all()
    assert data.district_scenario(d, 0)[["est", "crore"]].abs().max().max() == 0


def test_state_scenario_matches_headline_model(d):
    c = pd.read_csv(REPORTS / "tables" / "model_coefficients.csv")
    r = data.state_scenario(d, {"rain_shortfall_pct": 20, "yield_shortfall_pct": 0, "price_fall_pct": 0}).set_index("region")
    for region in data.REGIONS:
        m4 = c[(c.spec == "M4") & (c.region == region) & (c.term == "rain_shortfall_pct")].iloc[0]
        assert np.isclose(r.loc[region, "effect_pp"], 20 * m4.coef, atol=1e-4)
        assert np.isclose(r.loc[region, "lo"], 20 * m4.ci90_low, atol=1e-3)  # one shock: same interval as the table
        assert r.loc[region, "growth_lo"] < r.loc[region, "lo"] + r.loc[region, "growth_pct"] - r.loc[region, "effect_pp"]
    zero = data.state_scenario(d, {"rain_shortfall_pct": 0, "yield_shortfall_pct": 0, "price_fall_pct": 0})
    assert zero.effect_pp.abs().max() == 0 and not any(zero.outside)


def test_every_tab_renders_and_sliders_rerun():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=120).run()
    assert not at.exception, at.exception
    assert [t.label for t in at.tabs] == ["Overview", "Credit trends", "Weather & agriculture", "Results", "Early warning",
                                          "Data & methods"]
    at.slider(key="dist_dep").set_value(-45).run()
    at.slider(key="st_yield").set_value(25).run()
    assert not at.exception, at.exception
    assert any("treat as extrapolation" in w.value for w in at.warning)
    at.segmented_control(key="ew_filter").set_value("All districts").run()
    assert not at.exception
