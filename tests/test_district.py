import numpy as np
import pandas as pd

import district_panel as dp
from transformations import PROCESSED


def test_partial_out_matches_dummy_regression():
    rng = np.random.default_rng(0)
    units, years = 6, 8
    df = pd.DataFrame({"u": np.repeat(np.arange(units), years), "t": np.tile(np.arange(years), units)})
    df = df.iloc[rng.permutation(len(df))[:-5]]  # unbalanced
    df["x"] = rng.normal(size=len(df))
    df["y"] = 2 * df.x + df.u * 0.7 + df.t * -0.3 + rng.normal(size=len(df))
    Z = dp._partial_out(df, ["y", "x"], ["u", "t"])
    b_fwl = (Z.x @ Z.y) / (Z.x @ Z.x)
    D = pd.get_dummies(df[["u", "t"]].astype(str), drop_first=True, dtype=float)
    X = np.column_stack([np.ones(len(df)), df.x, D])
    b_full = np.linalg.lstsq(X, df.y, rcond=None)[0][1]
    assert np.isclose(b_fwl, b_full)


def test_units_are_unique_within_panel():
    p = pd.read_csv(PROCESSED / "district_panel.csv")
    assert not p.duplicated(["unit_id", "year"]).any()
    # 'Aurangabad' exists in both states and must stay two units
    assert {"Bihar|Aurangabad", "Maharashtra|Aurangabad"} <= set(p.unit_id)


def test_every_credit_district_maps_to_a_rainfall_unit():
    p = pd.read_csv(PROCESSED / "district_panel.csv")
    used = p[~p.excluded]
    assert used.rain_shortfall_pct.notna().all()
    assert used.groupby("state").unit_id.nunique().to_dict() == {"Bihar": 38, "Maharashtra": 33}
