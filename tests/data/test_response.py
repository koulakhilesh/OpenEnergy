from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from openenergy import DataError
from openenergy.data.response import SERVICES, ResponseSource, utilisation

DATA = Path(__file__).parents[2] / "data/response"


@pytest.mark.parametrize(
    ("hz", "dc", "dm", "dr"),
    [
        # Rows of the delivery table in NESO's Response Services Service Terms (v6).
        (49.80, 0.05, 1.0, 1.0),
        (49.90, 0.023, 0.05, 0.4595),
        (49.985, 0.0, 0.0, 0.0),
        (50.0, 0.0, 0.0, 0.0),
        (49.5, 1.0, 1.0, 1.0),
    ],
)
def test_low_services_follow_the_envelopes(hz: float, dc: float, dm: float, dr: float) -> None:
    frequency = np.array([hz])
    for name, expected in (("DCL", dc), ("DML", dm), ("DRL", dr)):
        assert SERVICES[name].delivered(frequency)[0] == pytest.approx(expected, abs=5e-4)


def test_high_services_mirror_low() -> None:
    frequency = np.array([50.1, 49.9])
    assert SERVICES["DRH"].delivered(frequency).tolist() == pytest.approx([0.4595, 0.0], abs=1e-4)


def test_utilisation_is_average_delivery() -> None:
    factors = utilisation(np.array([49.8, 50.0, 50.2, np.nan]))
    assert factors["DRL"] == pytest.approx(1 / 3)
    assert factors["DRH"] == pytest.approx(1 / 3)
    assert factors["DCL"] == pytest.approx(0.05 / 3)
    with pytest.raises(DataError, match="no valid"):
        utilisation(np.array([np.nan]))


def write(tmp_path: Path, rows: str, usage: str = "month,dcl,dch\n2019-01-01,0.01,0.02\n") -> Path:
    path = tmp_path / "gb_dynamic_response.csv"
    path.write_text("utc_start,utc_end,dcl_gbp_per_mw_h,dcl_mw,dch_gbp_per_mw_h,dch_mw\n" + rows)
    (tmp_path / "gb_response_utilisation.csv").write_text(usage)
    return path


def test_reads_blocks_and_utilisation(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "2019-01-01T23:00:00Z,2019-01-02T03:00:00Z,5,100,1,50\n"
        "2019-01-02T03:00:00Z,2019-01-02T07:00:00Z,6,100,,\n",
    )
    market = ResponseSource(path).market(["DCL", "DCH"])
    assert market.services == ["DCL", "DCH"]
    assert market.prices["DCL"].tolist() == [5.0, 6.0]
    assert np.isnan(market.prices["DCH"].iloc[1])
    starts = pd.DatetimeIndex(market.prices.index)
    factors = market.utilisation_at(starts)
    assert factors["DCH"].tolist() == pytest.approx([0.02, 0.02])
    # A month without frequency data uses the average of the months there are.
    later = market.utilisation_at(pd.DatetimeIndex(["2020-06-01"], tz="UTC"))
    assert later["DCL"].iloc[0] == pytest.approx(0.01)


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ("2019-01-01T23:00:00Z,2019-01-01T22:00:00Z,5,1,1,1\n", "end before"),
        (
            "2019-01-01T23:00:00Z,2019-01-02T05:00:00Z,5,1,1,1\n"
            "2019-01-02T03:00:00Z,2019-01-02T07:00:00Z,5,1,1,1\n",
            "overlapping",
        ),
        (
            "2019-01-01T23:00:00Z,2019-01-02T03:00:00Z,5,1,1,1\n"
            "2019-01-01T23:00:00Z,2019-01-02T03:00:00Z,5,1,1,1\n",
            "duplicate",
        ),
    ],
)
def test_rejects_bad_blocks(tmp_path: Path, rows: str, message: str) -> None:
    with pytest.raises(DataError, match=message):
        ResponseSource(write(tmp_path, rows)).market(["DCL"])


def test_rejects_bad_requests(tmp_path: Path) -> None:
    path = write(tmp_path, "2019-01-01T23:00:00Z,2019-01-02T03:00:00Z,5,1,1,1\n")
    source = ResponseSource(path)
    with pytest.raises(DataError, match="unknown"):
        source.market(["FFR"])
    with pytest.raises(DataError, match="at least one"):
        source.market([])
    with pytest.raises(DataError, match="lacks columns"):
        source.market(["DML"])
    with pytest.raises(DataError, match="not found"):
        ResponseSource(tmp_path / "missing.csv").market(["DCL"])
    write(
        tmp_path,
        "2019-01-01T23:00:00Z,2019-01-02T03:00:00Z,5,1,1,1\n",
        "month,dcl,dch\n2019-01-01,2,0\n",
    )
    with pytest.raises(DataError, match=r"\[0, 1\]"):
        source.market(["DCL"])
    write(
        tmp_path,
        "2019-01-01T23:00:00Z,2019-01-02T03:00:00Z,5,1,1,1\n",
        "month,dcl\n2019-01-01,0.1\n",
    )
    with pytest.raises(DataError, match="lacks columns"):
        source.market(["DCH"])


def test_bundled_data_covers_september_2021_onwards() -> None:
    market = ResponseSource(DATA / "gb_dynamic_response.csv").market(list(SERVICES))
    starts = pd.DatetimeIndex(market.prices.index)
    assert starts[0] == pd.Timestamp("2021-09-15 22:00", tz="UTC")
    ends = pd.DatetimeIndex(market.prices["end"])
    assert (ends[:-1] == starts[1:]).all()
    assert market.prices.loc["2023-01-01":, "DRL"].notna().all()
    assert market.utilisation.index[0] == pd.Timestamp("2021-09-01", tz="UTC")
    assert (market.utilisation["DRL"] > market.utilisation["DCL"]).all()
