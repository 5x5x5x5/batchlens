"""The synthetic generator: deterministic, internally consistent, and its ground truth kept
apart from what the app may see."""

from __future__ import annotations

import ast
import dataclasses
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from batchlens import calc
from batchlens.analysis.metrics import batch_metrics
from batchlens.demo.generator import (
    BIOREACTOR,
    VOLUME_UNIT,
    Scenario,
    demo_campaign,
    generate,
)

SRC = Path(__file__).resolve().parents[1] / "src" / "batchlens"


def metrics(observations, as_of=None) -> dict[str, calc.Result]:
    volume = calc.Online("volume", VOLUME_UNIT, observations.online["volume"])
    return {r.metric: r for r in batch_metrics(observations.record, volume, as_of=as_of)}


@pytest.fixture(scope="module")
def campaign():
    batches, truth = demo_campaign()
    return {o.record.batch.batch_id: o for o in batches}, truth


def test_the_same_scenario_and_seed_give_identical_output(campaign):
    scenario = Scenario("BL-0001", demo_campaign()[0][0].record.phases[0].start)
    assert generate(scenario, 7) == generate(scenario, 7)
    assert demo_campaign() == demo_campaign()


def test_different_seeds_differ():
    scenario = Scenario("BL-0001", demo_campaign()[0][0].record.phases[0].start)
    first, second = generate(scenario, 7)[0], generate(scenario, 8)[0]
    assert first.record.results != second.record.results
    assert first.online != second.online


def test_four_batches_run_one_after_another_on_the_same_bioreactor(campaign):
    batches, _ = campaign
    assert sorted(batches) == ["BL-0001", "BL-0002", "BL-0003", "BL-0004"]
    windows = []
    for observations in batches.values():
        kinds = [phase.kind for phase in observations.record.phases]
        assert kinds == ["production_culture", "harvest", "protein_a_capture"]
        culture = observations.record.phases[0]
        assert culture.asset_id == BIOREACTOR
        windows.append((culture.start, culture.end))
        # The online data of a batch sits inside its own production window.
        for points in observations.online.values():
            assert culture.start <= points[0][0] and points[-1][0] <= culture.end
    windows.sort()
    assert all(end < start for (_, end), (start, _) in zip(windows, windows[1:]))
    assert [o.record.batch.is_reference for o in batches.values()] == [True, False, False, False]


def test_a_batch_has_roughly_daily_samples_with_each_result_available_later(campaign):
    batches, _ = campaign
    record = batches["BL-0001"].record
    assert len(record.samples) == 15
    gaps = [b.collected_at - a.collected_at for a, b in zip(record.samples, record.samples[1:])]
    assert len(set(gaps)) > 5  # irregular times
    assert max(gaps) < timedelta(days=1.5)
    collected = {sample.sample_id: sample.collected_at for sample in record.samples}
    by_analyte: dict[str, list[timedelta]] = {}
    for result in record.results:
        delay = result.result_available_at - collected[result.sample_id]
        by_analyte.setdefault(result.analyte, []).append(delay)
    assert sorted(by_analyte) == ["glucose", "lactate", "titer", "vcd", "viability"]
    assert max(by_analyte["vcd"]) < timedelta(hours=4) < min(by_analyte["titer"])
    assert all(delay > timedelta(0) for delays in by_analyte.values() for delay in delays)
    assert {pool.pool for pool in record.pools} == {"protein_a_load", "protein_a_eluate"}


def test_the_calculations_recover_the_generators_own_parameters(campaign):
    batches, truth = campaign
    for batch_id, observations in batches.items():
        found, expected = metrics(observations), truth[batch_id]
        assert all(result.status == "usable" for result in found.values()), batch_id
        # Tolerances are three standard deviations of the generator's assay noise
        # (docs/scientific-assumptions.md): 3 % per cell count averaged over 15 samples, and
        # 2 % on the single final titer that harvest mass, qP and the yield all rest on.
        assert found["ivcd"].value == pytest.approx(expected.ivcd, rel=0.03)
        assert found["qp"].value == pytest.approx(expected.qp_culture_average, rel=0.07)
        assert found["harvest_mass"].value == pytest.approx(expected.harvest_mass, rel=0.06)
        assert found["harvest_to_load_yield"].value == pytest.approx(
            100 * expected.harvest_to_load_yield, rel=0.07
        )
        assert found["protein_a_recovery"].value == pytest.approx(
            100 * expected.protein_a_recovery, rel=0.045
        )


def test_the_reduced_productivity_batch_has_lower_qp_than_the_normal_ones(campaign):
    batches, truth = campaign
    assert truth["BL-0003"].scenario == "reduced_culture_productivity"
    qp = {batch_id: metrics(o)["qp"].value for batch_id, o in batches.items()}
    assert qp["BL-0003"] < 0.9 * min(qp["BL-0001"], qp["BL-0002"])


def test_the_reduced_recovery_batch_has_a_normal_harvest_and_less_in_the_eluate(campaign):
    batches, truth = campaign
    assert truth["BL-0004"].scenario == "reduced_protein_a_recovery"
    found = {batch_id: metrics(o) for batch_id, o in batches.items()}
    recovery = {b: m["protein_a_recovery"].value for b, m in found.items()}
    assert recovery["BL-0004"] < min(recovery["BL-0001"], recovery["BL-0002"]) - 10
    harvest = {b: m["harvest_mass"].value for b, m in found.items()}
    assert harvest["BL-0004"] == pytest.approx(harvest["BL-0001"], rel=0.15)
    assert harvest["BL-0004"] > harvest["BL-0003"]


def test_what_the_app_sees_carries_no_ground_truth(campaign):
    batches, truth = campaign
    for batch_id, observations in batches.items():
        seen = repr(dataclasses.asdict(observations.record)).lower()
        for word in ("reduced", "normal", "fault", "scenario", truth[batch_id].scenario):
            assert word not in seen, (batch_id, word)
        assert all("synthetic-generator" in row.provenance for row in observations.record.results)


def test_a_result_not_yet_available_is_not_used_and_the_metric_says_why(campaign):
    batches, _ = campaign
    observations = batches["BL-0001"]
    culture = observations.record.phases[0]
    early = metrics(observations, as_of=culture.end + timedelta(hours=1))
    assert early["harvest_mass"].status == "insufficient"
    assert early["harvest_mass"].reasons[0].code == "result_not_yet_available"
    assert early["qp"].value is not None and "result_not_yet_available" in [
        reason.code for reason in early["qp"].reasons
    ]
    assert early["protein_a_recovery"].status == "insufficient"


def test_a_result_marked_invalid_is_left_out(campaign):
    batches, _ = campaign
    record = batches["BL-0001"].record
    last_titer = [r for r in record.results if r.analyte == "titer"][-1]
    spoiled = dataclasses.replace(
        record,
        results=tuple(
            dataclasses.replace(r, validity="invalid") if r is last_titer else r
            for r in record.results
        ),
    )
    volume = calc.Online("volume", VOLUME_UNIT, batches["BL-0001"].online["volume"])
    found = {r.metric: r for r in batch_metrics(spoiled, volume)}
    assert found["harvest_mass"].status == "insufficient"
    assert last_titer.result_id not in found["qp"].inputs


@pytest.mark.parametrize("package", ["calc", "demo/generator.py"])
def test_calc_and_the_generator_use_the_standard_library_only(package):
    path = SRC / package
    for file in [path] if path.is_file() else sorted(path.rglob("*.py")):
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                top = name.split(".")[0]
                assert top in sys.stdlib_module_names or top == "batchlens", (file.name, name)
                if package == "calc":
                    assert top != "batchlens" or name.startswith("batchlens.calc"), (
                        file.name,
                        name,
                    )
