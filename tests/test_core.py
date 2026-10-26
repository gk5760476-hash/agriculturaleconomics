"""Unit tests for calculations (spec s.24.1) on small known inputs."""
import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

import models
import shock_indicators
import transformations
from transformations import PROCESSED


@pytest.fixture
def xy():
    rng = np.random.default_rng(0)
    n = 22
    X = np.column_stack([np.ones(n), rng.normal(size=n), rng.normal(size=n)])
    y = X @ np.array([1.0, 0.5, -0.3]) + rng.normal(size=n)
    return y, X


# ------------------------------------------------------------ estimation core
def test_hac_matches_statsmodels(xy):
    y, X = xy
    beta, se, _ = models.ols(y, X, "hac1")
    ref = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 1, "use_correction": True})
    assert np.allclose(beta, ref.params)
    assert np.allclose(se, ref.bse)


def test_cluster_matches_statsmodels(xy):
    y, X = xy
    groups = np.repeat(np.arange(11), 2)
    _, se, _ = models.ols(y, X, "cluster", groups)
    ref = sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": groups})
    assert np.allclose(se, ref.bse)


def test_wild_bootstrap_is_reproducible_and_a_probability(xy):
    y, X = xy
    p1 = models.wild_bootstrap_p(y, X, 1, "hac1", None, np.random.default_rng(1), B=999)
    p2 = models.wild_bootstrap_p(y, X, 1, "hac1", None, np.random.default_rng(1), B=999)
    assert p1 == p2 and 0 < p1 <= 1


def test_wild_bootstrap_rejects_a_strong_effect():
    rng = np.random.default_rng(3)
    x = rng.normal(size=25)
    y = 5 * x + rng.normal(size=25)
    X = np.column_stack([np.ones(25), x])
    assert models.wild_bootstrap_p(y, X, 1, "hac1", None, rng, B=999) < 0.01


def test_benjamini_hochberg_matches_statsmodels():
    p = np.array([0.01, 0.04, 0.03, 0.5, 0.2])
    assert np.allclose(models.benjamini_hochberg(p), multipletests(p, method="fdr_bh")[1])


@pytest.mark.parametrize("coef,p,expected", [(0.4, 0.05, "countercyclical"), (-0.4, 0.05, "procyclical"),
                                             (0.4, 0.5, "inconclusive")])
def test_classification(coef, p, expected):
    assert models.classify("rain_shortfall_pct", coef, p) == expected


def test_controls_and_placebos_are_not_classified():
    assert models.classify("loan_waiver_year", -20, 0.001) == ""
    assert models.classify("rain_shortfall_lead_placebo_pct", -1, 0.001) == ""


# ------------------------------------------------------------ indicators
def test_yield_deviation_is_zero_on_an_exact_trend():
    years = np.arange(2004, 2015)
    panel = pd.DataFrame({"region": "X", "crop_year_start": years,
                          "foodgrain_yield_kg_ha": 1000 * np.exp(0.02 * (years - 2004))})
    assert np.allclose(shock_indicators.yield_deviation(panel), 0, atol=1e-9)


def test_price_weights_sum_to_one():
    w = shock_indicators.price_weights()
    assert np.allclose(w.groupby("region").weight.sum(), 1)


def test_imd_bands_cover_the_line():
    bands = transformations.IMD_BANDS
    assert all(a[1] == b[0] for a, b in zip(bands, bands[1:]))


# ------------------------------------------------------------ processed data
def test_rainfall_departure_formula():
    r = pd.read_csv(PROCESSED / "rainfall_region_year.csv")
    calc = 100 * (r.jjas_mm - r.jjas_normal_mm) / r.jjas_normal_mm
    assert np.allclose(calc, r.jjas_departure_pct, equal_nan=True)


def test_credit_growth_is_log_difference():
    c = pd.read_csv(PROCESSED / "credit_region_year.csv").sort_values(["region", "year"])
    g = 100 * np.log(c.agri_total_outstanding_cr).groupby(c.region).diff()
    assert np.allclose(g, c.agri_total_growth_pct, equal_nan=True)


def test_wpi_splice_has_no_break_at_link_year():
    w = pd.read_csv(PROCESSED / "wpi_crop_prices_fy.csv")
    paddy = w[w.item == "paddy"].set_index("fiscal_year").wpi_2011_12
    assert paddy["2011-12"] == pytest.approx(100)
    assert 0.8 < paddy["2010-11"] / paddy["2011-12"] < 1.1  # linked series continues smoothly


def test_shock_signs():
    s = pd.read_csv(PROCESSED / "shocks_region_year.csv")
    assert np.allclose(s.rain_shortfall_pct, -s.rain_departure_pct, equal_nan=True)
    assert (s.rain_deficit_pct.dropna() >= 0).all() and (s.rain_excess_pct.dropna() >= 0).all()
    assert np.allclose(s.price_fall_pct, -s.crop_real_price_growth_pct, equal_nan=True)


def test_missing_values_are_not_zero():
    p = pd.read_csv(PROCESSED / "analysis_panel_state_year.csv")
    assert p.agri_total_long_cr.isna().any()
    assert not (p.agri_total_long_cr == 0).any()
