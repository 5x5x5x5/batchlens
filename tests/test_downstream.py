"""The rest of downstream: step yields and cumulative recovery from harvest to drug substance,
and the genealogy of pools (two Protein A cycles merged into one eluate, checked by mass)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from batchlens import calc
from batchlens.analysis.downstream import STEPS, downstream
from batchlens.analysis.metrics import batch_metrics
from batchlens.demo.generator import VOLUME_UNIT, demo_campaign

AT = datetime(2026, 7, 16, tzinfo=UTC)


def mass(metric: str, value: float | None, status: str = "usable", inputs=("p",)) -> calc.Result:
    return calc.Result(metric, value, "g", status, (), tuple(inputs), "pool_mass/1")


# Calculations ----------------------------------------------------------------------------------


def test_a_merge_balances_when_the_parts_add_up_to_the_whole():
    # Two cycle pools of 4,600 g and 4,500 g merged into one pool measured at 9,150 g:
    # 100 * (9150 - 9100) / 9100 = +0.549 %, within the default 3 %.
    result = calc.merge_balance(
        [mass("c1", 4600.0, inputs=("a",)), mass("c2", 4500.0, inputs=("b",))],
        mass("eluate", 9150.0, inputs=("e",)),
    )
    assert (result.metric, result.unit, result.status) == ("merge_balance", "%", "usable")
    assert result.value == pytest.approx(0.549451, rel=1e-5)
    assert result.inputs == ("a", "b", "e")
    assert result.calculation_version == "merge_balance/1"


def test_a_merge_that_gains_or_loses_more_than_the_tolerance_is_suspect():
    # 100 * (9600 - 9100) / 9100 = +5.49 %: more came out of the merge than went in.
    gained = calc.merge_balance([mass("c1", 4600.0), mass("c2", 4500.0)], mass("e", 9600.0))
    assert gained.status == "suspect" and gained.value == pytest.approx(5.494505, rel=1e-6)
    assert gained.reasons == (calc.Reason("outside_merge_tolerance", {"tolerance_percent": 3.0}),)
    lost = calc.merge_balance([mass("c1", 4600.0), mass("c2", 4500.0)], mass("e", 8600.0))
    assert lost.status == "suspect" and lost.value == pytest.approx(-5.494505, rel=1e-6)


def test_a_merge_with_a_part_missing_is_insufficient_never_a_partial_sum():
    missing = mass("c2", None, "insufficient")
    result = calc.merge_balance([mass("c1", 4600.0), missing], mass("e", 9150.0))
    assert (result.status, result.value) == ("insufficient", None)
    assert result.reasons[0].code == "input_not_usable"
    assert calc.merge_balance([], mass("e", 9150.0)).status == "insufficient"
    assert (
        calc.merge_balance([mass("c1", 0.0)], mass("e", 9150.0)).reasons[0].code
        == "zero_denominator"
    )


# The generated train ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def trains():
    observations, truth = demo_campaign()
    made = {}
    for item in observations:
        volume = calc.Online("volume", VOLUME_UNIT, item.online["volume"])
        results = {r.metric: r for r in batch_metrics(item.record, volume)}
        made[item.record.batch.batch_id] = (
            item.record,
            downstream(item.record, results["harvest_mass"]),
        )
    return made, truth


def test_a_batch_runs_through_the_whole_train_in_order(trains):
    record, _ = trains[0]["BL-0001"]
    assert [phase.kind for phase in record.phases] == [
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
    assert all(a.end <= b.start for a, b in zip(record.phases, record.phases[1:]))
    assert len({phase.asset_id for phase in record.phases}) == 10  # each step on its own equipment
    assert [step for step, _, _ in STEPS] == [phase.kind for phase in record.phases[4:]]


def test_step_yields_multiply_to_the_cumulative_recovery(trains):
    record, answer = trains[0]["BL-0001"]
    steps = answer["steps"]
    assert [row["step"] for row in steps] == [step for step, _, _ in STEPS]
    product = 1.0
    for before, row in zip([None, *steps], steps):
        assert row["step_yield"]["status"] == "usable" and 60 < row["step_yield"]["value"] <= 105
        # What goes into a step is what came out of the one before.
        if before is not None:
            assert row["mass_in"]["value"] == before["mass_out"]["value"]
        product *= row["step_yield"]["value"] / 100
        from_load = row["mass_out"]["value"] / steps[0]["mass_in"]["value"]
        assert product == pytest.approx(from_load, rel=1e-9)
    # From harvest to drug substance, in the units and with the inputs of both ends.
    overall = answer["overall"]
    assert overall["metric"] == "harvest_to_drug_substance_recovery" and overall["unit"] == "%"
    assert overall["value"] == pytest.approx(
        100 * steps[-1]["mass_out"]["value"] / 10174.4736, rel=1e-6
    )
    assert 55 < overall["value"] < 80
    assert "BL-0001-drug_substance" in overall["inputs"]
    for row in steps:
        assert row["from_harvest"]["value"] == pytest.approx(
            100 * row["mass_out"]["value"] / 10174.4736, rel=1e-6
        )


def test_the_generated_step_yields_are_the_ones_the_generator_set(trains):
    made, truth = trains
    for batch_id in ("BL-0001", "BL-0002", "BL-0003"):
        _, answer = made[batch_id]
        for row in answer["steps"][1:]:
            true_yield = truth[batch_id].step_yields[row["step"]]
            # Two pool concentrations with 1 % assay noise each: three standard deviations.
            assert row["step_yield"]["value"] == pytest.approx(100 * true_yield, rel=0.045)


def test_the_two_protein_a_cycles_merge_into_the_eluate_and_the_mass_is_checked(trains):
    record, answer = trains[0]["BL-0001"]
    merged = next(pool for pool in record.pools if pool.pool == "protein_a_eluate")
    cycles = [pool for pool in record.pools if pool.pool.startswith("protein_a_eluate_cycle_")]
    assert len(cycles) == 2 and all(c.measured_at <= merged.measured_at for c in cycles)
    assert {(link.from_pool_id, link.to_pool_id) for link in record.links} >= {
        (cycle.measurement_id, merged.measurement_id) for cycle in cycles
    }
    genealogy = answer["genealogy"]
    eluate = next(node for node in genealogy if node["pool"] == "protein_a_eluate")
    assert sorted(eluate["sources"]) == sorted(c.measurement_id for c in cycles)
    assert eluate["merge_balance"]["status"] == "usable"
    assert abs(eluate["merge_balance"]["value"]) < 3
    # Every other pool comes from exactly the pool before it; the first has no source.
    by_pool = {node["pool"]: node for node in genealogy}
    assert by_pool["protein_a_load"]["sources"] == []
    assert by_pool["drug_substance"]["sources"] == ["BL-0001-viral_filtrate"]
    assert by_pool["drug_substance"]["merge_balance"] is None  # one source: a step, not a merge


def test_the_batch_with_the_poor_capture_step_loses_it_once_not_at_every_step(trains):
    made, _ = trains
    normal, poor = made["BL-0001"][1], made["BL-0004"][1]
    assert poor["steps"][0]["step_yield"]["value"] < normal["steps"][0]["step_yield"]["value"] - 15
    for a, b in zip(normal["steps"][1:], poor["steps"][1:]):
        assert abs(a["step_yield"]["value"] - b["step_yield"]["value"]) < 5
    assert poor["overall"]["value"] < normal["overall"]["value"] - 10


def test_without_a_harvest_mass_the_steps_are_still_answered_and_the_overall_is_not(trains):
    _, answer = trains[0]["BL-0005"]  # the hole in the historian: no harvest mass
    assert answer["overall"]["status"] == "insufficient" and answer["overall"]["value"] is None
    assert all(row["step_yield"]["status"] == "usable" for row in answer["steps"])
    assert all(row["from_harvest"]["value"] is None for row in answer["steps"])


def test_downstream_as_of_stops_where_the_measurements_stop():
    observations, _ = demo_campaign()
    record = observations[0].record
    volume = calc.Online("volume", VOLUME_UNIT, observations[0].online["volume"])
    cex = next(pool for pool in record.pools if pool.pool == "cation_exchange_pool")
    as_of = cex.result_available_at + timedelta(minutes=1)
    harvest = {r.metric: r for r in batch_metrics(record, volume, as_of=as_of)}["harvest_mass"]
    answer = downstream(record, harvest, as_of=as_of)
    statuses = {row["step"]: row["step_yield"]["status"] for row in answer["steps"]}
    assert statuses["cation_exchange"] == "usable"
    assert statuses["anion_exchange"] == statuses["ufdf"] == "insufficient"
    assert answer["overall"]["status"] == "insufficient"
    # Pools not yet measured are not in the genealogy at all.
    assert "drug_substance" not in {node["pool"] for node in answer["genealogy"]}


# The API ---------------------------------------------------------------------------------------


def test_the_metrics_route_answers_the_train_beside_the_reference(seeded, client):
    answer = client.get("/api/batches/BL-0004/metrics").json()["downstream"]
    capture = answer["steps"][0]
    assert capture["step"] == "protein_a_capture"
    assert capture["yield_difference"] == pytest.approx(
        capture["step_yield"]["value"] - capture["reference_yield"]
    )
    assert capture["yield_difference"] < -15
    assert all(abs(row["yield_difference"]) < 5 for row in answer["steps"][1:])
    assert answer["overall"]["status"] == "usable"
    assert answer["overall_reference"] > answer["overall"]["value"] + 10
    assert len(answer["genealogy"]) == 9
    # The reference batch has no reference: its own numbers only.
    own = client.get("/api/batches/BL-0001/metrics").json()["downstream"]
    assert "reference_yield" not in own["steps"][0] and own["overall_reference"] is None


def test_the_train_without_the_bioreactor_still_has_its_step_yields(tmp_path):
    from batchlens.demo.seed import seed_demo
    from tests.conftest import client_for, make_runtime
    from tests.plant import make_fake

    fake = make_fake(bioprocess=False)
    runtime = make_runtime(tmp_path, fake)
    try:
        seed_demo(runtime.batches)
        with client_for(runtime, fake) as client:
            answer = client.get("/api/batches/BL-0002/metrics").json()["downstream"]
            assert all(row["step_yield"]["status"] == "usable" for row in answer["steps"])
            assert answer["overall"]["status"] == "insufficient"
            assert answer["overall"]["reasons"][0]["code"] == "input_not_usable"
    finally:
        runtime.shutdown()


def test_a_pool_measured_twice_under_one_name_keeps_each_measurements_own_mass():
    import dataclasses

    from batchlens.batches.models import PoolLink

    observations, _ = demo_campaign()
    record = observations[0].record
    eluate = next(pool for pool in record.pools if pool.pool == "protein_a_eluate")
    again = dataclasses.replace(
        eluate,
        measurement_id="BL-0001-protein_a_eluate-again",
        volume=eluate.volume / 2,
        measured_at=eluate.measured_at + timedelta(minutes=5),
    )
    twice = dataclasses.replace(record, pools=(*record.pools, again))
    harvest = mass("harvest_mass", 10174.4736)
    by_id = {node["measurement_id"]: node for node in downstream(twice, harvest)["genealogy"]}
    first, second = by_id[eluate.measurement_id]["mass"], by_id[again.measurement_id]["mass"]
    assert second["value"] == pytest.approx(first["value"] / 2)
    assert second["inputs"] == [again.measurement_id]
    # A link to a pool that is not there is ignored, not an error.
    stray = PoolLink("x", "BL-0001", "no-such-pool", eluate.measurement_id, "p")
    answer = downstream(dataclasses.replace(record, links=(*record.links, stray)), harvest)
    assert (
        "no-such-pool"
        not in next(n for n in answer["genealogy"] if n["pool"] == "protein_a_eluate")["sources"]
    )


# Findings for the later steps ------------------------------------------------------------------


def later_steps(answer):
    return {f["finding"]: f for f in answer["findings"]}


def test_a_later_step_that_yields_far_less_than_the_reference_is_a_finding():
    from batchlens.demo.generator import CAMPAIGN_START, Scenario, generate

    poor, truth = generate(
        Scenario("X-1", CAMPAIGN_START, downstream_yields={"cation_exchange": 0.72}), 31
    )
    good, _ = generate(Scenario("X-0", CAMPAIGN_START), 32)
    assert truth.step_yields["cation_exchange"] == pytest.approx(0.72, rel=0.02)

    def harvest(item):
        volume = calc.Online("volume", VOLUME_UNIT, item.online["volume"])
        return {r.metric: r for r in batch_metrics(item.record, volume)}["harvest_mass"]

    answer = downstream(poor.record, harvest(poor), reference=(good.record, harvest(good)))
    found = later_steps(answer)
    assert list(found) == [
        "viral_inactivation_yield_shortfall",
        "cation_exchange_yield_shortfall",
        "anion_exchange_yield_shortfall",
        "viral_filtration_yield_shortfall",
        "ufdf_yield_shortfall",
    ]
    cex = found["cation_exchange_yield_shortfall"]
    assert cex["observation"]["status"] == "usable" and 12 < cex["observation"]["value"] < 24
    assert cex["observation"]["reasons"][0]["code"] == "below_reference"
    # The consequence: what came out of that step, against the reference.
    assert cex["consequence"]["metric"] == "cation_exchange_pool_mass"
    assert cex["consequence"]["difference"] < 0 and cex["cause"] is None and cex["evidence"] == []
    # The steps around it are within the tolerance: the loss is located in one step.
    for name in (
        "viral_inactivation_yield_shortfall",
        "anion_exchange_yield_shortfall",
        "ufdf_yield_shortfall",
    ):
        assert found[name]["observation"]["reasons"][0]["code"] == "within_reference"
        assert found[name]["consequence"] is None
    # Each step also carries the comparison in its own row.
    row = next(r for r in answer["steps"] if r["step"] == "cation_exchange")
    assert row["yield_difference"] == pytest.approx(-cex["observation"]["value"])


def test_without_a_reference_there_are_no_step_findings(trains):
    assert trains[0]["BL-0001"][1]["findings"] == []
