from pathlib import Path

import pandas as pd
import pytest

from openenergy import DataError
from openenergy.data.interconnectors import (
    NeighbourPriceSource,
    interconnector_flows,
    interconnectors,
)

ROOT = Path(__file__).parents[2]


def test_register_links_and_in_service_dates() -> None:
    links = {link.name: link for link in interconnectors(ROOT / "data/system")}
    assert len(links) == 10
    assert links["IFA Interconnector"].in_service is None  # in service before 2016
    assert links["IFA Interconnector"].import_mw == 1988
    # Sustained flow, not commissioning tests (Viking's first test flow is 2023-12-11).
    assert links["Viking Link Denmark Interconnector"].in_service == pd.Timestamp(
        "2023-12-29", tz="UTC"
    )
    assert links["NS Link"].neighbour == "norway"


def test_flows_match_2024_totals() -> None:
    flows = interconnector_flows(ROOT / "data/system")
    year = flows.loc["2024"]
    imports = year.filter(like="_import_mwh").sum().sum() / 1e6
    exports = year.filter(like="_export_mwh").sum().sum() / 1e6
    assert imports == pytest.approx(43.9, abs=0.05)
    assert exports == pytest.approx(10.6, abs=0.05)


def test_missing_system_files_are_errors(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="register"):
        interconnectors(tmp_path)
    with pytest.raises(DataError, match="flows"):
        interconnector_flows(tmp_path)


def neighbour_files(tmp_path: Path) -> Path:
    prices = tmp_path / "europe_day_ahead_ember.csv"
    prices.write_text(
        "utc_timestamp,france,norway\n"
        "2024-01-01T00:00:00Z,50,10\n"
        "2024-01-01T01:00:00Z,,20\n"
        "2024-01-01T02:00:00Z,70,\n"
    )
    (tmp_path / "ecb_gbp_per_eur.csv").write_text("date,gbp_per_eur\n2023-12-29,0.5\n")
    return prices


def test_neighbour_prices_convert_and_fill_short_gaps(tmp_path: Path) -> None:
    source = NeighbourPriceSource(neighbour_files(tmp_path))
    index = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    france = source.prices("france", index)
    assert france.currency == "GBP"
    assert list(france.prices) == [25.0, 30.0, 35.0]
    with pytest.raises(DataError, match="norway"):
        source.prices("norway", index)  # a trailing gap cannot be interpolated


def test_half_hourly_index_takes_the_hour_price(tmp_path: Path) -> None:
    source = NeighbourPriceSource(neighbour_files(tmp_path))
    index = pd.date_range("2024-01-01", periods=4, freq="30min", tz="UTC")
    assert list(source.prices("france", index).prices) == [25.0, 25.0, 30.0, 30.0]
