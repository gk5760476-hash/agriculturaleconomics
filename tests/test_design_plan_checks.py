"""Design-plan validation items added 2026-10-26: SPI, alternative drought thresholds,
leave-one-drought-out, unit-root tests and the scenario inputs embedded in the dashboard."""
import numpy as np
import pandas as pd
from scipy import stats

import reporting
import shock_indicators
from models import REPORTS
from transformations import PROCESSED


def test_spi_is_standard_normal_over_the_normal_period():
    rain = pd.read_csv(PROCESSED / "rainfall_region_year.csv")
    rain = rain[rain.district.isna()]
    spi = shock_indicators.monsoon_spi(rain)
    for region in ["Bihar", "Maharashtra", "All-India"]:
        x = np.array([spi[(region, y)] for y in range(1971, 2021)])
        assert abs(x.mean()) < 0.15 and 0.8 < x.std() < 1.2
        assert stats.spearmanr(x, rain.set_index(["region_id", "year"]).jjas_mm.loc[region].loc[1971:2020]).statistic > 0.999


def test_drought_thresholds_are_nested():
    s = pd.read_csv(PROCESSED / "shocks_region_year.csv").dropna(subset=["rain_departure_pct"])
    assert (s.drought_flag_70lpa <= s.drought_flag_75lpa).all() and (s.drought_flag_75lpa <= s.drought_flag).all()
    assert ((s.rain_departure_pct <= -25) == (s.drought_flag_75lpa == 1)).all()


def test_drought_holdout_excludes_the_held_out_year():
    h = pd.read_csv(REPORTS / "tables" / "forecast_drought_holdout.csv")
    s = pd.read_csv(PROCESSED / "shocks_region_year.csv").dropna(subset=["credit_real_growth_pct"])
    for r in h.itertuples():
        others = s[(s.region == r.region) & (s.year != r.held_out_year)].credit_real_growth_pct
        assert np.isclose(r.naive_mean, others.mean())


def test_unit_root_table_covers_every_region_and_series():
    u = pd.read_csv(REPORTS / "tables" / "unit_root_tests.csv")
    assert len(u) == 12 and u[["adf_p", "kpss_p"]].notna().all().all()


def test_scenario_coefficients_match_the_headline_model():
    s = pd.read_csv(PROCESSED / "shocks_region_year.csv")
    credit = s.merge(pd.read_csv(PROCESSED / "credit_agri_long_region_year.csv")[["region", "year", "agri_total_long_cr"]],
                     on=["region", "year"], how="left")
    sc = reporting.scenario_inputs(s, credit)
    c = pd.read_csv(REPORTS / "tables" / "model_coefficients.csv")
    for region, m in sc.items():
        m4 = c[(c.spec == "M4") & (c.region == region)].set_index("term").coef
        for t, b in zip(m["terms"], m["b"]):
            assert np.isclose(b, m4[t], atol=1e-5)
        assert np.allclose(m["V"], np.array(m["V"]).T) and min(np.linalg.eigvalsh(m["V"])) > -1e-8
