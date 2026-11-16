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
    assert seed_demo(runtime.batches) == ["BL-0001", "BL-0002", "BL-0003", "BL-0004", "BL-0005"]
    for batch_id, observations in CAMPAIGN.items():
        assert runtime.batches.get(batch_id) == observations.record
    assert runtime.batches.get("BL-9999") is None
    assert runtime.batches.get("'; DROP TABLE batches; --") is None


def test_seeding_twice_changes_nothing(seeded):
    before = seeded.batches.get("BL-0002")
    seed_demo(seeded.batches)
    assert len(seeded.batches.summaries()) == 5
    assert seeded.batches.get("BL-0002") == before


def test_the_command_line_seeds_the_demo(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("BATCHLENS_DATA_DIR", str(tmp_path))
    # The command sets up logging on the captured stderr; give the root logger back afterwards.
    monkeypatch.setattr(logging.root, "handlers", [])
    assert main(["seed-demo"]) == 0
    seeded = json.loads(capsys.readouterr().out)["batches"]
    assert seeded == ["BL-0001", "BL-0002", "BL-0003", "BL-0004", "BL-0005"]
    runtime = make_runtime(tmp_path, make_fake())
    try:
        assert len(runtime.batches.summaries()) == 5
    finally:
        runtime.shutdown()


# The routes ------------------------------------------------------------------------------------


def test_the_list_gives_each_batch_its_reference_flag_window_and_bioreactor(seeded, client):
    answer = client.get("/api/batches").json()
    assert answer["time_zone"] == "UTC"
    rows = answer["batches"]
    assert [row["batch_id"] for row in rows] == [
        "BL-0001",
        "BL-0002",
        "BL-0003",
        "BL-0004",
        "BL-0005",
    ]
    assert [row["is_reference"] for row in rows] == [True, False, False, False, False]
    first, record = rows[0], CAMPAIGN["BL-0001"].record
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
            assert len(rows) == 5 and rows[0]["asset_name"] is None
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
    assert finding["evidence"] == []
    # Its culture was normal, and so was its yield into the step, within the tolerance.
    assert codes(finding_of(client, "BL-0004", "titer_divergence")["observation"]) == [
        "no_divergence"
    ]
    step_yield = finding_of(client, "BL-0004", "harvest_to_load_yield_shortfall")
    assert codes(step_yield["observation"]) == ["within_reference"]
    assert step_yield["consequence"] is None


@pytest.mark.parametrize("batch_id", ["BL-0002", "BL-0003"])
def test_batches_with_a_normal_capture_step_get_no_recovery_shortfall(seeded, client, batch_id):
    for kind in FINDINGS[1:]:
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
    titer, step_yield, recovery, *later = findings_of(client, "BL-0005")
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
    assert whole["as_of"] is None and len(whole["phases"]) == 10 and len(whole["pools"]) == 9
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
