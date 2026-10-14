from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from openenergy import DataError
from openenergy.data.ember import gb_prices
from openenergy.data.interconnectors import (
    NeighbourPriceSource,
    availability_from_flows,
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
    # Fitted from flows (scripts/fit_interconnector_availability.py).
    assert all(0 < link.import_availability <= 1 for link in links.values())
    assert all(0 < link.export_availability <= 1 for link in links.values())
    assert links["IFA Interconnector"].import_availability == pytest.approx(0.685)


def test_availability_is_actual_flow_over_a_price_taker() -> None:
    prices = gb_prices(
        [ROOT / "data/prices/gb_day_ahead_ember.csv"], date(2024, 1, 1), date(2024, 3, 31)
    )
    table = availability_from_flows(
        ROOT / "data/system",
        prices[0].prices,
        NeighbourPriceSource(ROOT / "data/prices/europe_day_ahead_ember.csv"),
    )
    assert len(table) == 10
    ifa = table.loc["IFA Interconnector"]
    assert ifa["import_availability"] == pytest.approx(
        ifa["actual_import_mwh"] / ifa["price_taker_import_mwh"]
    )
    shares = table[["import_availability", "export_availability"]]
    assert shares.notna().all().all() and (shares > 0).all().all() and (shares <= 1).all().all()
    # Greenlink entered service in 2025, so it gets the mean of the others.
    others = table.drop("Greenlink")["import_availability"]
    assert table.loc["Greenlink", "import_availability"] == pytest.approx(others.mean())


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
