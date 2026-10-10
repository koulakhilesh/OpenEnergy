from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from openenergy import DataError
from openenergy.data import (
    EMBER_ATTRIBUTION,
    OPSD_ATTRIBUTION,
    EmberPriceSource,
    OPSDCsvSource,
    gb_prices,
)

ROOT = Path(__file__).parents[2]
BUNDLED = ROOT / "data/prices/gb_day_ahead_ember.csv"
OPSD = ROOT / "data/time_series/time_series_60min_singleindex_filtered.csv"


def write_ember(directory: Path, start: str = "2021-01-01", days: int = 3) -> Path:
    index = pd.date_range(start, periods=24 * days, freq="1h", tz="UTC")
    pd.DataFrame(
        {
            "utc_timestamp": index.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "price_eur_per_mwh": [100.0] * len(index),
        }
    ).to_csv(directory / "gb_day_ahead_ember.csv", index=False)
    # 2021-01-01 is a holiday with no ECB rate, so the 31 December rate applies to it.
    pd.DataFrame({"date": ["2020-12-31", "2021-01-04"], "gbp_per_eur": [0.9, 0.8]}).to_csv(
        directory / "ecb_gbp_per_eur.csv", index=False
    )
    return directory / "gb_day_ahead_ember.csv"


def test_converts_each_day_at_the_latest_ecb_rate(tmp_path: Path) -> None:
    source = EmberPriceSource(write_ember(tmp_path, days=4))
    prices = source.prices()
    assert prices.currency == "GBP" and prices.zone == "GB_GBN"
    daily = prices.prices.groupby(prices.prices.index.date).mean()
    assert daily.tolist() == pytest.approx([90.0, 90.0, 90.0, 80.0])
    assert len(source.prices("GB", date(2021, 1, 2), date(2021, 1, 2)).prices) == 24
    assert source.zones() == ["GB", "GB_GBN"]


def test_rejects_other_zones_and_missing_rates(tmp_path: Path) -> None:
    path = write_ember(tmp_path, start="2020-12-30")
    with pytest.raises(DataError, match="GB only"):
        EmberPriceSource(path).prices("DE_LU")
    with pytest.raises(DataError, match="no ECB rate on or before 2020-12-30"):
        EmberPriceSource(path).prices()
    with pytest.raises(DataError, match="not found"):
        EmberPriceSource(tmp_path / "none.csv").prices()
    pd.DataFrame({"date": ["2020-01-01"]}).to_csv(tmp_path / "rates.csv", index=False)
    with pytest.raises(DataError, match="missing columns: gbp_per_eur"):
        EmberPriceSource(path, rates=tmp_path / "rates.csv").prices()


def test_gb_prices_prefers_earlier_files_and_cites_what_it_used(tmp_path: Path) -> None:
    ember = write_ember(tmp_path, start="2020-09-29", days=4)
    pd.DataFrame({"date": ["2020-09-01"], "gbp_per_eur": [0.5]}).to_csv(
        tmp_path / "ecb_gbp_per_eur.csv", index=False
    )
    prices, sources = gb_prices([OPSD, ember], date(2020, 9, 29), date(2020, 10, 2))
    assert sources == [OPSD_ATTRIBUTION, EMBER_ATTRIBUTION]
    assert len(prices.prices) == 4 * 24
    assert (prices.prices.loc["2020-10-01":] == 50.0).all()
    opsd = OPSDCsvSource(OPSD).prices("GB_GBN", date(2020, 9, 29), date(2020, 9, 30)).prices
    merged = prices.prices.loc[:"2020-09-30"]
    pd.testing.assert_series_equal(merged, opsd, check_names=False, check_freq=False)
    # OPSD has no price for its last hour; Ember does not fill gaps inside OPSD's span.
    assert merged.isna().sum() == 1
    only_ember, sources = gb_prices([OPSD, ember], date(2020, 10, 1), date(2020, 10, 2))
    assert sources == [EMBER_ATTRIBUTION] and len(only_ember.prices) == 48
    _, sources = gb_prices([ember, OPSD], date(2020, 9, 29), date(2020, 9, 30))
    assert sources == [EMBER_ATTRIBUTION]
    with pytest.raises(DataError, match="no GB prices"):
        gb_prices([ember], date(2030, 1, 1), date(2030, 1, 2))
    with pytest.raises(DataError, match="not found"):
        gb_prices([tmp_path / "none.csv"], date(2020, 1, 1), date(2020, 1, 2))


@pytest.mark.skipif(not BUNDLED.exists(), reason="bundled Ember prices not present")
def test_bundled_ember_prices_match_opsd_where_they_overlap() -> None:
    ember = EmberPriceSource(BUNDLED).prices()
    assert ember.prices.index[0] == pd.Timestamp("2016-06-29 23:00", tz="UTC")
    assert not ember.prices.isna().any()
    opsd = OPSDCsvSource(OPSD).prices("GB_GBN")
    both = pd.concat({"ember": ember.prices, "opsd": opsd.prices}, axis=1, sort=True).dropna()
    assert len(both) > 37_000
    assert both.corr().iloc[0, 1] > 0.9999
    assert (both["ember"] - both["opsd"]).abs().mean() < 0.2
    assert ember.prices.loc["2022"].mean() == pytest.approx(204.8, abs=0.1)
