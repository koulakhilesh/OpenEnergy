from pathlib import Path

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def opsd_csv(tmp_path: Path) -> Path:
    """Three weeks of hourly OPSD-format GB prices with a daily shape."""
    hours = 21 * 24
    index = pd.date_range("2019-01-01", periods=hours, freq="h", tz="UTC")
    rng = np.random.default_rng(0)
    price = 40 + 20 * np.sin(np.arange(hours) * 2 * np.pi / 24) + rng.normal(0, 3, hours)
    path = tmp_path / "data" / "opsd.csv"
    path.parent.mkdir()
    pd.DataFrame(
        {"utc_timestamp": index.strftime("%Y-%m-%dT%H:%M:%SZ"), "GB_GBN_price_day_ahead": price}
    ).to_csv(path, index=False)
    return path


@pytest.fixture
def scenario_file(tmp_path: Path, opsd_csv: Path) -> Path:
    path = tmp_path / "scenarios" / "gb.yaml"
    path.parent.mkdir()
    path.write_text(
        """
name: gb-test
data:
  path: ../data/opsd.csv
  zone: GB_GBN
battery:
  power_mw: 1
  energy_mwh: 2
forecast: naive_last_week
dispatch:
  degradation_cost: 2
"""
    )
    return path
