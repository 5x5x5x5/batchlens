"""The two things a person may change: a sample's collection time (a correction, with a reason
and a kept history) and which batch is the reference. Editors change, viewers read, every
change is audited in PlantCraft, and nothing else about a batch can be written."""

from __future__ import annotations

from datetime import timedelta

import pytest

from batchlens.demo.generator import demo_campaign
from batchlens.demo.seed import seed_demo
from tests.conftest import client_for

CAMPAIGN = {o.record.batch.batch_id: o for o in demo_campaign()[0]}
BAD = CAMPAIGN["BL-0005"].record
S08, S09 = (next(s for s in BAD.samples if s.sample_id == f"BL-0005-S0{n}") for n in (8, 9))
URL = "/api/batches/BL-0005/samples/BL-0005-S09"
# Sample 9 was keyed in with sample 8's time; a day later is where a daily sample belongs.
RIGHT_TIME = S08.collected_at + timedelta(days=1)


def correction(**changes) -> dict:
    return {
        "collected_at": RIGHT_TIME.isoformat(),
        "reason": "Keyed in with the previous sample's time; corrected from the sample label.",
        **changes,
    }


def metric(client, batch_id: str, name: str) -> dict:
    found = client.get(f"/api/batches/{batch_id}/metrics").json()["metrics"]
    return next(item for item in found if item["metric"] == name)


def test_an_editor_corrects_a_mis_keyed_sample_time_and_the_metrics_follow(seeded, fake, client):
    assert metric(client, "BL-0005", "ivcd")["status"] == "invalid"
    answer = client.patch(URL, json=correction())
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["sample_id"] == "BL-0005-S09"
    assert body["collected_at"].startswith(RIGHT_TIME.strftime("%Y-%m-%dT%H:%M:%S"))
    # The culture metrics can now be computed; the historian's hole is still a hole.
    ivcd = metric(client, "BL-0005", "ivcd")
    assert ivcd["status"] == "usable" and 150 < ivcd["value"] < 210
    assert metric(client, "BL-0005", "qp")["status"] == "usable"
    assert metric(client, "BL-0005", "harvest_mass")["status"] == "insufficient"
    # PlantCraft's audit log names who changed what, from what, to what, and why.
    [entry] = [item for item in fake.audit_log if item["action"] == "batchlens.sample.corrected"]
    assert entry["username"] == "engineer" and entry["subject"] == "BL-0005-S09"
    assert entry["detail"]["batch"] == "BL-0005" and entry["detail"]["field"] == "collected_at"
    assert entry["detail"]["old"].startswith(S08.collected_at.strftime("%Y-%m-%dT%H:%M:%S"))
    assert entry["detail"]["new"].startswith(RIGHT_TIME.strftime("%Y-%m-%dT%H:%M:%S"))
    assert "sample label" in entry["detail"]["reason"]


def test_the_original_value_is_kept_beside_the_correction(seeded, client):
    assert client.get("/api/batches/BL-0005").json()["corrections"] == []
    client.patch(URL, json=correction())
    client.patch(URL, json=correction(collected_at=(RIGHT_TIME + timedelta(hours=1)).isoformat()))
    first, second = client.get("/api/batches/BL-0005").json()["corrections"]
    assert (first["record_id"], first["field"], first["corrected_by"]) == (
        "BL-0005-S09",
        "collected_at",
        "engineer",
    )
    assert first["old_value"].startswith(S08.collected_at.strftime("%Y-%m-%dT%H:%M:%S"))
    assert first["new_value"] == second["old_value"]
    assert first["reason"] and first["corrected_at"] <= second["corrected_at"]
    # The samples route marks what was corrected.
    samples = client.get("/api/batches/BL-0005/samples").json()["samples"]
    assert [s["corrected"] for s in samples if s["sample_id"] == "BL-0005-S09"] == [True]
    assert sum(s["corrected"] for s in samples) == 1


def test_viewers_and_strangers_cannot_correct(seeded, fake):
    with client_for(seeded, fake, "operator") as viewer:
        assert viewer.patch(URL, json=correction()).status_code == 403
        assert viewer.put("/api/batches/BL-0002/reference").status_code == 403
    with client_for(seeded, fake, "outsider") as outsider:
        assert outsider.patch(URL, json=correction()).status_code == 403
    with client_for(seeded, fake, None) as anonymous:
        assert anonymous.patch(URL, json=correction()).status_code == 401
        assert anonymous.put("/api/batches/BL-0002/reference").status_code == 401
    assert fake.audit_log == []
    assert seeded.batches.get("BL-0005") == BAD


@pytest.mark.parametrize(
    ("url", "status"),
    [
        ("/api/batches/BL-9999/samples/BL-0005-S09", 404),
        ("/api/batches/BL-0005/samples/BL-0005-S99", 404),
        ("/api/batches/BL-0004/samples/BL-0005-S09", 404),  # another batch's sample
    ],
)
def test_a_sample_that_is_not_there_is_a_404(seeded, client, url, status):
    assert client.patch(url, json=correction()).status_code == status


@pytest.mark.parametrize(
    "body",
    [
        correction(collected_at="yesterday"),
        correction(collected_at="12"),
        correction(reason=""),
        correction(reason="x"),
        correction(reason="x" * 600),
        correction(value=3.2),  # nothing but the time and the reason may be sent
        {"collected_at": RIGHT_TIME.isoformat()},
        {},
        # Outside the production phase the sample belongs to.
        correction(
            collected_at=(BAD.phase("production_culture").start - timedelta(hours=1)).isoformat()
        ),
        correction(
            collected_at=(BAD.phase("production_culture").end + timedelta(hours=1)).isoformat()
        ),
        # After one of its own results was already reported: a sample cannot be taken after that.
        correction(collected_at=(S09.collected_at + timedelta(days=5)).isoformat()),
    ],
)
def test_a_correction_that_breaks_a_rule_is_a_422_and_changes_nothing(seeded, fake, client, body):
    answer = client.patch(URL, json=body)
    assert answer.status_code == 422, answer.text
    assert seeded.batches.get("BL-0005") == BAD and fake.audit_log == []


def test_an_editor_makes_another_batch_the_reference(seeded, fake, client):
    before = client.get("/api/batches/BL-0003/metrics").json()
    assert before["reference_batch_id"] == "BL-0001"
    answer = client.put("/api/batches/BL-0002/reference")
    assert answer.status_code == 200 and answer.json() == {"reference_batch_id": "BL-0002"}
    rows = client.get("/api/batches").json()["batches"]
    assert [row["batch_id"] for row in rows if row["is_reference"]] == ["BL-0002"]
    after = client.get("/api/batches/BL-0003/metrics").json()
    assert after["reference_batch_id"] == "BL-0002"
    assert after["metrics"][0]["reference"]["value"] != before["metrics"][0]["reference"]["value"]
    assert client.get("/api/batches/BL-0002/metrics").json()["findings"] == []
    [entry] = [item for item in fake.audit_log if item["action"] == "batchlens.batch.reference_set"]
    assert (entry["username"], entry["subject"]) == ("engineer", "BL-0002")
    assert entry["detail"] == {"previous": "BL-0001"}
    assert client.put("/api/batches/BL-9999/reference").status_code == 404
    # Asking again changes nothing and is not audited twice.
    assert client.put("/api/batches/BL-0002/reference").status_code == 200
    assert len(fake.audit_log) == 1


def test_seeding_again_leaves_a_corrected_batch_alone_unless_asked_to_reset(seeded, client):
    client.patch(URL, json=correction())
    client.put("/api/batches/BL-0002/reference")
    corrected = seeded.batches.get("BL-0005")
    assert seed_demo(seeded.batches) == []  # nothing new to load
    assert seeded.batches.get("BL-0005") == corrected
    assert seeded.batches.reference().batch.batch_id == "BL-0002"
    assert len(seed_demo(seeded.batches, reset=True)) == 5
    assert seeded.batches.get("BL-0005") == BAD
    assert seeded.batches.reference().batch.batch_id == "BL-0001"
    # The history of what people changed is not erased with the data.
    assert len(client.get("/api/batches/BL-0005").json()["corrections"]) == 1


def test_seeding_replaces_batches_made_by_an_older_generator(seeded, client):
    import dataclasses

    # A database seeded before the generator changed: the same batch, an older provenance.
    stale = dataclasses.replace(
        BAD,
        batch=dataclasses.replace(BAD.batch, provenance="synthetic-generator/1 seed=105"),
        pools=(),
    )
    seeded.batches.save(stale)
    assert seeded.batches.get("BL-0005").pools == ()
    assert seed_demo(seeded.batches) == ["BL-0005"]
    assert seeded.batches.get("BL-0005") == BAD


# Found by the second review -------------------------------------------------------------------


def test_reloading_a_stale_batch_keeps_one_reference_and_an_honest_history(seeded, client, caplog):
    import dataclasses

    client.patch(URL, json=correction())
    client.put("/api/batches/BL-0003/reference")
    # The generator changed: the reference of the demo and the corrected batch are both stale.
    for batch_id in ("BL-0001", "BL-0005"):
        record = seeded.batches.get(batch_id)
        seeded.batches.save(
            dataclasses.replace(
                record,
                batch=dataclasses.replace(record.batch, provenance="synthetic-generator/1 seed=0"),
            )
        )
    with caplog.at_level("WARNING"):
        assert seed_demo(seeded.batches) == ["BL-0001", "BL-0005"]
    # The person's choice of reference stands, and there is exactly one.
    rows = client.get("/api/batches").json()["batches"]
    assert [row["batch_id"] for row in rows if row["is_reference"]] == ["BL-0003"]
    assert client.get("/api/batches/BL-0002/metrics").json()["reference_batch_id"] == "BL-0003"
    # The corrected time was replaced by the generated one, and nothing pretends otherwise: the
    # sample is no longer marked corrected, the history still says what was done, and the log
    # names what was undone.
    samples = client.get("/api/batches/BL-0005/samples").json()["samples"]
    assert not any(sample["corrected"] for sample in samples)
    assert len(client.get("/api/batches/BL-0005").json()["corrections"]) == 1
    assert "BL-0005-S09" in caplog.text and "undone" in caplog.text


def test_a_correction_to_the_time_it_already_has_is_refused(seeded, fake, client):
    same = client.patch(URL, json=correction(collected_at=S09.collected_at.isoformat()))
    assert same.status_code == 422
    assert fake.audit_log == [] and client.get("/api/batches/BL-0005").json()["corrections"] == []


def test_a_sample_that_vanished_between_the_check_and_the_write_is_a_404(seeded, client):
    with pytest.raises(LookupError):
        seeded.batches.store.correct_sample_time("BL-0005", "BL-0005-S99", RIGHT_TIME, "why", "me")


def test_an_as_of_view_does_not_show_later_corrections_or_a_phase_end_to_come(seeded, client):
    client.patch(URL, json=correction())
    culture = BAD.phase("production_culture")
    as_of = (culture.start + timedelta(days=3)).isoformat()
    # The correction was made today, long after day 3 of the batch.
    assert client.get("/api/batches/BL-0005", params={"as_of": as_of}).json()["corrections"] == []
    trends = client.get("/api/batches/BL-0005/trends", params={"as_of": as_of}).json()
    assert trends["end"] is None and trends["start"] is not None
    harvest = metric_as_of(client, "BL-0005", "harvest_mass", as_of)
    assert harvest["reasons"][0]["code"] == "phase_not_ended"
    assert "phase_end" not in harvest["reasons"][0]["values"]
    before = (culture.start - timedelta(days=1)).isoformat()
    trends = client.get("/api/batches/BL-0005/trends", params={"as_of": before}).json()
    assert trends["start"] is None and trends["end"] is None


def metric_as_of(client, batch_id: str, name: str, as_of: str) -> dict:
    found = client.get(f"/api/batches/{batch_id}/metrics", params={"as_of": as_of}).json()[
        "metrics"
    ]
    return next(item for item in found if item["metric"] == name)
