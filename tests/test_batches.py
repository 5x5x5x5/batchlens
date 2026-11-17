"""The app's own object and its read API: the seeded batches, their samples, metrics and
trends, read through the fake PlantCraft as the signed-in person."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

import pytest

from batchlens import calc
from batchlens.analysis.metrics import METRICS, batch_metrics
from batchlens.cli import main
from batchlens.demo.generator import BIOREACTOR, VOLUME_UNIT, demo_campaign
from batchlens.demo.seed import seed_demo
from tests.conftest import client_for, make_runtime
from tests.plant import BIO_SIGNALS, make_fake

DETAIL = ["/api/batches/{id}", "/api/batches/{id}/samples", "/api/batches/{id}/metrics"]
DETAIL += ["/api/batches/{id}/trends"]
WITH_AS_OF = DETAIL[1:]
ROUTES = ["/api/batches", *(path.format(id="BL-0001") for path in DETAIL)]
CAMPAIGN = {o.record.batch.batch_id: o for o in demo_campaign()[0]}
TRUTH = demo_campaign()[1]


def instant(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def metrics_of(client, batch_id: str, **params) -> dict[str, dict]:
    answer = client.get(f"/api/batches/{batch_id}/metrics", params=params)
    assert answer.status_code == 200, answer.text
    return {item["metric"]: item for item in answer.json()["metrics"]}


def codes(metric: dict) -> list[str]:
    return [reason["code"] for reason in metric["reasons"]]


# The store and the seed ------------------------------------------------------------------------


def test_the_seed_stores_exactly_what_the_generator_made(runtime):
    assert seed_demo(runtime.batches) == [
        "BK-0007",
        "BK-0008",
        "BK-0009",
        *(f"BL-000{n}" for n in range(1, 7)),
    ]
    for batch_id, observations in CAMPAIGN.items():
        assert runtime.batches.get(batch_id) == observations.record
    assert runtime.batches.get("BL-9999") is None
    assert runtime.batches.get("'; DROP TABLE batches; --") is None


def test_seeding_twice_changes_nothing(seeded):
    before = seeded.batches.get("BL-0002")
    seed_demo(seeded.batches)
    assert len(seeded.batches.summaries()) == 9
    assert seeded.batches.get("BL-0002") == before


def test_the_command_line_seeds_the_demo(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("BATCHLENS_DATA_DIR", str(tmp_path))
    # The command sets up logging on the captured stderr; give the root logger back afterwards.
    monkeypatch.setattr(logging.root, "handlers", [])
    assert main(["seed-demo"]) == 0
    seeded = json.loads(capsys.readouterr().out)["batches"]
    assert seeded == ["BK-0007", "BK-0008", "BK-0009", *(f"BL-000{n}" for n in range(1, 7))]
    runtime = make_runtime(tmp_path, make_fake())
    try:
        assert len(runtime.batches.summaries()) == 9
    finally:
        runtime.shutdown()


# The routes ------------------------------------------------------------------------------------


def test_the_list_gives_each_batch_its_reference_flag_window_and_bioreactor(seeded, client):
    answer = client.get("/api/batches").json()
    assert answer["time_zone"] == "UTC"
    rows = answer["batches"]
    assert [row["batch_id"] for row in rows] == [
        "BK-0007",
        "BK-0008",
        "BK-0009",
        *(f"BL-000{n}" for n in range(1, 7)),
    ]
    # The earlier campaign's three, then this one's, whose first is the reference.
    assert [row["is_reference"] for row in rows] == [*[False] * 3, True, *[False] * 5]
    assert [row["is_comparable"] for row in rows] == [*[True] * 5, *[False] * 4]
    first, record = rows[3], CAMPAIGN["BL-0001"].record
    assert first["product"] == "mAb-X"
    assert instant(first["start"]) == record.phases[0].start
    assert instant(first["end"]) == record.phases[-1].end
    assert first["asset_id"] == BIOREACTOR
    assert first["asset_name"] == "Production bioreactor 2000 L"  # read from PlantCraft


def test_one_batch_comes_with_its_phase_executions_and_pool_measurements(seeded, client):
    answer = client.get("/api/batches/BL-0001").json()
    assert answer["batch"]["batch_id"] == "BL-0001" and answer["batch"]["is_reference"] is True
    assert [phase["kind"] for phase in answer["phases"]] == [
        "seed_n2",
        "seed_n1",
        "production_culture",
        "harvest",
        "protein_a_capture",
        "viral_inactivation",
        "cation_exchange",
        "anion_exchange",
        "viral_filtration",
        "ufdf",
    ]
    assert [phase["asset_name"] for phase in answer["phases"]] == [
        "Seed bioreactor N-2 50 L",
        "Seed bioreactor N-1 250 L",
        "Production bioreactor 2000 L",
        "Harvest clarification skid",
        "Protein A chromatography skid",
        "Viral inactivation vessel",
        "Cation-exchange chromatography skid",
        "Anion-exchange chromatography skid",
        "Viral filtration skid",
        "UF/DF skid",
    ]
    assert all(instant(phase["start"]) < instant(phase["end"]) for phase in answer["phases"])
    assert [pool["pool"] for pool in answer["pools"]] == [
        "protein_a_load",
        "protein_a_eluate_cycle_1",
        "protein_a_eluate_cycle_2",
        "protein_a_eluate",
        "viral_inactivation_pool",
        "cation_exchange_pool",
        "anion_exchange_pool",
        "viral_filtrate",
        "drug_substance",
        "drug_substance_container_1",
        "drug_substance_container_2",
        "drug_substance_container_3",
    ]
    assert {pool["volume_unit"] for pool in answer["pools"]} == {"L"}
    assert "synthetic-generator" in answer["batch"]["provenance"]


def test_samples_carry_every_result_with_both_timestamps(seeded, client):
    answer = client.get("/api/batches/BL-0001/samples").json()
    assert answer["as_of"] is None
    kinds = [sample["phase_kind"] for sample in answer["samples"]]
    assert kinds == ["seed_n2"] * 4 + ["seed_n1"] * 4 + ["production_culture"] * 15
    for sample in answer["samples"]:
        # A seed passage's samples are counted only; the production culture's are assayed too.
        seed = sample["phase_kind"] != "production_culture"
        assert [r["analyte"] for r in sample["results"]] == (
            ["vcd", "viability"] if seed else ["glucose", "lactate", "titer", "vcd", "viability"]
        )
        for result in sample["results"]:
            assert instant(result["result_available_at"]) > instant(sample["collected_at"])
            assert result["unit"] and result["method"] and result["validity"] == "valid"


def test_metrics_are_the_calculations_on_what_plantcraft_and_the_store_hold(seeded, client):
    for batch_id, observations in CAMPAIGN.items():
        answered = metrics_of(client, batch_id)
        assert list(answered) == list(METRICS)
        volume = calc.Online(BIO_SIGNALS["volume"], VOLUME_UNIT, observations.online["volume"])
        for expected in batch_metrics(observations.record, volume):
            got = answered[expected.metric]
            assert got["status"] == expected.status, (batch_id, got)
            assert (got["status"] == "usable") == (
                batch_id != "BL-0005"
            ) or expected.metric.startswith(("protein_a", "seed_", "inoculation"))
            assert got["value"] == (
                pytest.approx(expected.value) if expected.value is not None else None
            )
            assert (got["unit"], got["calculation_version"]) == (
                expected.unit,
                expected.calculation_version,
            )
            assert got["inputs"] == list(expected.inputs)


def test_metrics_come_beside_the_reference_batch_and_the_difference(seeded, client):
    reference = metrics_of(client, "BL-0001")
    answer = client.get("/api/batches/BL-0003/metrics").json()
    assert answer["reference_batch_id"] == "BL-0001"
    for item in answer["metrics"]:
        beside = reference[item["metric"]]
        assert item["reference"] == {"value": beside["value"], "status": beside["status"]}
        assert item["difference"] == pytest.approx(item["value"] - beside["value"])
    assert {m["metric"]: m["difference"] for m in answer["metrics"]}["qp"] < -5
    # The reference batch is not compared with itself.
    own = client.get("/api/batches/BL-0001/metrics").json()
    assert own["reference_batch_id"] is None
    assert all(m["reference"] is None and m["difference"] is None for m in own["metrics"])


def test_trends_are_the_bioreactors_signals_over_the_production_phase(seeded, client):
    answer = client.get("/api/batches/BL-0002/trends").json()
    culture = CAMPAIGN["BL-0002"].record.phase("production_culture")
    assert answer["asset_id"] == BIOREACTOR
    assert instant(answer["start"]) == culture.start and instant(answer["end"]) == culture.end
    assert [s["role"] for s in answer["signals"]] == ["ph", "do", "temperature", "volume"]
    for signal in answer["signals"]:
        assert signal["status"] == "usable" and signal["signal_id"] == BIO_SIGNALS[signal["role"]]
        assert signal["unit"] and signal["name"]
        assert 100 < len(signal["t"]) == len(signal["v"]) <= 400  # downsampled
        assert all(culture.start <= instant(stamp) <= culture.end for stamp in signal["t"])
    volume = answer["signals"][3]["v"]
    assert 1395 < volume[0] < 1405 and 1995 < volume[-1] < 2005
    temperature = answer["signals"][2]["v"]
    assert 36 < temperature[0] < 37 and 32.5 < temperature[-1] < 33.5  # the planned shift


@pytest.mark.parametrize("path", DETAIL)
def test_an_unknown_batch_is_a_404(seeded, client, path):
    answer = client.get(path.format(id="BL-9999"))
    assert answer.status_code == 404 and answer.json()["detail"] == "Batch not found."


@pytest.mark.parametrize("path", WITH_AS_OF)
@pytest.mark.parametrize("as_of", ["yesterday", "2026-13-45T00:00:00Z", "12", ""])
def test_a_malformed_as_of_is_a_422(seeded, client, path, as_of):
    assert client.get(path.format(id="BL-0001"), params={"as_of": as_of}).status_code == 422


@pytest.mark.parametrize("path", ROUTES)
def test_who_may_read(seeded, fake, path):
    with client_for(seeded, fake, None) as anonymous:
        assert anonymous.get(path).status_code == 401
    with client_for(seeded, fake, "outsider") as outsider:
        assert outsider.get(path).status_code == 403
    with client_for(seeded, fake, "operator") as viewer:
        assert viewer.get(path).status_code == 200


def test_there_are_no_write_routes(seeded, client):
    for method in ("post", "put", "delete", "patch"):
        assert getattr(client, method)("/api/batches/BL-0001").status_code in (404, 405)


# No look-ahead ---------------------------------------------------------------------------------


def test_as_of_before_the_last_titer_came_in_omits_it_and_harvest_mass_waits(seeded, client):
    record = CAMPAIGN["BL-0001"].record
    as_of = (record.phase("production_culture").end + timedelta(hours=1)).isoformat()
    last = client.get("/api/batches/BL-0001/samples", params={"as_of": as_of}).json()["samples"][-1]
    assert "titer" not in [r["analyte"] for r in last["results"]]
    assert "vcd" in [r["analyte"] for r in last["results"]]
    found = metrics_of(client, "BL-0001", as_of=as_of)
    assert (
        found["harvest_mass"]["status"] == "insufficient" and found["harvest_mass"]["value"] is None
    )
    [reason] = found["harvest_mass"]["reasons"]
    assert reason["code"] == "result_not_yet_available"
    assert reason["values"]["ids"] == ["BL-0001-S15-titer"]
    assert found["harvest_to_load_yield"]["status"] == "insufficient"
    assert found["ivcd"]["status"] == "usable"


def test_as_of_mid_culture_shows_only_what_was_collected_and_recorded_by_then(seeded, client):
    culture = CAMPAIGN["BL-0001"].record.phase("production_culture")
    as_of = culture.start + timedelta(days=5)
    samples = client.get("/api/batches/BL-0001/samples", params={"as_of": as_of.isoformat()}).json()
    assert instant(samples["as_of"]) == as_of
    assert 0 < len(samples["samples"]) < 15
    assert all(instant(s["collected_at"]) <= as_of for s in samples["samples"])
    trends = client.get("/api/batches/BL-0001/trends", params={"as_of": as_of.isoformat()}).json()
    for signal in trends["signals"]:
        assert signal["t"] and all(instant(stamp) <= as_of for stamp in signal["t"])
    found = metrics_of(client, "BL-0001", as_of=as_of.isoformat())
    assert codes(found["harvest_mass"]) == ["phase_not_ended"]
    assert found["protein_a_load_mass"]["status"] == "insufficient"


@pytest.mark.parametrize("path", WITH_AS_OF)
@pytest.mark.parametrize("as_of", ["0001-01-01T00:00:00+05:00", "9999-12-31T23:59:59-05:00"])
def test_an_as_of_whose_utc_instant_does_not_exist_is_a_422_not_a_crash(
    seeded, client, path, as_of
):
    # Valid ISO text, but in UTC it falls before year 1 or after year 9999.
    assert client.get(path.format(id="BL-0001"), params={"as_of": as_of}).status_code == 422


@pytest.mark.parametrize("as_of", ["0001-01-02T00:00:00Z", "9999-12-30T00:00:00Z"])
def test_an_as_of_at_the_ends_of_time_is_answered(seeded, client, as_of):
    for path in WITH_AS_OF:
        assert client.get(path.format(id="BL-0001"), params={"as_of": as_of}).status_code == 200


def test_an_as_of_without_an_offset_is_utc(seeded, client):
    answer = client.get("/api/batches/BL-0001/samples", params={"as_of": "2026-07-06T06:00:00"})
    assert instant(answer.json()["as_of"]) == datetime(2026, 7, 6, 6, tzinfo=UTC)


# What PlantCraft does not have is an answer, not an error ------------------------------------


def test_without_the_bioreactor_in_plantcraft_the_app_says_so(tmp_path):
    fake = make_fake(bioprocess=False)  # a live PlantCraft before the synthetic plant is loaded
    runtime = make_runtime(tmp_path, fake)
    try:
        seed_demo(runtime.batches)
        with client_for(runtime, fake) as client:
            rows = client.get("/api/batches").json()["batches"]
            assert len(rows) == 9 and rows[0]["asset_name"] is None
            found = metrics_of(client, "BL-0001")
            harvest = found["harvest_mass"]
            assert (harvest["status"], harvest["value"]) == ("insufficient", None)
            assert harvest["reasons"] == [
                {"code": "asset_not_found", "values": {"asset_id": BIOREACTOR}}
            ]
            assert found["harvest_to_load_yield"]["status"] == "insufficient"
            # What rests on the app's own records is still computed.
            assert found["ivcd"]["status"] == found["protein_a_recovery"]["status"] == "usable"
            trends = client.get("/api/batches/BL-0001/trends")
            assert trends.status_code == 200
            for signal in trends.json()["signals"]:
                assert (signal["status"], signal["t"], signal["v"]) == ("insufficient", [], [])
                assert codes(signal) == ["asset_not_found"]
    finally:
        runtime.shutdown()


def test_a_bioreactor_without_a_volume_signal(seeded, fake, client):
    bioreactor = next(asset for asset in fake.assets if asset["id"] == BIOREACTOR)
    del bioreactor["signals"]["volume"]
    harvest = metrics_of(client, "BL-0001")["harvest_mass"]
    assert harvest["status"] == "insufficient"
    assert harvest["reasons"] == [
        {"code": "signal_not_found", "values": {"asset_id": BIOREACTOR, "role": "volume"}}
    ]
    signals = client.get("/api/batches/BL-0001/trends").json()["signals"]
    assert [s["status"] for s in signals] == ["usable", "usable", "usable", "insufficient"]
    assert codes(signals[3]) == ["signal_not_found"]


def test_a_dead_data_source_is_an_answer_too(seeded, fake, client):
    fake.broken[BIO_SIGNALS["volume"]] = "the historian is down"
    answer = client.get("/api/batches/BL-0001/metrics")
    assert answer.status_code == 200
    harvest = {m["metric"]: m for m in answer.json()["metrics"]}["harvest_mass"]
    assert harvest["status"] == "insufficient" and codes(harvest) == ["series_unreadable"]
    signals = client.get("/api/batches/BL-0001/trends").json()["signals"]
    assert [s["status"] for s in signals] == ["usable", "usable", "usable", "insufficient"]
    assert codes(signals[3]) == ["series_unreadable"]


def test_a_volume_signal_in_another_unit_is_invalid_not_converted(seeded, fake, client):
    next(s for s in fake.signals if s["id"] == BIO_SIGNALS["volume"])["unit"] = "m3"
    harvest = metrics_of(client, "BL-0001")["harvest_mass"]
    assert (harvest["status"], harvest["value"]) == ("invalid", None)
    assert codes(harvest) == ["wrong_unit"]


# Scope and ground truth ------------------------------------------------------------------------


def test_two_batches_on_the_same_bioreactor_do_not_see_each_other(seeded, client):
    seen = {}
    for batch_id in ("BL-0001", "BL-0002"):
        culture = CAMPAIGN[batch_id].record.phase("production_culture")
        samples = client.get(f"/api/batches/{batch_id}/samples").json()["samples"]
        assert all(s["sample_id"].startswith(batch_id) for s in samples)
        assert all(r["result_id"].startswith(batch_id) for s in samples for r in s["results"])
        trends = client.get(f"/api/batches/{batch_id}/trends").json()["signals"]
        stamps = [instant(stamp) for signal in trends for stamp in signal["t"]]
        assert stamps and all(culture.start <= stamp <= culture.end for stamp in stamps)
        inputs = [i for m in metrics_of(client, batch_id).values() for i in m["inputs"]]
        assert all(i.startswith(batch_id) or i == BIO_SIGNALS["volume"] for i in inputs)
        seen[batch_id] = (min(stamps), max(stamps))
    assert seen["BL-0001"][1] < seen["BL-0002"][0]  # the same signal, two separate windows


def test_no_response_carries_the_scenario_or_its_parameters(seeded, client):
    truth = demo_campaign()[1]
    text = client.get("/api/batches").text
    for batch_id in CAMPAIGN:
        for path in DETAIL:
            text += client.get(path.format(id=batch_id)).text
    text = text.lower()
    labels = {item.scenario for item in truth.values()}
    for word in (*labels, "reduced", "scenario", "fault", "ground", "truth", "shift", "label"):
        assert word not in text, word


# Findings --------------------------------------------------------------------------------------


def findings_of(client, batch_id: str, **params) -> list[dict]:
    answer = client.get(f"/api/batches/{batch_id}/metrics", params=params)
    assert answer.status_code == 200, answer.text
    return answer.json()["findings"]


def finding_of(client, batch_id: str, kind: str, **params) -> dict:
    found = [f for f in findings_of(client, batch_id, **params) if f["finding"] == kind]
    assert len(found) == 1, [f["finding"] for f in findings_of(client, batch_id, **params)]
    return found[0]


FINDINGS = [
    "titer_divergence",
    "inoculation_density_shortfall",
    "harvest_to_load_yield_shortfall",
    "protein_a_recovery_shortfall",
    "viral_inactivation_yield_shortfall",
    "cation_exchange_yield_shortfall",
    "anion_exchange_yield_shortfall",
    "viral_filtration_yield_shortfall",
    "ufdf_yield_shortfall",
]


def test_every_compared_batch_gets_the_same_findings_in_the_same_order(seeded, client):
    for batch_id in ("BL-0002", "BL-0003", "BL-0004"):
        assert [f["finding"] for f in findings_of(client, batch_id)] == FINDINGS
        assert all(f["cause"] is None for f in findings_of(client, batch_id))


def test_the_batch_that_lost_product_in_protein_a_gets_a_recovery_finding(seeded, client):
    finding = finding_of(client, "BL-0004", "protein_a_recovery_shortfall")
    observation = finding["observation"]
    assert (observation["status"], observation["unit"]) == ("usable", "percentage points")
    recovery = metrics_of(client, "BL-0004")["protein_a_recovery"]
    assert observation["value"] == pytest.approx(recovery["reference"]["value"] - recovery["value"])
    assert observation["value"] > 15
    assert codes(observation) == ["below_reference"]
    # It rests on the pool measurements of both batches.
    assert set(observation["inputs"]) == {
        "BL-0004-protein_a_eluate",
        "BL-0004-protein_a_load",
        "BL-0001-protein_a_eluate",
        "BL-0001-protein_a_load",
    }
    # The consequence: what came out of the step, against the reference.
    eluate = metrics_of(client, "BL-0004")["protein_a_eluate_mass"]
    assert finding["consequence"] == {
        "metric": "protein_a_eluate_mass",
        "unit": "g",
        "status": "usable",
        "value": eluate["value"],
        "reference": eluate["reference"]["value"],
        "difference": eluate["difference"],
    }
    assert [group["at"] for group in finding["evidence"]] == ["buffer_lot"]
    # Its culture was normal, and so was its yield into the step, within the tolerance.
    assert codes(finding_of(client, "BL-0004", "titer_divergence")["observation"]) == [
        "no_divergence"
    ]
    step_yield = finding_of(client, "BL-0004", "harvest_to_load_yield_shortfall")
    assert codes(step_yield["observation"]) == ["within_reference"]
    assert step_yield["consequence"] is None


def test_the_low_inoculum_batch_is_found_by_its_first_count_not_by_its_titer(seeded, client):
    # The titer stays within the tolerance of the reference's, so that finding is quiet.
    titer = finding_of(client, "BL-0006", "titer_divergence")
    assert codes(titer["observation"]) == ["no_divergence"]
    finding = finding_of(client, "BL-0006", "inoculation_density_shortfall")
    observation = finding["observation"]
    assert observation["status"] == "usable" and observation["value"] > 50  # percent below
    assert codes(observation) == ["inoculated_below_reference"]
    assert observation["inputs"] == ["BL-0006-S01-vcd", "BL-0001-S01-vcd"]
    assert finding["cause"] is None
    # What it amounts to: less product at harvest than the reference batch.
    assert finding["consequence"]["metric"] == "harvest_mass"
    assert -1500 < finding["consequence"]["difference"] < -300
    # Beside it, the last sample of the N-1 passage against the reference's: far fewer cells.
    [group] = finding["evidence"]
    assert (group["at"], group["sample_id"], group["reference_sample_id"]) == (
        "seed_n1_end",
        "BL-0006-N1-S04",
        "BL-0001-N1-S04",
    )
    assert group["culture_day"] == pytest.approx(3 - 1 / 24)
    count = next(row for row in group["results"] if row["analyte"] == "vcd")
    assert count["value"] < 0.5 * count["reference_value"]
    # Every other batch began near the target: nothing found, no evidence shown.
    for batch_id in ("BL-0002", "BL-0003", "BL-0004", "BL-0005"):
        other = finding_of(client, batch_id, "inoculation_density_shortfall")
        assert codes(other["observation"]) == ["inoculation_within_reference"]
        assert other["consequence"] is None and other["evidence"] == []


def test_the_low_inoculum_finding_uses_only_what_was_available_at_as_of(seeded, client):
    culture = CAMPAIGN["BL-0006"].record.phase("production_culture")
    # An hour into the culture the first count is collected, not yet reported.
    early = (culture.start + timedelta(hours=1, minutes=5)).isoformat()
    waiting = finding_of(client, "BL-0006", "inoculation_density_shortfall", as_of=early)
    assert waiting["observation"]["status"] == "insufficient"
    assert waiting["consequence"] is None and waiting["evidence"] == []
    # A day in, it is found; the harvest it would be compared by has not happened.
    day_one = (culture.start + timedelta(days=1)).isoformat()
    found = finding_of(client, "BL-0006", "inoculation_density_shortfall", as_of=day_one)
    assert found["observation"]["value"] > 50
    assert found["consequence"]["difference"] is None
    assert [group["at"] for group in found["evidence"]] == ["seed_n1_end"]


def test_each_metric_sits_beside_the_comparable_batches_median_and_range(seeded, client):
    answer = client.get("/api/batches/BL-0004/metrics").json()
    assert answer["comparable_batch_ids"] == ["BK-0007", "BK-0008", "BK-0009", "BL-0001", "BL-0002"]
    found = {item["metric"]: item["comparable"] for item in answer["metrics"]}
    recovery = found["protein_a_recovery"]
    assert recovery["status"] == "usable" and codes(recovery) == ["below_expected_range"]
    seen = recovery["reasons"][0]["values"]
    assert seen["count"] == 5 and 91 < seen["lowest"] < seen["median"] < seen["highest"] < 94
    assert recovery["value"] == pytest.approx(73.39 - seen["median"], abs=0.01)
    assert codes(found["qp"]) == ["within_expected_range"]
    # A normal batch just outside what five batches happened to give is not remarked on.
    started = found["inoculation_density"]["reasons"][0]
    assert started["code"] == "within_expected_range"
    assert started["values"]["expected_low"] < 0.5 < started["values"]["lowest"]
    # A comparable batch is not read against itself: four others are left.
    own = client.get("/api/batches/BL-0002/metrics").json()
    assert "BL-0002" not in own["comparable_batch_ids"]
    assert own["metrics"][0]["comparable"]["reasons"][0]["values"]["count"] == 4
    # The badly recorded batch has no IVCD to place.
    bad = {
        m["metric"]: m["comparable"]
        for m in client.get("/api/batches/BL-0005/metrics").json()["metrics"]
    }
    assert (bad["ivcd"]["status"], codes(bad["ivcd"])) == ("insufficient", ["input_not_usable"])


def test_comparable_batches_are_read_as_of_the_same_moment(seeded, client):
    culture = CAMPAIGN["BL-0004"].record.phase("production_culture")
    as_of = (culture.start + timedelta(days=5)).isoformat()
    found = {
        m["metric"]: m
        for m in client.get("/api/batches/BL-0004/metrics", params={"as_of": as_of}).json()[
            "metrics"
        ]
    }
    # The comparable batches finished long before: their harvest masses are known, this one's not.
    assert found["harvest_mass"]["value"] is None
    assert codes(found["harvest_mass"]["comparable"]) == ["input_not_usable"]
    assert codes(found["ivcd"]["comparable"])[0].endswith("_expected_range")


def transfers_of(client, batch_id: str, **params) -> list[dict]:
    return client.get(f"/api/batches/{batch_id}/metrics", params=params).json()["transfers"]


def test_every_feed_is_checked_against_the_bioreactors_volume(seeded, client):
    rows = transfers_of(client, "BL-0001")
    assert [row["kind"] for row in rows][:12] == ["passage", "inoculation", *["feed"] * 10]
    for feed in rows[2:12]:
        assert (feed["from_asset_id"], feed["to_asset_id"]) == ("MH-1201", "BR-2001")
        assert feed["volume"] == pytest.approx(60, abs=1) and feed["volume_unit"] == "L"
        balance = feed["balance"]
        assert balance["status"] == "usable" and abs(balance["value"]) < 5
        assert codes(balance) == ["transfer_balanced"]
        # Checked at both ends: the bioreactor's rise and the feed tank's fall.
        assert balance["inputs"] == [
            feed["transfer_id"],
            BIO_SIGNALS["volume"],
            "batchlens-synthetic:BIO.MH-1201.VOLUME",
        ]
        seen = balance["reasons"][0]["values"]
        assert seen["arrived"] == pytest.approx(60, abs=3) and seen["left"] == pytest.approx(
            60, abs=3
        )
    # The passage is checked at both seed reactors. The bioreactor recorded nothing before its
    # culture began, so the inoculation is checked by what left the last seed reactor alone.
    passage, inoculation = rows[:2]
    assert (passage["from_asset_id"], passage["to_asset_id"]) == ("BR-1001", "BR-1002")
    assert passage["balance"]["status"] == "usable" and abs(passage["balance"]["value"]) < 5
    assert set(passage["balance"]["reasons"][0]["values"]) >= {"arrived", "left"}
    assert inoculation["to_asset_id"] == "BR-2001" and 150 < inoculation["volume"] < 250
    assert inoculation["balance"]["status"] == "usable" and abs(inoculation["balance"]["value"]) < 5
    seen = inoculation["balance"]["reasons"][0]["values"]
    assert "arrived" not in seen and seen["left"] == pytest.approx(inoculation["volume"], rel=0.05)


def test_a_feed_recorded_with_a_digit_dropped_is_flagged_not_corrected(seeded, client):
    assert TRUTH["BL-0005"].mis_recorded_transfer == "BL-0005-T09"
    rows = {row["transfer_id"]: row for row in transfers_of(client, "BL-0005")}
    bad = rows["BL-0005-T09"]
    assert bad["volume"] == pytest.approx(6, abs=0.2)  # as recorded: the app changes nothing
    assert bad["balance"]["status"] == "suspect" and bad["balance"]["value"] > 800
    assert codes(bad["balance"]) == ["outside_transfer_tolerance"]
    assert bad["balance"]["reasons"][0]["values"]["arrived"] == pytest.approx(60, abs=3)
    others = [row for key, row in rows.items() if key != "BL-0005-T09" and row["kind"] == "feed"]
    assert len(others) == 9 and all(row["balance"]["status"] == "usable" for row in others)
    # The low-inoculum batch moved the whole N-1 vessel.
    low = transfers_of(client, "BL-0006")[1]
    assert low["kind"] == "inoculation" and low["volume"] == pytest.approx(250, abs=4)


def test_transfers_in_an_as_of_view_are_only_those_begun_and_balanced_only_once_ended(
    seeded, client
):
    culture = CAMPAIGN["BL-0002"].record.phase("production_culture")
    # Five minutes into the first feed (it takes ten, ending at culture day 3).
    during = (culture.start + timedelta(days=3, minutes=-5)).isoformat()
    rows = transfers_of(client, "BL-0002", as_of=during)
    assert [row["kind"] for row in rows] == ["passage", "inoculation", "feed"]
    feed = rows[-1]
    assert feed["end"] is None and feed["volume"] is None
    assert codes(feed["balance"]) == ["transfer_not_ended"]
    after = (culture.start + timedelta(days=3, minutes=1)).isoformat()
    feed = transfers_of(client, "BL-0002", as_of=after)[-1]
    assert feed["end"] is not None and feed["balance"]["status"] == "usable"


def test_evidence_says_how_long_after_a_feed_each_sample_was_taken(seeded, client):
    finding = finding_of(client, "BL-0003", "titer_divergence")
    # At the divergence (culture day 8): daily feeds, daily samples within three hours of the
    # same clock time. The last sample (day 14) comes two days after the last feed (day 12).
    at_divergence, last = finding["evidence"]
    for key in ("hours_since_feed", "reference_hours_since_feed"):
        assert 0 <= at_divergence[key] < 27 and 40 < last[key] < 52
    record = CAMPAIGN["BL-0003"].record
    sample = next(s for s in record.samples if s.sample_id == finding["evidence"][0]["sample_id"])
    feeds = [t.end for t in record.transfers if t.kind == "feed" and t.end <= sample.collected_at]
    expected = (sample.collected_at - max(feeds)).total_seconds() / 3600
    assert finding["evidence"][0]["hours_since_feed"] == pytest.approx(expected)
    # The N-1 sample beside a low inoculation was taken before any feed.
    low = finding_of(client, "BL-0006", "inoculation_density_shortfall")["evidence"][0]
    assert low["hours_since_feed"] is None and low["reference_hours_since_feed"] is None


@pytest.mark.parametrize("batch_id", ["BL-0002", "BL-0003"])
def test_batches_with_a_normal_capture_step_get_no_recovery_shortfall(seeded, client, batch_id):
    for kind in FINDINGS[2:]:
        observation = finding_of(client, batch_id, kind)["observation"]
        assert (observation["status"], observation["value"]) == ("usable", None)
        assert codes(observation) == ["within_reference"]


def test_a_recovery_finding_waits_for_the_pool_measurements(seeded, client):
    capture = CAMPAIGN["BL-0004"].record.phase("protein_a_capture")
    finding = finding_of(
        client, "BL-0004", "protein_a_recovery_shortfall", as_of=capture.start.isoformat()
    )
    assert finding["observation"]["status"] == "insufficient"
    assert codes(finding["observation"]) == ["input_not_usable"]


def test_the_divergence_comes_with_the_other_results_of_the_same_samples_as_evidence(
    seeded, client
):
    finding = finding_of(client, "BL-0003", "titer_divergence")
    seen = finding["observation"]["reasons"][0]["values"]
    at_divergence, at_last = finding["evidence"]
    assert (at_divergence["at"], at_last["at"]) == ("divergence", "last_sample")
    assert at_divergence["sample_id"] == seen["result_id"].removesuffix("-titer")
    assert at_divergence["reference_sample_id"] == seen["reference_result_id"].removesuffix(
        "-titer"
    )
    assert at_last["sample_id"] == "BL-0003-S15" and at_last["reference_sample_id"] == "BL-0001-S15"
    for group in (at_divergence, at_last):
        assert 7 < group["culture_day"] < 15
        assert [row["analyte"] for row in group["results"]] == [
            "glucose",
            "lactate",
            "titer",
            "vcd",
            "viability",
        ]
        for row in group["results"]:
            assert row["result_id"] == f"{group['sample_id']}-{row['analyte']}"
            assert row["reference_result_id"] == f"{group['reference_sample_id']}-{row['analyte']}"
            assert row["unit"] and row["value"] is not None and row["reference_value"] is not None
            assert row["difference"] == pytest.approx(row["value"] - row["reference_value"])
    # The numbers are there to be read; nothing is concluded from them.
    last = {row["analyte"]: row for row in at_last["results"]}
    assert last["lactate"]["difference"] > 1 and last["titer"]["difference"] < -1
    assert "interpretation" not in finding and finding["cause"] is None
    # No divergence, no evidence.
    assert finding_of(client, "BL-0002", "titer_divergence")["evidence"] == []


def test_evidence_holds_only_what_was_available_at_as_of(seeded, client):
    culture = CAMPAIGN["BL-0003"].record.phase("production_culture")
    as_of = (culture.start + timedelta(days=12)).isoformat()
    finding = finding_of(client, "BL-0003", "titer_divergence", as_of=as_of)
    last = finding["evidence"][1]
    # Titers arrive a day late, so the last compared sample is not the last collected one.
    assert last["sample_id"] < "BL-0003-S13"
    available = client.get("/api/batches/BL-0003/samples", params={"as_of": as_of}).json()
    known = {r["result_id"] for sample in available["samples"] for r in sample["results"]}
    for group in finding["evidence"]:
        assert {row["result_id"] for row in group["results"]} <= known


def test_samples_carry_their_culture_day_and_can_be_laid_over_another_batch(seeded, client):
    own = client.get("/api/batches/BL-0003/samples").json()["samples"]
    record = CAMPAIGN["BL-0003"].record
    for sample in own:
        # The age counts from the start of the sample's own phase: a seed passage's from its own.
        began = record.phase(sample["phase_kind"]).start
        age = (instant(sample["collected_at"]) - began).total_seconds() / 86400
        assert 0 <= age <= 14.25
        assert sample["culture_day"] == pytest.approx(age)
        assert sample["aligned_at"] is None
    # The reference batch's samples, placed at the same culture age on BL-0003's timeline.
    laid = client.get("/api/batches/BL-0001/samples", params={"align_to": "BL-0003"}).json()
    assert laid["aligned_to"] == "BL-0003"
    for sample in laid["samples"]:
        # Each on the same phase of BL-0003: a seed passage's sample on that seed passage.
        shifted = record.phase(sample["phase_kind"]).start + timedelta(days=sample["culture_day"])
        assert abs((instant(sample["aligned_at"]) - shifted).total_seconds()) < 0.002
    assert (
        client.get("/api/batches/BL-0001/samples", params={"align_to": "BL-9999"}).status_code
        == 404
    )


def test_the_batch_whose_titer_left_the_reference_gets_a_finding_in_three_separate_parts(
    seeded, client
):
    finding = finding_of(client, "BL-0003", "titer_divergence")
    # The observation: where, with the samples it rests on.
    observation = finding["observation"]
    assert (observation["status"], observation["unit"]) == ("usable", "days")
    assert 7 < observation["value"] < 10  # seen at the first samples after it began
    [reason] = observation["reasons"]
    assert reason["code"] == "diverged_from_reference"
    assert reason["values"]["result_id"].startswith("BL-0003-S")
    assert reason["values"]["reference_result_id"].startswith("BL-0001-S")
    assert reason["values"]["titer"] < reason["values"]["reference_titer"]
    assert reason["values"]["later_samples_below"] >= 3
    assert {i[:7] for i in observation["inputs"]} == {"BL-0003", "BL-0001"}
    # The calculation: what the batch had at harvest against the reference, in grams.
    harvest = metrics_of(client, "BL-0003")["harvest_mass"]
    assert finding["consequence"] == {
        "metric": "harvest_mass",
        "unit": "g",
        "status": "usable",
        "value": harvest["value"],
        "reference": harvest["reference"]["value"],
        "difference": harvest["difference"],
    }
    assert finding["consequence"]["difference"] < -2000
    # And no cause: the app observes and calculates, it does not diagnose.
    assert finding["cause"] is None


@pytest.mark.parametrize("batch_id", ["BL-0002", "BL-0004"])
def test_a_batch_that_followed_the_reference_gets_the_finding_that_nothing_diverged(
    seeded, client, batch_id
):
    finding = finding_of(client, batch_id, "titer_divergence")
    assert (finding["observation"]["status"], finding["observation"]["value"]) == ("usable", None)
    assert codes(finding["observation"]) == ["no_divergence"]
    assert finding["consequence"] is None and finding["cause"] is None


def test_the_reference_batch_is_not_compared_with_itself(seeded, client):
    assert findings_of(client, "BL-0001") == []


def test_a_finding_uses_only_what_was_available_at_as_of(seeded, client):
    culture = CAMPAIGN["BL-0003"].record.phase("production_culture")
    # Day 6.5: before the titer left the reference, and before day 6's own titer came in.
    early = finding_of(
        client,
        "BL-0003",
        "titer_divergence",
        as_of=(culture.start + timedelta(days=6.5)).isoformat(),
    )
    assert early["observation"]["value"] is None
    assert codes(early["observation"]) == ["no_divergence", "result_not_yet_available"]
    assert early["consequence"] is None
    # Before any titer of the batch exists there is nothing to compare.
    none = finding_of(
        client,
        "BL-0003",
        "titer_divergence",
        as_of=(culture.start + timedelta(hours=2)).isoformat(),
    )
    assert none["observation"]["status"] == "insufficient"
    # After the divergence is seen but before harvest: the observation stands, and the
    # consequence says the harvest mass is not there yet rather than leaving it out.
    mid = finding_of(
        client,
        "BL-0003",
        "titer_divergence",
        as_of=(culture.start + timedelta(days=12)).isoformat(),
    )
    assert mid["observation"]["value"] is not None
    assert (mid["consequence"]["status"], mid["consequence"]["difference"]) == (
        "insufficient",
        None,
    )


def test_without_the_bioreactor_the_observation_stands_and_the_consequence_says_what_is_missing(
    tmp_path,
):
    fake = make_fake(bioprocess=False)
    runtime = make_runtime(tmp_path, fake)
    try:
        seed_demo(runtime.batches)
        with client_for(runtime, fake) as client:
            finding = finding_of(client, "BL-0003", "titer_divergence")
            assert finding["observation"]["value"] is not None  # titers are the app's own records
            assert finding["consequence"]["status"] == "insufficient"
            assert finding["consequence"]["difference"] is None
    finally:
        runtime.shutdown()


# A batch whose records are bad ------------------------------------------------------------------


def test_the_badly_recorded_batch_is_flagged_everywhere_and_answered_nowhere_it_should_not_be(
    seeded, client
):
    found = metrics_of(client, "BL-0005")
    assert (found["ivcd"]["status"], found["ivcd"]["value"]) == ("invalid", None)
    assert codes(found["ivcd"]) == ["times_not_increasing"]
    assert found["ivcd"]["reasons"][0]["values"]["id"] == "BL-0005-S09-vcd"
    assert (found["qp"]["status"], found["qp"]["value"]) == ("invalid", None)
    assert (found["harvest_mass"]["status"], found["harvest_mass"]["value"]) == (
        "insufficient",
        None,
    )
    assert codes(found["harvest_mass"]) == ["no_volume_near_sample"]
    assert found["harvest_to_load_yield"]["status"] == "insufficient"
    assert found["protein_a_recovery"]["status"] == "usable"
    # No number, so no difference from the reference either.
    assert found["ivcd"]["difference"] is None and found["harvest_mass"]["difference"] is None
    titer, started, step_yield, recovery, *later = findings_of(client, "BL-0005")
    assert codes(started["observation"]) == ["inoculation_within_reference"]
    assert all(codes(f["observation"]) == ["within_reference"] for f in later)
    assert (titer["observation"]["status"], titer["observation"]["value"]) == ("invalid", None)
    assert codes(titer["observation"]) == ["times_not_increasing"]
    assert titer["consequence"] is None and titer["evidence"] == []
    assert step_yield["observation"]["status"] == "insufficient"
    assert codes(recovery["observation"]) == ["within_reference"]


def test_the_hole_in_the_historian_shows_in_the_trends_as_missing_values(seeded, client):
    answer = client.get("/api/batches/BL-0005/trends").json()
    culture = CAMPAIGN["BL-0005"].record.phase("production_culture")
    hole = culture.start + timedelta(days=13.4)
    for signal in answer["signals"]:
        assert signal["status"] == "usable"
        values = dict(zip(map(instant, signal["t"]), signal["v"]))
        assert any(v is not None for t, v in values.items() if t < hole - timedelta(hours=2))
        # Nothing is drawn across the hole: no value, or no point at all.
        assert all(v is None for t, v in values.items() if t >= hole)
        assert sum(v is None for v in signal["v"]) >= 15  # about 20 h at 69 min a step


# The span an as-of control moves over ------------------------------------------------------------


def test_a_batch_says_from_when_to_when_anything_about_it_became_known(seeded, client):
    record = CAMPAIGN["BL-0003"].record
    timeline = client.get("/api/batches/BL-0003").json()["timeline"]
    assert instant(timeline["start"]) == record.phases[0].start
    last_known = max(
        [phase.end for phase in record.phases]
        + [result.result_available_at for result in record.results]
        + [pool.result_available_at for pool in record.pools]
    )
    assert instant(timeline["end"]) == last_known
    # At the end of the span everything is known: the same answer as without as_of.
    whole = client.get("/api/batches/BL-0003/metrics").json()
    at_end = client.get("/api/batches/BL-0003/metrics", params={"as_of": timeline["end"]}).json()
    assert at_end["metrics"] == whole["metrics"] and at_end["findings"] == whole["findings"]


def test_an_as_of_view_does_not_know_the_future(seeded, client):
    record = CAMPAIGN["BL-0003"].record
    culture = record.phase("production_culture")
    as_of = culture.start + timedelta(days=6.5)  # day 6's sample is taken, its titer not reported
    params = {"as_of": as_of.isoformat()}
    # Samples collected after as_of do not exist yet: no metric or finding names them.
    answer = client.get("/api/batches/BL-0003/metrics", params=params).json()
    collected = {s.sample_id: s.collected_at for s in record.samples}
    named = [
        result_id
        for item in [*answer["metrics"], *(f["observation"] for f in answer["findings"])]
        for reason in item["reasons"]
        for result_id in reason["values"].get("ids", [])
    ]
    assert named, "day 6's own titer is collected and still pending: it is named"
    assert all(collected[i.rsplit("-", 1)[0]] <= as_of for i in named if i.startswith("BL-0003"))
    # The batch itself: the culture is in progress, the later phases have not begun, and no
    # pool has been measured.
    detail = client.get("/api/batches/BL-0003", params=params).json()
    assert instant(detail["as_of"]) == as_of
    *seed, phase = detail["phases"]
    assert [(p["kind"], p["end"] is not None) for p in seed] == [
        ("seed_n2", True),
        ("seed_n1", True),
    ]
    assert (phase["kind"], phase["end"]) == ("production_culture", None)
    assert detail["pools"] == []
    # After everything: all three phases with their ends, both pools.
    whole = client.get("/api/batches/BL-0003").json()
    assert whole["as_of"] is None and len(whole["phases"]) == 10 and len(whole["pools"]) == 11
    assert all(phase["end"] for phase in whole["phases"])
    assert client.get("/api/batches/BL-0003", params={"as_of": "soon"}).status_code == 422
    # The list is not an as-of view: it has no as_of.
    before = client.get(
        "/api/batches/BL-0003", params={"as_of": (culture.start - timedelta(days=7)).isoformat()}
    )
    assert before.status_code == 200 and before.json()["phases"] == []


def test_a_value_that_is_not_a_number_never_reaches_a_trend():
    from batchlens.api.plant import _step_means

    start = datetime(2026, 7, 1, 6, tzinfo=UTC)
    stamps = [(start + timedelta(minutes=10 * i)).isoformat() for i in range(4)]
    marks, values = _step_means(
        stamps, [1.0, float("nan"), 3.0, float("inf")], start, start + timedelta(hours=1), 1200
    )
    # Steps of 20 minutes: [1.0, nan] -> 1.0; [3.0, inf] -> 3.0; the third step has nothing.
    assert values == [1.0, 3.0, None] and len(marks) == 3


def test_feeds_and_buffers_name_the_lot_they_came_from_and_how_old_it_was(seeded, client):
    rows = transfers_of(client, "BL-0001")
    assert [row["kind"] for row in rows] == [
        "passage",
        "inoculation",
        *["feed"] * 10,
        *["buffer"] * 3,
    ]
    assert rows[0]["from_lot_id"] == "" and rows[0]["lot_solution"] is None
    feeds = rows[2:12]
    assert {feed["from_lot_id"] for feed in feeds} == {"BL-0001-MF"}
    assert {feed["lot_solution"] for feed in feeds} == {"Feed medium"}
    # One lot of medium for ten daily feeds: made the day before the first, so it is a day old
    # at the first feed (less the ten minutes a feed takes) and ten days old at the last.
    ages = [feed["lot_age_days"] for feed in feeds]
    assert ages[0] == pytest.approx(1 - (2 * 60 + 10) / 1440) and ages[-1] == pytest.approx(
        ages[0] + 9
    )
    buffers = {row["lot_solution"]: row for row in rows[12:]}
    assert sorted(buffers) == [
        "Cation-exchange elution buffer",
        "Diafiltration buffer",
        "Protein A elution buffer",
    ]
    elution = buffers["Protein A elution buffer"]
    assert (elution["from_asset_id"], elution["to_asset_id"]) == ("BH-1301", "CH-3001")
    assert elution["from_lot_id"] == "BL-0001-BA" and elution["volume"] == pytest.approx(
        300, rel=0.05
    )
    assert elution["lot_age_days"] == pytest.approx(1.0)  # prepared 26 h before, in 2 h
    # Neither the hold tank nor the skid has a volume signal: listed, not checked, both named.
    assert codes(elution["balance"]) == ["signal_not_found", "signal_not_found"]
    named = [reason["values"]["asset_id"] for reason in elution["balance"]["reasons"]]
    assert named == ["CH-3001", "BH-1301"]


def test_a_solution_lot_is_a_batch_of_its_own_kind_and_is_not_listed(seeded, client):
    listed = [row["batch_id"] for row in client.get("/api/batches").json()["batches"]]
    assert len(listed) == 9 and not any(batch_id.endswith(("-MF", "-BA")) for batch_id in listed)
    lot = client.get("/api/batches/BL-0004-BA").json()
    assert (lot["batch"]["kind"], lot["batch"]["product"]) == ("buffer", "Protein A elution buffer")
    assert [(p["kind"], p["asset_id"]) for p in lot["phases"]] == [
        ("solution_prep", "MX-1101"),
        ("solution_hold", "BH-1301"),
    ]
    [sample] = client.get("/api/batches/BL-0004-BA/samples").json()["samples"]
    assert sample["phase_kind"] == "solution_prep"
    found = {r["analyte"]: (r["value"], r["unit"]) for r in sample["results"]}
    assert found["ph"][1] == "pH" and found["conductivity"][1] == "mS/cm"
    assert found["ph"][0] == pytest.approx(3.9, abs=0.1)  # this lot was made off its target
    assert client.get("/api/batches/BL-0001").json()["batch"]["kind"] == "product"
    medium = client.get("/api/batches/BL-0004-MF/samples").json()["samples"][0]
    assert sorted(r["analyte"] for r in medium["results"]) == ["osmolality", "ph"]
    # A lot is never the reference and never among the comparable batches.
    assert client.get("/api/batches/BL-0002/metrics").json()["reference_batch_id"] == "BL-0001"


def test_a_database_from_before_solution_lots_is_upgraded_and_its_batches_are_products(tmp_path):
    import sqlite3

    from batchlens.config import Settings

    path = Settings(processcraft_url="http://x", data_dir=tmp_path).database_path
    with sqlite3.connect(path) as old:  # the batches table as it was before the kind column
        old.execute(
            "CREATE TABLE batches (batch_id TEXT PRIMARY KEY, product TEXT NOT NULL, "
            "is_reference INTEGER NOT NULL, created_at TEXT NOT NULL, provenance TEXT NOT NULL)"
        )
        old.execute(
            "INSERT INTO batches VALUES ('OLD-1', 'mAb-X', 1, '2026-01-01T00:00:00.000Z', 'p')"
        )
        old.execute(
            "CREATE TABLE pool_links (link_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, "
            "from_pool_id TEXT NOT NULL, to_pool_id TEXT NOT NULL, provenance TEXT NOT NULL)"
        )
        old.execute("INSERT INTO pool_links VALUES ('OLD-1-L01', 'OLD-1', 'a', 'b', 'p')")
    old.close()
    runtime = make_runtime(tmp_path, make_fake())
    try:
        kept = runtime.batches.get("OLD-1")
        assert kept is not None and kept.batch.kind == "product" and kept.batch.is_reference
        assert [batch.batch_id for batch, _ in runtime.batches.summaries()] == ["OLD-1"]
        assert [link.kind for link in kept.links] == ["process"]
        seed_demo(runtime.batches)  # and the new kind is stored beside it
        assert runtime.batches.get("BL-0001-MF").batch.kind == "medium"
        # Links stored before they had a kind are steps; the generator's now say which.
        kinds = {link.kind for link in runtime.batches.get("BL-0001").links}
        assert kinds == {"process", "portion"}
    finally:
        runtime.shutdown()


def test_a_step_that_recovered_less_shows_the_buffer_lot_it_drew_beside_the_references(
    seeded, client
):
    assert TRUTH["BL-0004"].elution_buffer_ph == 3.9  # the generator's own cause
    finding = finding_of(client, "BL-0004", "protein_a_recovery_shortfall")
    [group] = finding["evidence"]
    assert (group["at"], group["solution"]) == ("buffer_lot", "Protein A elution buffer")
    assert (group["lot_id"], group["reference_lot_id"]) == ("BL-0004-BA", "BL-0001-BA")
    assert (group["sample_id"], group["reference_sample_id"]) == (
        "BL-0004-BA-S01",
        "BL-0001-BA-S01",
    )
    assert group["age_days"] == pytest.approx(1.0) and group["reference_age_days"] == pytest.approx(
        1.0
    )
    rows = {row["analyte"]: row for row in group["results"]}
    assert sorted(rows) == ["conductivity", "ph"]
    # Evidence, not a verdict: the numbers of both lots and their difference.
    assert rows["ph"]["value"] == pytest.approx(3.9, abs=0.08)
    assert rows["ph"]["reference_value"] == pytest.approx(3.5, abs=0.08)
    assert rows["ph"]["difference"] == pytest.approx(0.4, abs=0.1)
    assert abs(rows["conductivity"]["difference"]) < 0.6
    assert finding["cause"] is None
    # Beside each, what the comparable batches' lots lead to expect: the pH is above it, and
    # the conductivity, which differs from the reference's by as much, is not.
    among = {analyte: row["comparable"]["reasons"][0] for analyte, row in rows.items()}
    assert among["ph"]["code"] == "above_expected_range" and among["ph"]["values"]["count"] == 5
    assert among["ph"]["values"]["expected_high"] < 3.7
    assert among["conductivity"]["code"] == "within_expected_range"
    # A step within tolerance carries no lot table, and neither does another finding.
    for batch_id in ("BL-0002", "BL-0003"):
        assert finding_of(client, batch_id, "protein_a_recovery_shortfall")["evidence"] == []
    assert finding_of(client, "BL-0004", "cation_exchange_yield_shortfall")["evidence"] == []


def test_lot_evidence_holds_only_what_was_available_at_as_of(seeded, client):
    record = CAMPAIGN["BL-0004"].record
    eluate = next(pool for pool in record.pools if pool.pool == "protein_a_eluate")
    # Once the eluate was reported the shortfall is found; the lot was sampled a day earlier.
    as_of = (eluate.result_available_at + timedelta(minutes=1)).isoformat()
    finding = finding_of(client, "BL-0004", "protein_a_recovery_shortfall", as_of=as_of)
    assert finding["observation"]["value"] > 15 and len(finding["evidence"]) == 1
    # With the lot of the batch gone from the store, the finding stands and shows no lot.
    seeded.batches.store._connect().execute(
        "DELETE FROM batches WHERE batch_id = 'BL-0004-BA'"
    ).connection.commit()
    assert finding_of(client, "BL-0004", "protein_a_recovery_shortfall")["evidence"] == []


def test_one_window_without_values_does_not_give_the_signal_up_for_the_request(monkeypatch):
    """PlantCraft 0.6.0 answers a window in which nothing was recorded as a failed read (seen
    on the live demo: the batch with a hole in its historian lost its bioreactor for every
    transfer on the page). A second failure does give it up: that is a dead source."""

    from batchlens.api import plant

    failed = calc.Reason("series_unreadable", {"detail": "No tag was loaded"})
    answers = [failed, {"t": ["2026-07-01T06:00:00Z"], "v": [1400.0]}, failed]
    asked = []

    def read(call, missing):
        asked.append(1)
        return answers[len(asked) - 1]

    monkeypatch.setattr(plant, "_read", read)
    monkeypatch.setattr(plant, "_signal", lambda *args: {"id": "sig", "unit": "L"})
    monkeypatch.setattr(plant, "asset", lambda *args: {})
    seen: dict = {}
    window = (datetime(2026, 7, 1, tzinfo=UTC), datetime(2026, 7, 2, tzinfo=UTC))
    assert plant.volume_between(None, "BR-2001", *window, seen) is failed
    second = plant.volume_between(None, "BR-2001", *window, seen)
    assert isinstance(second, calc.Online) and len(second.points) == 1
    assert plant.volume_between(None, "BR-2001", *window, seen) is failed and len(asked) == 3
    # Twice failed: not asked again.
    assert plant.volume_between(None, "BR-2001", *window, seen) is failed and len(asked) == 3
