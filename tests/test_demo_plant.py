"""The synthetic plant as files a live PlantCraft imports: the recorded values as a CSV for its
CSV source, and a plant map (sources, assets, signals) for its map import."""

from __future__ import annotations

import csv
import json
import logging
from datetime import UTC, datetime

import pytest

from batchlens.cli import main
from batchlens.demo.generator import BIOREACTOR, ONLINE_UNITS, demo_campaign
from batchlens.demo.plant import ASSETS, SOURCE_ID, TAGS, write_plant_files
from tests.plant import BIO_SIGNALS, make_fake


def test_the_csv_holds_every_recorded_value_at_its_utc_time(tmp_path):
    files = write_plant_files(tmp_path)
    with files.csv.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert list(rows[0]) == ["time", *TAGS.values()]
    observations, _ = demo_campaign()
    expected = sum(len(batch.online["volume"]) for batch in observations)
    assert len(rows) == expected
    stamps = [row["time"] for row in rows]
    assert stamps == sorted(stamps) and len(set(stamps)) == len(stamps)
    # PlantCraft's CSV source reads times without an offset as UTC.
    assert stamps[0] == "2026-07-01 06:00:00"
    by_time = {row["time"]: row for row in rows}
    for batch in observations:
        for role, points in batch.online.items():
            for moment, value in (points[0], points[len(points) // 2], points[-1]):
                assert moment.tzinfo is UTC
                row = by_time[moment.strftime("%Y-%m-%d %H:%M:%S")]
                assert float(row[TAGS[role]]) == value


def test_the_csv_can_be_written_on_the_wall_clock_of_plantcrafts_time_zone(tmp_path):
    # PlantCraft 0.6.0 reads a CSV source's times on the wall clock of its scenario's source
    # time zone, whatever the source's own setting says. The same instants, written for it:
    utc = write_plant_files(tmp_path / "utc")
    local = write_plant_files(tmp_path / "sp", time_zone="America/Sao_Paulo")

    def first_and_values(path):
        with path.open(newline="", encoding="utf-8") as file:
            rows = list(csv.reader(file))
        return rows[1][0], [row[1:] for row in rows[1:]]

    assert first_and_values(utc.csv)[0] == "2026-07-01 06:00:00"
    assert first_and_values(local.csv)[0] == "2026-07-01 03:00:00"  # UTC-3
    assert first_and_values(utc.csv)[1] == first_and_values(local.csv)[1]
    with pytest.raises(ValueError, match="Mars/Olympus"):
        write_plant_files(tmp_path / "x", time_zone="Mars/Olympus")


def test_the_map_names_the_source_the_assets_and_each_signal_with_its_unit_and_role(tmp_path):
    files = write_plant_files(tmp_path)
    plant_map = json.loads(files.map.read_text(encoding="utf-8"))
    assert plant_map["format"] == "processcraft-map"
    assert plant_map["sources"] == [
        {
            "source_id": SOURCE_ID,
            "name": "BatchLens synthetic",
            "type": "csv",
            "path": str(files.csv.resolve()),
        }
    ]
    assets = {
        row["asset_id"]: (kind, row) for kind in ("unit", "equipment") for row in plant_map[kind]
    }
    assert set(assets) == {
        "U-MAB",
        "BR-2001",
        "HV-2101",
        "CH-3001",
        "VI-3101",
        "CH-3201",
        "CH-3301",
        "VF-3401",
        "UF-3501",
    }
    assert assets["U-MAB"][0] == "unit" and assets["U-MAB"][1]["parent_id"] == ""
    assert all(row["parent_id"] == "U-MAB" for kind, row in assets.values() if kind == "equipment")
    assert all("synthetic" in row["description"].lower() for _, row in assets.values())
    signals = {row["role"]: row for row in plant_map["signals"]}
    assert set(signals) == set(ONLINE_UNITS)
    for role, row in signals.items():
        assert row["tag"] == TAGS[role] and row["source_id"] == SOURCE_ID
        assert row["asset_id"] == BIOREACTOR and row["unit"] == ONLINE_UNITS[role]
        assert row["name"] and row["monitor"] is True
    assert signals["volume"]["unit"] == "L"  # the exact unit the harvest mass requires


def test_writing_the_files_twice_gives_the_same_bytes(tmp_path):
    first = [path.read_bytes() for path in write_plant_files(tmp_path / "a")]
    again = [path.read_bytes() for path in write_plant_files(tmp_path / "a")]
    assert len(first) == 2
    assert first == again


def test_the_fake_plantcraft_of_the_tests_serves_the_same_plant(tmp_path):
    plant_map = json.loads(write_plant_files(tmp_path).map.read_text(encoding="utf-8"))
    fake = {asset["id"]: asset for asset in make_fake().assets}
    for kind in ("unit", "equipment"):
        for row in plant_map[kind]:
            served = fake[row["asset_id"]]
            assert (served["name"], served["kind"]) == (row["name"], kind)
            assert served["parent_id"] == (row["parent_id"] or "plant")
    assert len(ASSETS) == 9
    roles = fake[BIOREACTOR]["signals"]
    assert roles == BIO_SIGNALS
    assert {row["role"]: row["tag"] for row in plant_map["signals"]} == {
        role: signal_id.split(":", 1)[1] for role, signal_id in roles.items()
    }


def test_the_command_line_writes_the_files(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(logging.root, "handlers", [])
    assert main(["demo-plant", "--out", str(tmp_path / "plant")]) == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer["status"] == "ok"
    assert (tmp_path / "plant" / "bioreactor.csv").is_file()
    assert answer["map"] == str((tmp_path / "plant" / "plant-map.json").resolve())
    assert answer["time_zone"] == "UTC"
    assert datetime.fromisoformat(answer["first"]) < datetime.fromisoformat(answer["last"])


def test_the_command_line_takes_plantcrafts_time_zone(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(logging.root, "handlers", [])
    out = str(tmp_path / "plant")
    assert main(["demo-plant", "--out", out, "--time-zone", "America/Sao_Paulo"]) == 0
    assert json.loads(capsys.readouterr().out)["time_zone"] == "America/Sao_Paulo"
    assert "2026-07-01 03:00:00" in (tmp_path / "plant" / "bioreactor.csv").read_text()
    assert main(["demo-plant", "--out", out, "--time-zone", "Mars/Olympus"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"
