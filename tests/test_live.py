"""The live campaign: the same batches moved in time, a sixth still running, and the rule that
nothing dated later than now is shown."""

from __future__ import annotations

import csv
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from batchlens.api import deps
from batchlens.demo.generator import LIVE_BATCH, demo_campaign, live_start
from batchlens.demo.plant import write_plant_files
from batchlens.demo.seed import live_from, seed_demo

NOW = datetime(2027, 3, 10, 15, 30, tzinfo=UTC)
START = live_start(NOW)


@pytest.fixture
def live(runtime, monkeypatch):
    monkeypatch.setattr(deps, "now", lambda: NOW)
    seed_demo(runtime.batches, live_at=NOW)
    return runtime


def test_the_live_batch_began_nine_days_ago_at_six_and_the_others_end_before_it():
    assert START == datetime(2027, 3, 1, 6, 0, tzinfo=UTC)
    observations, truth = demo_campaign(START)
    assert [o.record.batch.batch_id for o in observations][-1] == LIVE_BATCH
    assert truth[LIVE_BATCH].scenario == "reduced_culture_productivity"
    ends = [max(p.end for p in o.record.phases) for o in observations[:-1]]
    assert max(ends) < START


def test_moving_a_batch_in_time_changes_none_of_its_values():
    fixed, _ = demo_campaign()
    moved, _ = demo_campaign(START)
    for a, b in zip(fixed, moved[:-1], strict=True):
        shift = (
            b.record.phase("production_culture").start - a.record.phase("production_culture").start
        )
        assert shift.total_seconds() % 86400 == 0
        assert [r.value for r in a.record.results] == [r.value for r in b.record.results]
        assert [
            replace(p, start=p.start + shift, end=p.end + shift) for p in a.record.phases
        ] == list(b.record.phases)
        assert [v for _, v in a.online["ph"]] == [v for _, v in b.online["ph"]]


def test_the_dates_are_fixed_the_first_time_and_kept_afterwards(runtime):
    assert seed_demo(runtime.batches, live_at=NOW) == [
        "BK-0007",
        "BK-0008",
        "BK-0009",
        *(f"BL-000{n}" for n in range(1, 8)),
    ]
    assert live_from(runtime.batches) == START
    assert seed_demo(runtime.batches, live_at=NOW + timedelta(days=2)) == []
    assert live_from(runtime.batches) == START


def test_a_first_live_seed_replaces_batches_stored_with_other_dates(seeded, runtime):
    seed_demo(runtime.batches, live_at=NOW)
    first = runtime.batches.get("BL-0001").phase("production_culture")
    assert first.start == START - timedelta(days=126)


def test_the_list_says_the_live_batch_is_running_and_gives_it_no_end(live, client):
    rows = {row["batch_id"]: row for row in client.get("/api/batches").json()["batches"]}
    assert rows[LIVE_BATCH]["running"] is True and rows[LIVE_BATCH]["end"] is None
    assert rows["BL-0005"]["running"] is False and rows["BL-0005"]["end"]


def test_a_running_batch_shows_nothing_later_than_now(live, client):
    stamp = NOW.isoformat().replace("+00:00", "Z")
    detail = client.get(f"/api/batches/{LIVE_BATCH}").json()
    assert detail["running"] is True
    assert [(p["kind"], p["end"] is None) for p in detail["phases"]] == [
        ("seed_n2", False),
        ("seed_n1", False),
        ("production_culture", True),
    ]
    assert detail["pools"] == []
    assert datetime.fromisoformat(detail["timeline"]["end"].replace("Z", "+00:00")) == NOW
    samples = client.get(f"/api/batches/{LIVE_BATCH}/samples").json()["samples"]
    assert samples and all(s["collected_at"] <= stamp for s in samples)
    assert all(r["result_available_at"] <= stamp for s in samples for r in s["results"])
    # Asking for a later moment gives no more.
    later = client.get(
        f"/api/batches/{LIVE_BATCH}/samples", params={"as_of": "2027-03-20T00:00:00Z"}
    )
    assert later.json()["samples"] == samples


def test_the_running_batch_already_has_its_finding_and_no_harvest_yet(live, client):
    answer = client.get(f"/api/batches/{LIVE_BATCH}/metrics").json()
    titer = next(f for f in answer["findings"] if f["finding"] == "titer_divergence")
    assert titer["observation"]["status"] == "usable"
    assert titer["observation"]["reasons"][0]["code"].startswith("diverged")
    harvest = next(m for m in answer["metrics"] if m["metric"] == "harvest_mass")
    assert harvest["status"] == "insufficient"


def test_a_finished_batch_is_shown_whole(live, client):
    detail = client.get("/api/batches/BL-0005").json()
    assert detail["running"] is False and len(detail["phases"]) == 10


def test_the_live_plant_file_stops_at_now(tmp_path):
    files = write_plant_files(tmp_path, live_from=START, until=NOW)
    rows = list(csv.reader(files.csv.open()))
    assert rows[-1][0] == "2027-03-10 15:30:00"
    assert not (tmp_path / "bioreactor.csv.part").exists()


def test_the_live_loops_file_holds_the_two_days_before_now(tmp_path):
    files = write_plant_files(tmp_path, live_from=START, until=NOW)
    rows = list(csv.reader(files.loops.open()))
    assert rows[1][0] == "2027-03-08 15:30:00" and rows[-1][0] == "2027-03-10 15:30:00"
    assert len(rows) - 1 == 48 * 120 + 1
