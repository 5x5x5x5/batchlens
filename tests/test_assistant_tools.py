"""The two read-only tools BatchLens offers PlantCraft's assistant. PlantCraft calls them as
the person who asks; they answer what the pages show, as data with its limits stated."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from plantcraft_sdk.contributes import contributions

from batchlens.demo.generator import demo_campaign
from tests.conftest import client_for

ROOT = Path(__file__).resolve().parents[1]
LIST, FINDINGS = "/api/assistant/tools/list_batches", "/api/assistant/tools/batch_findings"


def test_the_manifest_declares_the_tools_the_app_serves():
    manifest = tomllib.loads((ROOT / "app.toml").read_text(encoding="utf-8"))
    declared = manifest["contributes"]["assistant"]["tools"]
    assert [tool["id"] for tool in declared] == ["list_batches", "batch_findings"]
    assert [arg["key"] for arg in declared[1]["args"]] == ["batch"]
    for tool in declared:
        assert "synthetic" in tool["description"].lower()
    assert "never a cause" in declared[1]["description"]
    assert contributions(manifest)  # the SDK accepts the declaration


def test_list_batches_answers_the_batches_and_which_is_the_reference(seeded, client):
    answer = client.post(LIST, json={})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert "synthetic" in body["note"].lower() and "not instructions" in body["note"]
    assert [b["batch"] for b in body["batches"]] == [
        "BL-0001",
        "BL-0002",
        "BL-0003",
        "BL-0004",
        "BL-0005",
        "BL-0006",
    ]
    assert [b["reference"] for b in body["batches"]] == [True, *[False] * 5]
    assert body["batches"][0]["ref"] == "/batchlens/batches/BL-0001"
    assert body["batches"][0]["bioreactor"] == "BR-2001"


def test_batch_findings_answers_what_the_page_shows_and_attributes_no_cause(seeded, fake, client):
    answer = client.post(FINDINGS, json={"batch": "BL-0003"})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    page = client.get("/api/batches/BL-0003/metrics").json()
    assert body["batch"] == "BL-0003" and body["reference_batch"] == "BL-0001"
    assert body["url"] == "/batchlens/batches/BL-0003"
    assert "no cause" in body["note"].lower() and "synthetic" in body["note"].lower()
    # The same numbers as the page, each with unit, status and reasons.
    by_metric = {m["metric"]: m for m in body["metrics"]}
    for item in page["metrics"]:
        mine = by_metric[item["metric"]]
        assert (mine["value"], mine["unit"], mine["status"]) == (
            item["value"],
            item["unit"],
            item["status"],
        )
        assert mine["reference_value"] == (item["reference"] or {}).get("value")
    titer = body["findings"][0]
    assert titer["finding"] == "titer_divergence" and titer["found"] is True
    assert titer["culture_day"] == pytest.approx(page["findings"][0]["observation"]["value"])
    assert titer["consequence"]["difference"] == page["findings"][0]["consequence"]["difference"]
    assert titer["cause"] == "not attributed"
    assert [f["found"] for f in body["findings"]] == [True, *[False] * 8]
    assert [s["step"] for s in body["purification"]][:2] == [
        "protein_a_capture",
        "viral_inactivation",
    ]
    assert body["harvest_to_drug_substance_percent"] == page["downstream"]["overall"]["value"]
    # The app records that the assistant read it.
    [entry] = [
        item for item in fake.audit_log if item["action"] == "batchlens.assistant.batch_findings"
    ]
    assert (entry["username"], entry["subject"]) == ("engineer", "BL-0003")


def test_a_flagged_batch_is_answered_with_its_flags_not_with_numbers(seeded, client):
    body = client.post(FINDINGS, json={"batch": "BL-0005"}).json()
    ivcd = next(m for m in body["metrics"] if m["metric"] == "ivcd")
    assert (ivcd["value"], ivcd["status"]) == (None, "invalid")
    assert ivcd["reasons"][0]["code"] == "times_not_increasing"
    assert body["findings"][0]["found"] is None  # could not be compared
    assert body["findings"][0]["status"] == "invalid"


def test_a_batch_that_is_not_there_is_said_so_without_an_error(seeded, client):
    answer = client.post(FINDINGS, json={"batch": "BL-9999"})
    assert answer.status_code == 200
    body = answer.json()
    assert body["found"] is False and "list_batches" in body["empty"]
    assert "metrics" not in body
    # The batch may come as the model writes it.
    assert client.post(FINDINGS, json={"batch": " bl-0003 "}).json()["batch"] == "BL-0003"
    assert client.post(FINDINGS, json={}).status_code == 422
    assert client.post(FINDINGS, json={"batch": "x" * 500}).status_code == 422


def test_the_tools_answer_people_who_may_open_the_app_and_nobody_else(seeded, fake):
    with client_for(seeded, fake, "operator") as viewer:
        assert viewer.post(LIST, json={}).status_code == 200
        assert viewer.post(FINDINGS, json={"batch": "BL-0001"}).status_code == 200
    with client_for(seeded, fake, "outsider") as outsider:
        assert outsider.post(LIST, json={}).status_code == 403
    with client_for(seeded, fake, None) as anonymous:
        assert anonymous.post(FINDINGS, json={"batch": "BL-0001"}).status_code == 401


def test_no_tool_answer_carries_the_ground_truth(seeded, client):
    truth = demo_campaign()[1]
    text = client.post(LIST, json={}).text
    for batch_id in truth:
        text += client.post(FINDINGS, json={"batch": batch_id}).text
    text = text.lower()
    for word in (
        *{item.scenario for item in truth.values()},
        "reduced",
        "scenario",
        "fault",
        "truth",
        "shift",
        "label",
        "mis_keyed",
    ):
        assert word not in text, word
