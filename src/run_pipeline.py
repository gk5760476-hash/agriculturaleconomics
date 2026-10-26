"""Run the whole pipeline in order, raw data -> dashboard (spec s.24.2).

Usage:
    python -I src/run_pipeline.py                 # everything (~6 min; ingestion reads the 127 MB credit workbook)
    python -I src/run_pipeline.py --skip-ingestion  # reuse data/interim (~1 min)
"""
from __future__ import annotations

import argparse
import time

import build_msp_table
import district_panel
import district_robustness
import early_warning
import forecasting
import ingestion
import models
import reporting
import shock_indicators
import transformations
import validation


def stages(skip_ingestion: bool):
    if not skip_ingestion:
        yield "msp transcription", build_msp_table.build
        for name in ["foodgrains", "handbook", "wpi", "rainfall", "credit"]:
            yield f"ingest {name}", getattr(ingestion, f"ingest_{name}")
    yield "transformations", transformations.main
    yield "validation", lambda: (validation.availability_matrix(), validation.checks())
    yield "shock indicators", shock_indicators.build_shocks
    yield "state models", models.main
    yield "district panel", lambda: district_panel.estimate(district_panel.build_panel())
    yield "district robustness", district_robustness.run
    yield "early warning", lambda: (early_warning.backtest(early_warning.state_signals()),
                                    early_warning.backtest_district(), early_warning.district_signals())
    yield "forecasting", lambda: (forecasting.score(forecasting.state_forecasts()), forecasting.district_ranking())
    yield "dashboard", reporting.build


def main(skip_ingestion=False):
    t0 = time.time()
    for name, fn in stages(skip_ingestion):
        t = time.time()
        fn()
        print(f"[{time.time() - t0:6.1f}s] {name} ({time.time() - t:.1f}s)", flush=True)
    flagged = validation.checks().query("result != 'PASS'")
    print(f"done in {time.time() - t0:.0f}s; {len(flagged)} data check(s) flagged: "
          + "; ".join(f"{r.check} [{r.result}]" for r in flagged.itertuples()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-ingestion", action="store_true")
    main(ap.parse_args().skip_ingestion)
