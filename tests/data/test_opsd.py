from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from openenergy import DataError
from openenergy.data import OPSD_ATTRIBUTION, OPSDCsvSource, fill_gaps

BUNDLED = Path(__file__).parents[2] / "data/time_series/time_series_60min_singleindex_filtered.csv"


def write_csv(path: Path, rows: int = 48) -> Path:
    index = pd.date_range("2019-01-01", periods=rows, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "utc_timestamp": index.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "cet_cest_timestamp": "",
            "GB_GBN_price_day_ahead": range(rows),
            "DE_LU_price_day_ahead": 1.0,
            "GB_GBN_load_actual_entsoe_transparency": 1.0,
        }
    )
    frame.to_csv(path, index=False)
    return path


def test_zones_lists_price_columns(tmp_path: Path) -> None:
    source = OPSDCsvSource(write_csv(tmp_path / "ts.csv"))
    assert source.zones() == ["DE_LU", "GB_GBN"]


def test_prices_loads_zone_with_currency(tmp_path: Path) -> None:
    source = OPSDCsvSource(write_csv(tmp_path / "ts.csv"))
    gb = source.prices("GB_GBN")
    de = source.prices("DE_LU")
    assert gb.currency == "GBP"
    assert de.currency == "EUR"
    assert gb.zone == "GB_GBN"
    assert str(gb.prices.index.tz) == "UTC"
    assert len(gb.prices) == 48


def test_prices_filters_inclusive_days(tmp_path: Path) -> None:
    source = OPSDCsvSource(write_csv(tmp_path / "ts.csv"))
    series = source.prices("GB_GBN", start=date(2019, 1, 2), end=date(2019, 1, 2))
    assert len(series.prices) == 24
    assert series.prices.iloc[0] == 24


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="not found"):
        OPSDCsvSource(tmp_path / "missing.csv").zones()


def test_unknown_zone_lists_available(tmp_path: Path) -> None:
    source = OPSDCsvSource(write_csv(tmp_path / "ts.csv"))
    with pytest.raises(DataError, match="DE_LU, GB_GBN"):
        source.prices("FR")


def test_missing_timestamp_column_raises(tmp_path: Path) -> None:
    path = tmp_path / "ts.csv"
    pd.DataFrame({"GB_GBN_price_day_ahead": [1.0, 2.0]}).to_csv(path, index=False)
    with pytest.raises(DataError, match="utc_timestamp"):
        OPSDCsvSource(path).prices("GB_GBN")


def test_attribution_cites_doi() -> None:
    assert "10.25832/time_series/2020-10-06" in OPSD_ATTRIBUTION


@pytest.mark.skipif(not BUNDLED.exists(), reason="bundled OPSD extract not present")
def test_bundled_gb_prices() -> None:
    series = OPSDCsvSource(BUNDLED).prices("GB_GBN", date(2019, 1, 1), date(2019, 12, 31))
    assert series.currency == "GBP"
    assert series.periods_per_day == 24
    assert len(series.prices) == 365 * 24
    # 2019-03-31 has a 2h DST gap; 2019-06-07/08 share a 24h outage.
    assert len(series.complete_days()) == 362
    filled, count = fill_gaps(series, max_gap_hours=2)
    assert count == 2
    assert len(filled.complete_days()) == 363
