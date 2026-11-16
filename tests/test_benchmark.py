"""The benchmark: the findings scored against the generator's ground truth over many seeded
batches. It is the one place outside the tests that reads the ground truth."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from batchlens.benchmark.report import render
from batchlens.benchmark.run import run
from batchlens.cli import main

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def small():
    return run(batches=2, references=2)


def test_the_same_run_gives_the_same_numbers(small):
    assert run(batches=2, references=2) == small
    assert json.loads(json.dumps(small)) == small  # plain data


def test_it_counts_what_it_ran(small):
    counts = small["counts"]
    # Per seed: 1 normal, 9 reduced productivity (3 onset days x 3 factors), 3 reduced recovery,
    # 3 with a poor later step, 3 badly recorded; times 2 seeds, each compared with 2
    # reference batches.
    assert counts == {
        "references": 2,
        "normal": 2,
        "reduced_productivity": 18,
        "reduced_recovery": 6,
        "reduced_step_yield": 6,
        "bad_records": 6,
        "comparisons": 76,
    }


def test_badly_recorded_batches_never_get_a_number_they_should_not(small):
    bad = small["bad_records"]
    assert bad["mis_keyed_sample"]["batches"] == 4
    assert bad["mis_keyed_sample"]["culture_metrics_answered"] == 0
    assert bad["mis_keyed_sample"]["titer_findings_answered"] == 0
    assert bad["historian_gap"]["batches"] == 4
    assert bad["historian_gap"]["harvest_mass_answered"] == 0
    assert bad["historian_gap"]["yield_findings_answered"] == 0
    # What rests on good records is still answered, every time.
    assert bad["protein_a_recovery_answered"] == bad["batches"] == 6


def test_the_titer_finding_is_scored_by_tolerance(small):
    rows = {row["tolerance_percent"]: row for row in small["titer_divergence"]}
    assert sorted(rows) == [5.0, 10.0, 15.0, 20.0]
    for row in rows.values():
        assert (
            row["without_culture_change"]["comparisons"] == 28
        )  # every batch with a normal culture
        assert 0 <= row["without_culture_change"]["found"] <= 16
        assert row["with_culture_change"]["comparisons"] == 36
        assert 0 <= row["with_culture_change"]["found"] <= 36
        by_factor = {item["qp_factor"]: item for item in row["by_qp_factor"]}
        assert sorted(by_factor) == [0.55, 0.7, 0.85]
        assert sum(item["comparisons"] for item in by_factor.values()) == 36
    # A tighter tolerance never finds fewer of the real changes.
    found = [rows[t]["with_culture_change"]["found"] for t in (5.0, 10.0, 15.0, 20.0)]
    assert found == sorted(found, reverse=True)
    # The strongest change is found at the default tolerance, after it began, never before.
    strong = next(i for i in rows[15.0]["by_qp_factor"] if i["qp_factor"] == 0.55)
    assert strong["found"] == strong["comparisons"]
    assert strong["delay_days"]["min"] >= 0 and strong["found_before_onset"] == 0


def test_the_recovery_findings_are_scored_by_tolerance(small):
    rows = {row["tolerance_points"]: row for row in small["recovery_shortfall"]}
    assert sorted(rows) == [5.0, 10.0, 15.0]
    default = rows[10.0]
    by_level = {item["recovery"]: item for item in default["protein_a_by_true_recovery"]}
    assert sorted(by_level) == [0.74, 0.8, 0.86]
    assert by_level[0.74]["found"] == by_level[0.74]["comparisons"] == 4
    assert default["protein_a_without_loss"]["comparisons"] == 52
    # The yield never truly changes in the generator: everything found there is a false alarm.
    assert default["yield_false_alarms"]["comparisons"] == 64  # every batch whose records are good
    assert rows[5.0]["yield_false_alarms"]["found"] >= rows[15.0]["yield_false_alarms"]["found"]


def test_the_later_steps_are_scored_too(small):
    rows = {row["tolerance_points"]: row for row in small["later_step_shortfall"]}
    assert sorted(rows) == [5.0, 10.0, 15.0]
    default = rows[10.0]
    # 6 batches with one poor step (three sizes of loss), each against 2 references.
    by_loss = {item["yield_multiplier"]: item for item in default["by_yield_multiplier"]}
    assert sorted(by_loss) == [0.75, 0.85, 0.92]
    assert sum(item["comparisons"] for item in by_loss.values()) == 12
    assert by_loss[0.75]["found"] == by_loss[0.75]["comparisons"]
    # A finding must name the step that lost, never another one.
    assert default["wrong_step_named"] == 0
    # Every other step of every good-record batch is a chance for a false alarm.
    assert default["false_alarms"]["comparisons"] > 300
    assert rows[5.0]["false_alarms"]["found"] >= rows[15.0]["false_alarms"]["found"]


def test_calculation_errors_against_the_true_values_are_reported(small):
    errors = small["calculation_error_percent"]
    assert sorted(errors) == [
        "harvest_mass",
        "harvest_to_load_yield",
        "inoculation_density",
        "ivcd",
        "protein_a_recovery",
        "qp",
        "seed_n1_growth_rate",
        "seed_n2_growth_rate",
    ]
    for item in errors.values():
        assert item["batches"] == 32  # every batch whose records are good
        assert 0 <= item["mean_abs"] <= item["max_abs"] < 15


def test_the_report_states_its_limits_and_every_table(small):
    text = render(small)
    assert text.startswith("# Verification report")
    for part in (
        "synthetic",
        "same generator",
        "## Badly recorded batches",
        "## Titer divergence",
        "## Step recovery shortfall",
        "## Later purification steps",
        "## Calculation error",
        "## Known limitations",
        "batchlens benchmark",
    ):
        assert part in text, part
    assert "| 15 %" in text and "| 10 points" in text


def test_the_command_line_writes_the_report(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(logging.root, "handlers", [])
    out = tmp_path / "report.md"
    assert main(["benchmark", "--batches", "1", "--references", "1", "--out", str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["comparisons"] == 19
    assert out.read_text(encoding="utf-8").startswith("# Verification report")


@pytest.mark.slow
def test_the_published_report_is_what_the_benchmark_gives_today():
    published = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    assert published == render(run())
