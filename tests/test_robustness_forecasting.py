import numpy as np
import pandas as pd

import forecasting
from models import REPORTS


def test_mechanism_family_has_bh_q_values():
    r = pd.read_csv(REPORTS / "tables" / "district_robustness.csv")
    k = r[r.spec.str.startswith("K")]
    assert len(k) == 24 and k.q_bh_mechanism.notna().all()
    assert (k.q_bh_mechanism >= k.p_wild_district - 1e-12).all()


def test_two_way_se_is_reported_for_pre_registered_specs():
    r = pd.read_csv(REPORTS / "tables" / "district_robustness.csv")
    assert set(r[r.clusters == "district+state-year"].spec) == {"I1", "I1-Bihar"}


def test_forecasts_use_only_past_data():
    f = pd.read_csv(REPORTS / "tables" / "forecast_state_oos.csv")
    s = pd.read_csv(forecasting.PROCESSED / "shocks_region_year.csv")
    for region, g in f.groupby("region"):
        hist = s[s.region == region].dropna(subset=["credit_real_growth_pct"]).sort_values("year")
        for r in g.itertuples():
            past = hist[hist.year < r.year].credit_real_growth_pct
            assert np.isclose(r.naive_mean, past.mean()) and r.n_train == len(past)


def test_naive_mean_scores_one_against_itself():
    sc = pd.read_csv(REPORTS / "tables" / "forecast_state_scores.csv")
    assert np.allclose(sc[sc.model == "naive_mean"].mae_vs_naive_mean, 1)
