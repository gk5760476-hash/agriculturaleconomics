import pandas as pd

import early_warning as ew
from models import REPORTS


def test_every_row_has_a_known_category_and_a_reason():
    s = pd.read_csv(REPORTS / "tables" / "early_warning_state.csv")
    assert set(s.category) <= set(ew.CATEGORIES)
    flagged = s[s.category.isin(["Watch", "Elevated concern"])]
    assert (flagged.indicators != "none").all()


def test_quiet_rows_with_missing_inputs_are_not_normal():
    s = pd.read_csv(REPORTS / "tables" / "early_warning_state.csv")
    gaps = s[s.missing_inputs.notna() & (s.indicators == "none")]
    assert (gaps.category == "Data insufficient").all()


def test_known_drought_is_flagged():
    # 2015 monsoon (-27% in Maharashtra) -> credit year 2016
    s = pd.read_csv(REPORTS / "tables" / "early_warning_state.csv")
    row = s[(s.region == "Maharashtra") & (s.year == 2016)].iloc[0]
    assert row.category == "Elevated concern" and "monsoon deficient" in row.indicators


def test_backtest_rates_are_probabilities():
    b = pd.read_csv(REPORTS / "tables" / "early_warning_backtest_district.csv")
    for c in ["precision", "base_rate", "hit_rate", "false_alarm_rate"]:
        assert b[c].between(0, 1).all()
