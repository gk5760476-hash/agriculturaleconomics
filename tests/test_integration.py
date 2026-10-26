"""End-to-end: interim data -> processed -> models -> dashboard (spec s.24.2).

Runs on a scratch copy of the project (ACREWS_ROOT) so the real data/processed,
reports/ and app/dashboard.html are left untouched.

Slow (~1 min). Skip with: pytest -m "not slow"
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Inputs the pipeline reads when ingestion is skipped.
INPUTS = ["config", "data/interim", "data/metadata", "data/raw/policy", "data/raw/prices/msp",
          "app/dashboard_template.html"]


@pytest.mark.slow
def test_pipeline_rebuilds_dashboard_from_interim(tmp_path):
    for rel in INPUTS:
        src, dst = ROOT / rel, tmp_path / rel
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    real_dashboard = (ROOT / "app" / "dashboard.html").stat().st_mtime

    env = {**os.environ, "ACREWS_ROOT": str(tmp_path), "PYTHONPATH": str(ROOT / "src")}
    subprocess.run([sys.executable, "-c", "import run_pipeline; run_pipeline.main(skip_ingestion=True)"],
                   env=env, cwd=tmp_path, check=True)

    out = tmp_path / "app" / "dashboard.html"
    html = out.read_text(encoding="utf-8")
    data = json.loads(re.search(r"const D = (\{.*?\});\n", html, re.S).group(1).replace("<\\/", "</"))
    for key in ["credit", "rain", "summary", "district", "district_robust", "ew_state", "fc_state", "sources"]:
        assert data[key], key
    assert {r["region"] for r in data["credit"]} == {"Bihar", "Maharashtra", "All-India"}
    assert (ROOT / "app" / "dashboard.html").stat().st_mtime == real_dashboard
