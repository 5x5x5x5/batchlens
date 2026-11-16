"""The synthetic generator: deterministic, internally consistent, and its ground truth kept
apart from what the app may see."""

from __future__ import annotations

import ast
import dataclasses
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from batchlens import calc
from batchlens.analysis.metrics import batch_metrics
from batchlens.demo.generator import (
    BIOREACTOR,
    LOOP_ROLES,
    VOLUME_UNIT,
    Scenario,
    demo_campaign,
    generate,
    loop_series,
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
    scenario = Scenario("BL-0001", demo_campaign()[0][0].record.phase("production_culture").start)
    assert generate(scenario, 7) == generate(scenario, 7)
    assert demo_campaign() == demo_campaign()


def test_different_seeds_differ():
    scenario = Scenario("BL-0001", demo_campaign()[0][0].record.phase("production_culture").start)
    first, second = generate(scenario, 7)[0], generate(scenario, 8)[0]
    assert first.record.results != second.record.results
    assert first.online != second.online


def test_nine_batches_run_one_after_another_on_the_same_bioreactor(campaign):
    batches, _ = campaign
    assert sorted(batches) == [
        "BK-0007",
        "BK-0008",
        "BK-0009",
        *(f"BL-000{n}" for n in range(1, 7)),
    ]
    windows = []
    for observations in batches.values():
        kinds = [phase.kind for phase in observations.record.phases]
        assert kinds[:5] == [
            "seed_n2",
            "seed_n1",
            "production_culture",
            "harvest",
            "protein_a_capture",
        ]
        assert len(kinds) == 10  # then the rest of the train (tests/test_downstream.py)
        culture = observations.record.phase("production_culture")
        assert culture.asset_id == BIOREACTOR
        windows.append((culture.start, culture.end))
        # The online data of a batch sits inside its own production window.
        for points in observations.online.values():
            assert culture.start <= points[0][0] and points[-1][0] <= culture.end
    windows.sort()
    assert all(end < start for (_, end), (start, _) in zip(windows, windows[1:]))
    assert [o.record.batch.is_reference for o in batches.values()] == [
        *[False] * 3,
        True,
        *[False] * 5,
    ]


def test_the_data_problem_batch_has_a_normal_culture_recorded_badly(campaign):
    batches, truth = campaign
    problem, expected = batches["BL-0005"], truth["BL-0005"]
    assert expected.scenario == "data_problem"
    assert (expected.mis_keyed_sample, expected.online_gap_days) == ("BL-0005-S09", (13.4, 14.25))
    # A mis-keyed collection time: sample 9 carries sample 8's instant.
    times = {sample.sample_id: sample.collected_at for sample in problem.record.samples}
    assert times["BL-0005-S09"] == times["BL-0005-S08"]
    assert len(set(times.values())) == len(times) - 1
    # A hole in the historian over the end of the culture, where the harvest sample sits.
    culture = problem.record.phase("production_culture")
    for points in problem.online.values():
        assert max(moment for moment, _ in points) < culture.start + timedelta(days=13.4)
    assert times["BL-0005-S15"] > culture.start + timedelta(days=13.4)
    # The assay values themselves are those of a normal batch.
    titers = [r.value for r in problem.record.results if r.analyte == "titer"]
    assert 4.5 < max(titers) < 6.5


def test_the_calculations_refuse_the_badly_recorded_batch_instead_of_answering(campaign):
    batches, _ = campaign
    found = metrics(batches["BL-0005"])
    assert (found["ivcd"].status, found["ivcd"].value) == ("invalid", None)
    assert found["ivcd"].reasons[0].code == "times_not_increasing"
    assert (found["qp"].status, found["qp"].value) == ("invalid", None)
    assert (found["harvest_mass"].status, found["harvest_mass"].value) == ("insufficient", None)
    assert found["harvest_mass"].reasons[0].code == "no_volume_near_sample"
    assert found["harvest_to_load_yield"].status == "insufficient"
    # What does not depend on the bad records is still answered.
    assert found["protein_a_recovery"].status == "usable"
    assert found["protein_a_load_mass"].status == found["protein_a_eluate_mass"].status == "usable"


def test_two_titers_recorded_at_one_instant_are_invalid_not_silently_merged():
    at = datetime(2026, 7, 1, tzinfo=UTC)
    cells = [
        calc.Measurement(f"v{i}", at + timedelta(days=i), 1.0 + i, "1e6 cells/mL", at)
        for i in range(3)
    ]
    titers = [
        calc.Measurement("t0", at, 0.0, "g/L", at),
        calc.Measurement("t1", at + timedelta(days=2), 0.5, "g/L", at),
        calc.Measurement("t1-again", at + timedelta(days=2), 0.9, "g/L", at),
    ]
    result = calc.specific_productivity(cells, titers)
    assert (result.status, result.value) == ("invalid", None)
    assert [reason.code for reason in result.reasons] == ["times_not_increasing"]


def test_a_batch_has_roughly_daily_samples_with_each_result_available_later(campaign):
    batches, _ = campaign
    record = batches["BL-0001"].record
    culture = record.phase("production_culture")
    samples = [sample for sample in record.samples if sample.phase_id == culture.phase_id]
    assert len(samples) == 15
    gaps = [b.collected_at - a.collected_at for a, b in zip(samples, samples[1:])]
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
    assert {pool.pool for pool in record.pools} >= {"protein_a_load", "protein_a_eluate"}


def test_the_calculations_recover_the_generators_own_parameters(campaign):
    batches, truth = campaign
    for batch_id, observations in batches.items():
        if truth[batch_id].scenario == "data_problem":
            continue  # its numbers are not meant to be recovered: see the tests below
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


def test_a_batch_begins_with_two_seed_passages_whose_growth_rates_are_recovered(campaign):
    batches, truth = campaign
    for batch_id, observations in batches.items():
        record, found = observations.record, metrics(observations)
        n2, n1, culture = (record.phase(k) for k in ("seed_n2", "seed_n1", "production_culture"))
        assert (n2.asset_id, n1.asset_id) == ("BR-1001", "BR-1002")
        assert n2.end == n1.start and n1.end == culture.start  # moved on at once
        for kind in ("seed_n2", "seed_n1"):
            rate = found[f"{kind}_growth_rate"]
            # Two counts with 3 % noise each, three days apart: about 0.014 per day, one sigma.
            assert rate.status == "usable" and rate.unit == "1/day"
            assert rate.value == pytest.approx(truth[batch_id].seed_growth_rates[kind], abs=0.05)
            assert all(
                result_id.startswith(f"{batch_id}-{kind[-2:].upper()}-")
                for result_id in rate.inputs
            )
        # Every demo batch but the low-inoculum one was seeded at the target density.
        target = (
            0.5 if truth[batch_id].scenario != "low_inoculum" else pytest.approx(0.19, abs=0.01)
        )
        assert truth[batch_id].inoculation_density == target
        assert found["inoculation_density"].value == pytest.approx(
            truth[batch_id].inoculation_density * 1.03, rel=0.1
        )


def test_a_slow_last_passage_starts_the_culture_with_fewer_cells_not_less_per_cell(campaign):
    batches, truth = campaign
    start = batches["BL-0001"].record.phase("production_culture").start
    low, low_truth = generate(Scenario("BL-0001", start, n1_growth_factor=0.4), 101)
    normal, normal_truth = batches["BL-0001"], truth["BL-0001"]
    found, usual = metrics(low), metrics(normal)
    # The cause is in the seed records: the N-1 passage grew at well under half the rate.
    assert found["seed_n1_growth_rate"].value < 0.5 * usual["seed_n1_growth_rate"].value
    assert found["seed_n2_growth_rate"].value == usual["seed_n2_growth_rate"].value
    # All of N-1 held too few cells for the target, so the culture began below it.
    assert low_truth.inoculation_density < 0.25
    assert found["inoculation_density"].value == pytest.approx(
        low_truth.inoculation_density, rel=0.1
    )
    # Fewer cell-days and less product, at the same productivity per cell.
    assert found["ivcd"].value < 0.93 * usual["ivcd"].value
    assert found["harvest_mass"].value < 0.93 * usual["harvest_mass"].value
    assert low_truth.qp_nominal == normal_truth.qp_nominal
    assert found["qp"].value == pytest.approx(usual["qp"].value, rel=0.07)


def test_the_seed_train_left_every_other_value_of_a_batch_as_it_was(campaign):
    """Pinned from the generator before the seed train existed (synthetic-generator/2)."""

    record = campaign[0]["BL-0003"].record
    values = {result.result_id: result.value for result in record.results}
    assert (values["BL-0003-S01-vcd"], values["BL-0003-S15-titer"]) == (0.49, 3.658)


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
        for word in (
            "reduced",
            "normal",
            "fault",
            "scenario",
            "problem",
            "mis_keyed",
            "gap",
            truth[batch_id].scenario,
        ):
            assert word not in seen, (batch_id, word)
        assert all("synthetic-generator" in row.provenance for row in observations.record.results)


def test_a_result_not_yet_available_is_not_used_and_the_metric_says_why(campaign):
    batches, _ = campaign
    observations = batches["BL-0001"]
    culture = observations.record.phase("production_culture")
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


def loops_of(batch_id: str, first_day: float, last_day: float):
    batch = next(o for o in demo_campaign()[0] if o.record.batch.batch_id == batch_id)
    start = batch.record.phase("production_culture").start
    since, until = start + timedelta(days=first_day), start + timedelta(days=last_day)
    return batch, start, loop_series(batch, since, until)


def test_a_loops_fast_value_passes_through_every_recorded_value():
    batch, start, loops = loops_of("BL-0001", 3.0, 4.0)
    assert set(loops) == {f"{role}.{part}" for role in LOOP_ROLES for part in ("pv", "sp", "op")}
    for role in LOOP_ROLES:
        fast = dict(loops[f"{role}.pv"])
        recorded = [(m, v) for m, v in batch.online[role] if m in fast]
        assert len(recorded) == 145  # a day of 10-minute values, both ends
        if role == "do":  # the controller's value keeps 15 % of the recorded scatter
            assert all(
                fast[m] == pytest.approx(40.0 + 0.15 * (v - 40.0), abs=1e-3) for m, v in recorded
            )
        else:
            assert all(fast[moment] == value for moment, value in recorded)
        assert len(fast) == 144 * 20 + 1  # one every 30 seconds
        assert all(0 <= value <= 100 for _, value in loops[f"{role}.op"])


def test_any_window_gives_the_same_loop_values():
    _, _, whole = loops_of("BL-0001", 3.0, 4.0)
    _, _, part = loops_of("BL-0001", 3.5, 3.6)
    for key, points in part.items():
        assert points and set(points) <= set(whole[key])


def test_the_temperature_setpoint_makes_the_planned_shift_and_the_others_hold():
    _, _, before = loops_of("BL-0001", 5.0, 5.1)
    _, _, after = loops_of("BL-0001", 7.0, 7.1)
    assert {value for _, value in before["temperature.sp"]} == {36.5}
    assert {value for _, value in after["temperature.sp"]} == {33.0}
    assert {value for _, value in after["ph.sp"]} == {7.0}
    assert {value for _, value in after["do.sp"]} == {40.0}


def test_a_loops_output_answers_the_error_between_setpoint_and_value():
    # More oxygen when dissolved oxygen is below its setpoint than when it is above.
    _, _, loops = loops_of("BL-0001", 10.0, 12.0)
    pairs = list(zip(loops["do.pv"], loops["do.op"]))
    below = [op for (_, pv), (_, op) in pairs if pv < 39.8]
    above = [op for (_, pv), (_, op) in pairs if pv > 40.2]
    assert below and above and sum(below) / len(below) > sum(above) / len(above)


def test_no_loop_value_is_made_across_a_hole_in_the_record():
    # The fifth batch's historian kept nothing from culture day 13.4 on.
    batch, start, loops = loops_of("BL-0005", 13.0, 14.25)
    last = max(moment for moment, _ in loops["ph.pv"])
    assert last < start + timedelta(days=13.4)
    assert last >= batch.online["ph"][-1][0] - timedelta(minutes=10)


def test_the_dissolved_oxygen_loop_holds_its_value_close_to_the_setpoint():
    _, _, loops = loops_of("BL-0001", 10.0, 12.0)
    values = [value for _, value in loops["do.pv"]]
    assert sum(abs(value - 40.0) <= 0.4 for value in values) / len(values) > 0.9
