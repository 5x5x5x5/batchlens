"""Where a batch's titer left the reference batch's, against hand-worked cases.

The rule: pair each titer sample with the reference sample nearest in culture age (within a
window, never interpolated); the divergence is the first sample that is below its reference
by more than the tolerance *and* after which every later paired sample is below too.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from batchlens import calc
from batchlens.calc import Measurement

BATCH_START = datetime(2026, 8, 12, 6, 0, tzinfo=UTC)
REFERENCE_START = datetime(2026, 7, 1, 6, 0, tzinfo=UTC)  # another batch, weeks earlier


def titers(start: datetime, prefix: str, points, *, unit: str = "g/L", late_hours: float = 24):
    return [
        Measurement(
            f"{prefix}@{age}",
            start + timedelta(days=age),
            value,
            unit,
            start + timedelta(days=age, hours=late_hours),
            "HPLC",
        )
        for age, value in points
    ]


# The reference gains 1 g/L a day; samples at culture days 1 to 5.
REFERENCE = titers(REFERENCE_START, "ref", [(1, 1.0), (2, 2.0), (3, 3.0), (4, 4.0), (5, 5.0)])
# Deficits against the nearest reference sample (ages differ by at most 0.1 day = 2.4 h):
#   day 1.1: (1.0 - 0.98) / 1.0 = 0.020   within 15 %
#   day 2.0: (2.0 - 1.60) / 2.0 = 0.200   below, but day 3.1 recovers: a blip, not the divergence
#   day 3.1: (3.0 - 2.90) / 3.0 = 0.033   within
#   day 4.0: (4.0 - 3.20) / 4.0 = 0.200   below, and everything later is below: the divergence
#   day 5.1: (5.0 - 4.00) / 5.0 = 0.200   below
BATCH = titers(BATCH_START, "b", [(1.1, 0.98), (2.0, 1.6), (3.1, 2.9), (4.0, 3.2), (5.1, 4.0)])


def diverge(batch=BATCH, reference=REFERENCE, **options):
    return calc.titer_divergence(
        batch, reference, batch_start=BATCH_START, reference_start=REFERENCE_START, **options
    )


def codes(result) -> list[str]:
    return [reason.code for reason in result.reasons]


def test_the_divergence_is_the_first_sample_of_the_last_unbroken_run_below_the_reference():
    result = diverge()
    assert (result.metric, result.unit, result.status) == ("titer_divergence", "days", "usable")
    assert result.value == pytest.approx(4.0)  # culture age of sample b@4.0
    assert result.calculation_version == "titer_divergence/1"
    [reason] = result.reasons
    assert reason.code == "diverged_from_reference"
    assert reason.values == {
        "result_id": "b@4.0",
        "reference_result_id": "ref@4",
        "collected_at": "2026-08-16T06:00:00Z",
        "titer": 3.2,
        "reference_titer": 4.0,
        "deficit_percent": pytest.approx(20.0),
        "tolerance_percent": 15.0,
        "later_samples_below": 1,
    }
    # Every pair it looked at, batch result then its reference.
    assert result.inputs == (
        "b@1.1", "ref@1", "b@2.0", "ref@2", "b@3.1", "ref@3", "b@4.0", "ref@4", "b@5.1", "ref@5"
    )  # fmt: skip


def test_a_batch_that_ends_within_the_tolerance_has_not_diverged():
    # The last sample is back within 15 %: (5.0 - 4.5) / 5.0 = 0.10. Earlier dips do not count.
    recovered = titers(BATCH_START, "b", [(1, 1.0), (2, 1.6), (3, 2.4), (4, 3.2), (5, 4.5)])
    result = diverge(recovered)
    assert (result.status, result.value) == ("usable", None)
    [reason] = result.reasons
    assert reason.code == "no_divergence"
    assert reason.values == {"pairs": 5, "tolerance_percent": 15.0}


def test_exactly_the_tolerance_is_not_more_than_the_tolerance():
    # Values a float holds exactly, so the edge is the edge: (2.0 - 1.5) / 2.0 = 0.25 and
    # (4.0 - 3.0) / 4.0 = 0.25. With a tolerance of 25 % that is not below "by more than" it.
    reference = titers(REFERENCE_START, "ref", [(2, 2.0), (4, 4.0)])
    edge = titers(BATCH_START, "b", [(2, 1.5), (4, 3.0)])
    assert codes(diverge(edge, reference, tolerance_fraction=0.25)) == ["no_divergence"]
    # With 12.5 % the same samples have diverged from the first one on.
    assert diverge(edge, reference, tolerance_fraction=0.125).value == pytest.approx(2.0)


def test_a_higher_titer_than_the_reference_is_not_a_divergence():
    higher = titers(BATCH_START, "b", [(1, 1.5), (2, 3.0), (3, 4.5)])
    assert codes(diverge(higher)) == ["no_divergence"]


def test_a_sample_with_no_reference_sample_near_its_age_is_left_out_never_interpolated():
    # Day 2.5 is 12 h from the reference samples of days 2 and 3; the window is 6 h. The straight
    # line between them would say 2.5 g/L: that number is never made up.
    batch = titers(BATCH_START, "b", [(1, 1.0), (2.5, 1.0), (4, 3.2), (5, 4.0)])
    result = diverge(batch)
    assert result.value == pytest.approx(4.0)
    assert "b@2.5" not in result.inputs
    assert codes(result) == ["diverged_from_reference", "samples_without_reference_pair"]
    assert result.reasons[1].values == {"ids": ["b@2.5"], "pairing_window_hours": 6.0}
    # A wider window pairs it (days 2 and 3 are equally near; the earlier one is taken).
    assert "b@2.5" in diverge(batch, pairing_window_hours=12).inputs


def test_the_nearest_reference_sample_in_culture_age_is_the_pair():
    reference = titers(REFERENCE_START, "ref", [(1.0, 1.0), (1.2, 1.2), (2.0, 2.0)])
    batch = titers(BATCH_START, "b", [(1.15, 1.2), (2.1, 2.0)])
    assert diverge(batch, reference).inputs == ("b@1.15", "ref@1.2", "b@2.1", "ref@2.0")


def test_fewer_than_two_pairs_is_insufficient():
    result = diverge(BATCH[:1])
    assert (result.status, result.value) == ("insufficient", None)
    assert codes(result) == ["fewer_than_two_reference_pairs"]
    assert result.reasons[0].values == {"pairs": 1}
    assert diverge(BATCH, []).status == "insufficient"


def test_only_results_available_at_as_of_are_compared_for_both_batches():
    # Titers arrive 24 h after collection. At batch day 4.5 the batch's results to day 3.1 are
    # in; the reference ran weeks earlier, so all of its results are. Pairs: days 1.1, 2.0, 3.1.
    result = diverge(as_of=BATCH_START + timedelta(days=4.5))
    assert (result.status, result.value) == ("usable", None)
    assert codes(result) == ["no_divergence", "result_not_yet_available"]
    assert result.reasons[0].values["pairs"] == 3
    assert result.reasons[1].values["ids"] == ["b@4.0", "b@5.1"]
    # An as_of before the reference's own results existed leaves nothing to compare with.
    early = diverge(as_of=REFERENCE_START + timedelta(days=1.5))
    assert early.status == "insufficient"


@pytest.mark.parametrize(
    ("batch", "reference", "code"),
    [
        (titers(BATCH_START, "b", [(1, 1.0), (2, 2000.0)], unit="mg/L"), REFERENCE, "wrong_unit"),
        (BATCH, titers(REFERENCE_START, "ref", [(1, 1.0), (2, -2.0)]), "negative_value"),
        (titers(BATCH_START, "b", [(1, 1.0), (2, float("nan"))]), REFERENCE, "non_finite_value"),
        (titers(BATCH_START, "b", [(1, 1.0), (1, 1.1)]), REFERENCE, "times_not_increasing"),
    ],
)
def test_the_comparison_is_invalid_when_an_input_breaks_a_rule(batch, reference, code):
    result = diverge(batch, reference)
    assert (result.status, result.value) == ("invalid", None)
    assert code in codes(result)


def test_a_reference_titer_of_zero_is_compared_without_dividing_by_it():
    # Both start at zero (nothing made yet): not below. Later the batch stays below.
    # Day 2: (2.0 - 1.0) / 2.0 = 0.5; day 3: (3.0 - 1.5) / 3.0 = 0.5.
    reference = titers(REFERENCE_START, "ref", [(0, 0.0), (2, 2.0), (3, 3.0)])
    batch = titers(BATCH_START, "b", [(0, 0.0), (2, 1.0), (3, 1.5)])
    result = diverge(batch, reference)
    assert result.value == pytest.approx(2.0)
    assert result.reasons[0].values["deficit_percent"] == pytest.approx(50.0)


# A step's recovery against the reference batch's ----------------------------------------------


def percent(metric: str, value: float | None, status: str = "usable", inputs=("x",)) -> calc.Result:
    return calc.Result(metric, value, "%", status, (), tuple(inputs), "ratio_percent/1")


def test_a_recovery_more_than_the_tolerance_below_the_reference_is_a_shortfall():
    # 93.6 - 73.4 = 20.2 points below; the default tolerance is 10 points.
    result = calc.recovery_shortfall(
        percent("protein_a_recovery", 73.4, inputs=("e", "l")),
        percent("protein_a_recovery", 93.6, inputs=("re", "rl")),
    )
    assert (result.metric, result.unit, result.status) == (
        "protein_a_recovery_shortfall",
        "percentage points",
        "usable",
    )
    assert result.value == pytest.approx(20.2)
    assert result.calculation_version == "recovery_shortfall/1"
    [reason] = result.reasons
    assert reason.code == "below_reference"
    assert reason.values == {
        "metric": "protein_a_recovery",
        "value": 73.4,
        "reference_value": 93.6,
        "tolerance_points": 10.0,
    }
    assert result.inputs == ("e", "l", "re", "rl")


def test_a_recovery_within_the_tolerance_or_above_the_reference_is_no_shortfall():
    # 97.0 - 89.4 = 7.6 points: within 10. Exactly 10 points is not "more than" 10.
    for value, reference in ((89.4, 97.0), (86.0, 96.0), (95.0, 91.0)):
        result = calc.recovery_shortfall(percent("y", value), percent("y", reference))
        assert (result.status, result.value) == ("usable", None)
        assert codes(result) == ["within_reference"]
    # The tolerance is a setting: 7.6 points is a shortfall at 5.
    tight = calc.recovery_shortfall(percent("y", 89.4), percent("y", 97.0), tolerance_points=5)
    assert tight.value == pytest.approx(7.6)


def test_a_recovery_without_a_value_on_either_side_cannot_be_compared():
    missing = percent("protein_a_recovery", None, "insufficient")
    for pair in ((missing, percent("r", 93.6)), (percent("r", 73.4), missing)):
        result = calc.recovery_shortfall(*pair)
        assert (result.status, result.value) == ("insufficient", None)
        assert codes(result) == ["input_not_usable"]


def test_a_suspect_recovery_makes_the_comparison_suspect():
    result = calc.recovery_shortfall(percent("r", 73.4), percent("r", 106.4, "suspect"))
    assert result.status == "suspect" and result.value == pytest.approx(33.0)
    assert codes(result) == ["below_reference", "input_suspect"]


def test_a_suspect_recovery_that_is_within_the_reference_has_no_value_and_is_not_called_suspect():
    # 106 % is itself suspect (above 105), and above the reference: nothing is short. A result
    # without a value is never "suspect": that status means a value is shown, flagged.
    result = calc.recovery_shortfall(percent("r", 106.0, "suspect"), percent("r", 93.6))
    assert (result.status, result.value) == ("usable", None)
    assert codes(result) == ["within_reference", "input_suspect"]
