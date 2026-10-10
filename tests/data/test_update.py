import io
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openenergy.cli import app
from openenergy.data import EmberPriceSource
from openenergy.data import update as update_module
from openenergy.data.update import cache_dir, update_prices

runner = CliRunner()
EMBER_CSV = (
    "Country,ISO3 Code,Datetime (UTC),Datetime (Local),Price (EUR/MWhe)\n"
    "United Kingdom,GBR,2026-01-01 00:00:00,2026-01-01 00:00:00,100.0\n"
    "United Kingdom,GBR,2026-01-01 01:00:00,2026-01-01 01:00:00,110.0\n"
)
ECB_CSV = "KEY,TIME_PERIOD,OBS_VALUE\nX,2026-01-02,0.86\nX,2025-12-31,0.85\n"


def fake_download(url: str) -> bytes:
    if url == update_module.EMBER_HOURLY:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("hourly/Germany.csv", "x\n")
            archive.writestr("hourly/United Kingdom.csv", EMBER_CSV)
        return buffer.getvalue()
    if url == update_module.ECB_DAILY:
        return ECB_CSV.encode()
    raise AssertionError(url)


def test_update_writes_files_the_ember_source_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(update_module, "_download", fake_download)
    path, hours, first, last = update_prices(tmp_path / "prices")
    assert (hours, first, last) == (2, "2026-01-01 00:00:00", "2026-01-01 01:00:00")
    assert (tmp_path / "prices" / "ecb_gbp_per_eur.csv").read_text().splitlines()[1] == (
        "2025-12-31,0.85"
    )
    prices = EmberPriceSource(path).prices()
    assert prices.prices.tolist() == pytest.approx([85.0, 93.5])


def test_cli_data_update(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update_module, "_download", fake_download)
    result = runner.invoke(app, ["data", "update", "--dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "2 hours" in result.output and "CC BY 4.0" in result.output

    def offline(url: str) -> bytes:
        raise OSError("no network")

    monkeypatch.setattr(update_module, "_download", offline)
    result = runner.invoke(app, ["data", "update", "--dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "download failed" in result.output


def test_missing_uk_file_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_uk(url: str) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("hourly/Germany.csv", "x\n")
        return buffer.getvalue()

    monkeypatch.setattr(update_module, "_download", no_uk)
    with pytest.raises(OSError, match="not found"):
        update_prices(tmp_path)


def test_empty_uk_file_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def empty(url: str) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("United Kingdom.csv", EMBER_CSV.splitlines()[0] + "\n")
        return buffer.getvalue()

    monkeypatch.setattr(update_module, "_download", empty)
    with pytest.raises(OSError, match="empty"):
        update_prices(tmp_path)


def test_download_retries_then_gives_up(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class Response(io.BytesIO):
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def flaky(request: object, timeout: float) -> Response:
        calls.append("x")
        if len(calls) < 3:
            raise OSError("reset")
        return Response(b"ok")

    monkeypatch.setattr(update_module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(update_module.urllib.request, "urlopen", flaky)
    assert update_module._download("https://example.org") == b"ok"
    assert len(calls) == 3

    def down(request: object, timeout: float) -> Response:
        raise OSError("down")

    monkeypatch.setattr(update_module.urllib.request, "urlopen", down)
    with pytest.raises(OSError, match="down"):
        update_module._download("https://example.org")


def test_cache_dir_follows_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert cache_dir() == tmp_path / "openenergy" / "prices"
    monkeypatch.delenv("XDG_CACHE_HOME")
    assert cache_dir() == Path.home() / ".cache" / "openenergy" / "prices"
