"""The pure calculations (``batchlens.calc``) against hand-calculated oracles.

Every expected number is worked out in a comment beside its test; nothing here is computed by
the code under test. Times are irregular on purpose.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from batchlens import calc
from batchlens.calc import Measurement, Online, Pool, Reason, Result

T0 = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
VCD_UNIT = "1e6 cells/mL"


def at(days: float) -> datetime:
    return T0 + timedelta(days=days)


def vcd(days: float, value: float, *, unit: str = VCD_UNIT, late_hours: float = 2) -> Measurement:
    return Measurement(f"vcd@{days}", at(days), value, unit, at(days) + timedelta(hours=late_hours))


def titer(days: float, value: float, *, unit: str = "g/L", late_hours: float = 24) -> Measurement:
    return Measurement(
        f"titer@{days}", at(days), value, unit, at(days) + timedelta(hours=late_hours), "HPLC"
    )


def codes(result: Result) -> list[str]:
    return [reason.code for reason in result.reasons]


# Four samples at days 0, 1.25, 3.0 and 3.5 (irregular spacing).
CURVE = [vcd(0, 0.5), vcd(1.25, 1.5), vcd(3.0, 4.0), vcd(3.5, 5.0)]
TITERS = [titer(0, 0.0), titer(1.25, 0.02), titer(3.0, 0.10), titer(3.5, 0.16625)]


# IVCD ---------------------------------------------------------------------------------------


def test_ivcd_is_the_trapezoid_over_irregular_samples():
    # 0.5 * (0.5 + 1.5) * 1.25 = 1.25
    # 0.5 * (1.5 + 4.0) * 1.75 = 4.8125
    # 0.5 * (4.0 + 5.0) * 0.50 = 2.25
    # sum                      = 8.3125
    result = calc.ivcd(CURVE)
    assert result.value == pytest.approx(8.3125, rel=1e-12)
    assert (result.metric, result.unit, result.status) == ("ivcd", "1e6 cell-days/mL", "usable")
    assert result.inputs == ("vcd@0", "vcd@1.25", "vcd@3.0", "vcd@3.5")
    assert result.calculation_version == "ivcd/1"
    assert result.reasons == ()


def test_ivcd_needs_two_samples():
    result = calc.ivcd(CURVE[:1])
    assert (result.status, result.value) == ("insufficient", None)
    assert result.reasons == (Reason("fewer_than_two_samples", {"count": 1}),)


@pytest.mark.parametrize(
    ("samples", "code"),
    [
        ([vcd(0, 0.5), vcd(1, -0.1)], "negative_value"),
        ([vcd(0, 0.5), vcd(1, float("nan"))], "non_finite_value"),
        ([vcd(0, 0.5), vcd(1, float("inf"))], "non_finite_value"),
        ([vcd(0, 0.5), vcd(0, 0.6)], "times_not_increasing"),
        ([vcd(1, 0.5), vcd(0, 0.6)], "times_not_increasing"),
        ([vcd(0, 0.5), vcd(1, 600.0, unit="1e3 cells/mL")], "wrong_unit"),
    ],
)
def test_ivcd_is_invalid_when_an_input_breaks_a_rule(samples, code):
    result = calc.ivcd(samples)
    assert (result.status, result.value) == ("invalid", None)
    assert code in codes(result)


def test_ivcd_never_bridges_a_gap_longer_than_the_maximum():
    # Days 1.25 to 4.5 are 3.25 days apart; the default maximum is 3 days.
    result = calc.ivcd([vcd(0, 0.5), vcd(1.25, 1.5), vcd(4.5, 4.0)])
    assert (result.status, result.value) == ("insufficient", None)
    [reason] = result.reasons
    assert reason.code == "gap_exceeds_maximum"
    assert reason.values["gap_days"] == pytest.approx(3.25)
    assert reason.values["max_gap_days"] == 3.0
    # The limit is a setting: with 4 days the same samples are usable.
    # 0.5 * 2.0 * 1.25 + 0.5 * 5.5 * 3.25 = 1.25 + 8.9375 = 10.1875
    assert calc.ivcd(
        [vcd(0, 0.5), vcd(1.25, 1.5), vcd(4.5, 4.0)], max_gap_days=4
    ).value == pytest.approx(10.1875)


def test_ivcd_uses_only_results_available_at_as_of():
    # The day 3.5 count is available 2 h after collection; one hour after collection it is not.
    as_of = at(3.5) + timedelta(hours=1)
    result = calc.ivcd(CURVE, as_of=as_of)
    # Without the last sample: 1.25 + 4.8125 = 6.0625
    assert result.value == pytest.approx(6.0625)
    assert result.inputs == ("vcd@0", "vcd@1.25", "vcd@3.0")
    assert result.status == "usable"
    [reason] = result.reasons
    assert reason.code == "result_not_yet_available"
    assert reason.values["ids"] == ["vcd@3.5"]


# Specific productivity ------------------------------------------------------------------------


def test_qp_is_the_titer_gain_over_ivcd_on_the_same_window():
    # 1000 * (0.16625 - 0.0) g/L / 8.3125 (1e6 cell-days/mL) = 166.25 / 8.3125 = 20.0 pg/cell/day
    result = calc.specific_productivity(CURVE, TITERS)
    assert result.value == pytest.approx(20.0, rel=1e-12)
    assert (result.metric, result.unit, result.status) == ("qp", "pg/cell/day", "usable")
    assert set(result.inputs) == {m.id for m in CURVE} | {"titer@0", "titer@3.5"}


def test_qp_window_ends_at_the_last_titer_available_at_as_of():
    # At day 3.5 + 1 h the cell counts to day 3.0 are in (the day 3.5 count is not), and titers
    # (24 h late) only to day 1.25. Window: day 0 to day 1.25.
    # IVCD = 1.25; qP = 1000 * (0.02 - 0.0) / 1.25 = 16.0
    result = calc.specific_productivity(CURVE, TITERS, as_of=at(3.5) + timedelta(hours=1))
    assert result.value == pytest.approx(16.0)
    assert "result_not_yet_available" in codes(result)
    assert "titer@3.0" not in result.inputs and "vcd@3.0" not in result.inputs


def test_qp_is_insufficient_until_two_samples_have_both_results():
    # Three hours in, the first cell count is available and no titer is (24 h late).
    result = calc.specific_productivity(CURVE, TITERS, as_of=at(0) + timedelta(hours=3))
    assert (result.status, result.value) == ("insufficient", None)
    assert "fewer_than_two_paired_samples" in codes(result)


def test_qp_passes_on_why_ivcd_could_not_be_computed():
    wrong = [vcd(0, 0.5), vcd(1.25, -1.0)]
    result = calc.specific_productivity(wrong, TITERS[:2])
    assert (result.status, result.value) == ("invalid", None)
    assert "negative_value" in codes(result)
    gap = calc.specific_productivity([vcd(0, 0.5), vcd(4, 1.0)], [titer(0, 0.0), titer(4, 0.1)])
    assert gap.status == "insufficient" and "gap_exceeds_maximum" in codes(gap)


def test_qp_with_a_wrong_titer_unit_is_invalid_not_converted():
    result = calc.specific_productivity(CURVE, [titer(0, 0.0), titer(3.5, 166.25, unit="mg/L")])
    assert (result.status, result.value) == ("invalid", None)
    assert "wrong_unit" in codes(result)


def test_qp_with_no_cells_is_insufficient_never_a_division_by_zero():
    result = calc.specific_productivity([vcd(0, 0.0), vcd(1, 0.0)], [titer(0, 0.0), titer(1, 0.1)])
    assert (result.status, result.value) == ("insufficient", None)
    assert "zero_denominator" in codes(result)


def test_a_falling_titer_gives_a_negative_qp_shown_as_suspect():
    # 1000 * (0.01 - 0.02) / 1.25 = -8.0
    result = calc.specific_productivity(CURVE[:2], [titer(0, 0.02), titer(1.25, 0.01)])
    assert result.value == pytest.approx(-8.0)
    assert result.status == "suspect" and "negative_productivity" in codes(result)


# Product mass at harvest ----------------------------------------------------------------------

PHASE_START, PHASE_END = at(0), at(14.25)
LAST = titer(14.0, 5.0)  # 6 h before the end of the production phase
VOLUME = Online(
    "src:BR.VOLUME",
    "L",
    [
        (at(14.0) - timedelta(minutes=20), 1988.0),
        (at(14.0) - timedelta(minutes=10), 1990.0),
        (at(14.0) + timedelta(minutes=5), 1750.0),  # after the sample: never used
    ],
)


def harvest(**changes):
    options = {"titer": [titer(13.0, 4.6), LAST], "volume": VOLUME, **changes}
    return calc.harvest_mass(
        options.pop("titer"),
        options.pop("volume"),
        phase_start=PHASE_START,
        phase_end=PHASE_END,
        **options,
    )


def test_harvest_mass_is_last_titer_times_volume_at_its_collection_time():
    # 5.0 g/L * 1990 L (the last online value at or before the sample, 10 min old) = 9950 g
    result = harvest()
    assert result.value == pytest.approx(9950.0)
    assert (result.metric, result.unit, result.status) == ("harvest_mass", "g", "usable")
    assert result.inputs == ("titer@14.0", "src:BR.VOLUME")
    assert result.reasons == (
        Reason("estimated_from_concentration_times_volume", {"method": "HPLC"}),
    )


def test_harvest_mass_waits_for_the_titer_result():
    # The titer is available 24 h after collection; 12 h after the end of the phase it is not.
    result = harvest(as_of=PHASE_END + timedelta(hours=12))
    assert (result.status, result.value) == ("insufficient", None)
    [reason] = result.reasons
    assert reason.code == "result_not_yet_available" and reason.values["ids"] == ["titer@14.0"]


def test_harvest_mass_before_the_phase_ended_is_insufficient():
    result = harvest(as_of=at(10))
    assert result.status == "insufficient" and codes(result) == ["phase_not_ended"]


def test_harvest_mass_needs_a_titer_close_to_the_end_of_the_phase():
    # The last sample is 1.25 days before the end; the window is 12 h.
    result = harvest(titer=[titer(13.0, 4.6)])
    assert result.status == "insufficient" and codes(result) == ["no_titer_near_phase_end"]
    # A sample collected after the phase is not a culture sample.
    result = harvest(titer=[titer(14.5, 5.0)])
    assert result.status == "insufficient" and codes(result) == ["no_titer_in_phase"]


def test_harvest_mass_never_reaches_for_an_old_or_later_volume():
    old = Online("src:BR.VOLUME", "L", [(at(14.0) - timedelta(minutes=16), 1990.0)])
    result = harvest(volume=old)  # the default maximum age is 15 minutes
    assert result.status == "insufficient" and codes(result) == ["no_volume_near_sample"]
    later = Online("src:BR.VOLUME", "L", [(at(14.0) + timedelta(seconds=1), 1990.0)])
    assert codes(harvest(volume=later)) == ["no_volume_near_sample"]


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"volume": Online("s", "m3", VOLUME.points)}, "wrong_unit"),
        ({"volume": Online("s", "L", [(at(14.0), float("nan"))])}, "non_finite_value"),
        ({"volume": Online("s", "L", [(at(14.0), -5.0)])}, "negative_value"),
        ({"titer": [titer(14.0, 5000.0, unit="mg/L")]}, "wrong_unit"),
        ({"titer": [titer(14.0, -1.0)]}, "negative_value"),
    ],
)
def test_harvest_mass_is_invalid_when_an_input_breaks_a_rule(changes, code):
    result = harvest(**changes)
    assert (result.status, result.value) == ("invalid", None)
    assert code in codes(result)


# Pool masses, yield and recovery --------------------------------------------------------------


def pool(name: str, volume: float, concentration: float, **changes) -> Pool:
    fields = {
        "id": name,
        "volume": volume,
        "volume_unit": "L",
        "concentration": concentration,
        "concentration_unit": "g/L",
        "method": "UV A280",
        "available_at": at(15),
        **changes,
    }
    return Pool(**fields)


LOAD = pool("load", 1900.0, 4.8)  # 1900 * 4.8 = 9120 g
ELUATE = pool("eluate", 450.0, 18.5)  # 450 * 18.5 = 8325 g


def test_pool_mass_is_volume_times_concentration_and_says_so():
    result = calc.pool_mass("protein_a_load_mass", LOAD)
    assert result.value == pytest.approx(9120.0)
    assert (result.unit, result.status, result.inputs) == ("g", "usable", ("load",))
    assert result.reasons == (
        Reason("estimated_from_concentration_times_volume", {"method": "UV A280"}),
    )


def test_pool_mass_without_a_measurement_or_before_it_is_available_is_insufficient():
    missing = calc.pool_mass("protein_a_load_mass", None)
    assert missing.status == "insufficient" and codes(missing) == ["measurement_missing"]
    early = calc.pool_mass("protein_a_load_mass", LOAD, as_of=at(15) - timedelta(seconds=1))
    assert (early.status, early.value) == ("insufficient", None)
    assert codes(early) == ["result_not_yet_available"]
    assert calc.pool_mass("protein_a_load_mass", LOAD, as_of=at(15)).status == "usable"


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"volume_unit": "mL"}, "wrong_unit"),
        ({"concentration_unit": "mg/mL"}, "wrong_unit"),
        ({"volume": -1.0}, "negative_value"),
        ({"concentration": float("nan")}, "non_finite_value"),
    ],
)
def test_pool_mass_is_invalid_when_an_input_breaks_a_rule(changes, code):
    result = calc.pool_mass(
        "protein_a_load_mass",
        pool(**{"name": "load", "volume": 1900.0, "concentration": 4.8, **changes}),
    )
    assert (result.status, result.value) == ("invalid", None)
    assert code in codes(result)


def test_harvest_to_load_yield_and_protein_a_recovery():
    harvest_mass = harvest()  # 9950 g
    load = calc.pool_mass("protein_a_load_mass", LOAD)  # 9120 g
    eluate = calc.pool_mass("protein_a_eluate_mass", ELUATE)  # 8325 g
    # 100 * 9120 / 9950 = 91.65829...
    step_yield = calc.ratio_percent("harvest_to_load_yield", load, harvest_mass)
    assert step_yield.value == pytest.approx(91.658291, rel=1e-7)
    assert (step_yield.unit, step_yield.status) == ("%", "usable")
    assert step_yield.inputs == load.inputs + harvest_mass.inputs
    # 100 * 8325 / 9120 = 91.28289...
    recovery = calc.ratio_percent("protein_a_recovery", eluate, load)
    assert recovery.value == pytest.approx(91.282895, rel=1e-7)
    assert recovery.status == "usable"


def test_a_missing_or_zero_denominator_is_insufficient_never_zero_percent():
    eluate = calc.pool_mass("protein_a_eluate_mass", ELUATE)
    missing = calc.ratio_percent("protein_a_recovery", eluate, calc.pool_mass("load", None))
    assert (missing.status, missing.value) == ("insufficient", None)
    assert codes(missing) == ["input_not_usable"]
    assert missing.reasons[0].values == {"metric": "load", "status": "insufficient"}
    empty = calc.pool_mass("protein_a_load_mass", pool("load", 0.0, 4.8))  # 0 g, a valid number
    zero = calc.ratio_percent("protein_a_recovery", eluate, empty)
    assert (zero.status, zero.value) == ("insufficient", None)
    assert codes(zero) == ["zero_denominator"]


def test_a_recovery_above_the_plausibility_bound_is_suspect_with_its_value_unchanged():
    # 100 * 9700 / 9120 = 106.359...: above the default bound of 105 %
    eluate = calc.pool_mass("protein_a_eluate_mass", pool("eluate", 500.0, 19.4))
    recovery = calc.ratio_percent("protein_a_recovery", eluate, calc.pool_mass("l", LOAD))
    assert recovery.value == pytest.approx(106.359649, rel=1e-7)
    assert recovery.status == "suspect"
    assert Reason("above_plausibility_bound", {"bound_percent": 105.0}) in recovery.reasons
    # 100 * 9500 / 9120 = 104.17: above 100 but under the bound, so it is not flagged.
    under = calc.pool_mass("protein_a_eluate_mass", pool("eluate", 500.0, 19.0))
    assert calc.ratio_percent("r", under, calc.pool_mass("l", LOAD)).status == "usable"


def test_a_suspect_input_makes_the_ratio_suspect():
    eluate = calc.pool_mass("protein_a_eluate_mass", pool("eluate", 500.0, 19.4))
    load = calc.pool_mass("protein_a_load_mass", LOAD)
    recovery = calc.ratio_percent("protein_a_recovery", eluate, load)  # suspect, 106.36 %
    chained = calc.ratio_percent("x", recovery, load)
    assert chained.status == "suspect" and chained.value is not None
    assert Reason("input_suspect", {"metric": "protein_a_recovery"}) in chained.reasons


def test_a_result_is_plain_data_for_the_api():
    body = calc.ivcd(CURVE, as_of=at(3.5) + timedelta(hours=1)).to_dict()
    assert body == {
        "metric": "ivcd",
        "value": pytest.approx(6.0625),
        "unit": "1e6 cell-days/mL",
        "status": "usable",
        "reasons": [
            {
                "code": "result_not_yet_available",
                "values": {"ids": ["vcd@3.5"], "as_of": "2026-07-04T21:00:00Z"},
            }
        ],
        "inputs": ["vcd@0", "vcd@1.25", "vcd@3.0"],
        "calculation_version": "ivcd/1",
    }


def test_growth_rate_is_the_log_of_the_last_count_over_the_first_per_day():
    counts = [vcd(0.0, 0.5), vcd(1.2, 1.1), vcd(3.0, 3.5)]
    result = calc.growth_rate("seed_n1_growth_rate", counts)
    # ln(3.5 / 0.5) / 3 d = 1.9459 / 3 = 0.6486 per day. The count between them is not used.
    assert (result.metric, result.unit, result.status) == ("seed_n1_growth_rate", "1/day", "usable")
    assert result.value == pytest.approx(0.6486, abs=1e-4)
    assert result.inputs == ("vcd@0.0", "vcd@3.0") and result.calculation_version == "growth_rate/1"


def test_growth_rate_without_two_usable_counts_has_no_value():
    assert calc.growth_rate("g", []).reasons[0].code == "fewer_than_two_samples"
    one = calc.growth_rate("g", [vcd(0.0, 0.5)])
    assert (one.value, one.status) == (None, "insufficient")
    # The last count was not available yet: it is named, and the rate waits.
    late = calc.growth_rate("g", [vcd(0.0, 0.5), vcd(3.0, 3.5)], as_of=at(3.0))
    assert late.value is None
    assert [r.code for r in late.reasons] == ["fewer_than_two_samples", "result_not_yet_available"]
    zero = calc.growth_rate("g", [vcd(0.0, 0.0), vcd(3.0, 3.5)])
    assert (zero.status, zero.reasons[0].code) == ("insufficient", "zero_cell_count")
    same = calc.growth_rate("g", [vcd(1.0, 0.5), vcd(1.0, 3.5)])
    assert (same.status, same.reasons[0].code) == ("invalid", "times_not_increasing")
    wrong = calc.growth_rate("g", [vcd(0.0, 0.5), vcd(3.0, 3.5, unit="cells/mL")])
    assert (wrong.status, wrong.reasons[0].code) == ("invalid", "wrong_unit")


def test_inoculation_density_is_the_first_count_only_when_taken_near_the_start():
    counts = [vcd(1 / 24, 0.52), vcd(1.0, 1.0)]
    result = calc.inoculation_density(counts, phase_start=at(0))
    assert (result.value, result.unit, result.status) == (0.52, "1e6 cells/mL", "usable")
    assert (
        result.inputs == (f"vcd@{1 / 24}",)
        and result.calculation_version == "inoculation_density/1"
    )
    # A first count a day in is not the density the culture began at.
    late = calc.inoculation_density(counts[1:], phase_start=at(0))
    assert (late.value, late.status) == (None, "insufficient")
    assert late.reasons[0].code == "no_count_near_inoculation"
    assert late.reasons[0].values == {"id": "vcd@1.0", "hours": 24.0, "window_hours": 6.0}
    none = calc.inoculation_density([], phase_start=at(0))
    assert (none.status, none.reasons[0].code) == ("insufficient", "no_cell_count")
    before = calc.inoculation_density(counts, phase_start=at(0), as_of=at(1 / 24))
    assert before.value is None and before.reasons[-1].code == "result_not_yet_available"


def density(value: float | None, status: str = "usable") -> Result:
    return Result(
        "inoculation_density", value, VCD_UNIT, status, (), ("x",), "inoculation_density/1"
    )


def test_an_inoculation_density_well_below_the_references_is_a_shortfall_in_percent_of_it():
    result = calc.inoculation_shortfall(density(0.2), density(0.5))
    # (0.5 - 0.2) / 0.5 = 60 %, beyond the tolerance of 20 %.
    assert (result.metric, result.unit, result.status) == (
        "inoculation_density_shortfall",
        "%",
        "usable",
    )
    assert result.value == pytest.approx(60.0)
    assert codes(result) == ["inoculated_below_reference"]
    assert result.reasons[0].values["tolerance_percent"] == 20.0
    assert result.inputs == ("x", "x") and result.calculation_version == "inoculation_shortfall/1"


def test_an_inoculation_density_within_the_tolerance_or_above_is_no_shortfall():
    for own in (0.41, 0.5, 0.9):  # 18 % below, equal, above
        result = calc.inoculation_shortfall(density(own), density(0.5))
        assert (result.value, result.status) == (None, "usable")
        assert codes(result) == ["inoculation_within_reference"]
    assert calc.inoculation_shortfall(density(0.39), density(0.5)).value == pytest.approx(22.0)


def test_an_inoculation_density_that_cannot_be_compared_is_insufficient():
    missing = calc.inoculation_shortfall(density(None, "insufficient"), density(0.5))
    assert (missing.value, missing.status, codes(missing)) == (
        None,
        "insufficient",
        ["input_not_usable"],
    )
    zero = calc.inoculation_shortfall(density(0.2), density(0.0))
    assert (zero.value, zero.status, codes(zero)) == (None, "insufficient", ["zero_denominator"])


def tank(*points: tuple[float, float], unit: str = "L") -> Online:
    """A vessel's volume signal: (minutes from T0, litres)."""

    return Online("vol", unit, [(T0 + timedelta(minutes=m), v) for m, v in points])


FEED = {"start": T0 + timedelta(minutes=10), "end": T0 + timedelta(minutes=20)}


def test_transfer_balance_is_what_arrived_against_what_was_recorded_in_percent():
    signal = tank((0, 1400.0), (10, 1400.5), (20, 1461.7), (30, 1461.0))
    result = calc.transfer_balance("T1", 60.0, "L", signal, **FEED)
    # Arrived: 1461.7 - 1400.5 = 61.2 L. 100 * (61.2 - 60) / 60 = 2.0 %.
    assert (result.metric, result.unit, result.status) == ("transfer_balance", "%", "usable")
    assert result.value == pytest.approx(2.0)
    assert codes(result) == ["transfer_balanced"]
    assert result.reasons[0].values["arrived"] == pytest.approx(61.2)
    assert result.inputs == ("T1", "vol") and result.calculation_version == "transfer_balance/1"


def test_a_transfer_whose_record_and_vessel_disagree_is_suspect_with_its_value_shown():
    signal = tank((10, 1400.0), (20, 1460.0))
    result = calc.transfer_balance("T1", 6.0, "L", signal, **FEED)  # a digit dropped
    assert (result.status, codes(result)) == ("suspect", ["outside_transfer_tolerance"])
    assert result.value == pytest.approx(900.0)
    assert result.reasons[0].values == {"arrived": 60.0, "recorded": 6.0, "tolerance_percent": 5.0}


def test_a_transfer_with_no_volume_value_close_on_either_side_is_insufficient():
    late = tank((10, 1400.0), (40, 1460.0))  # nothing within 900 s after the end
    result = calc.transfer_balance("T1", 60.0, "L", late, **FEED)
    assert (result.value, result.status) == (None, "insufficient")
    assert result.reasons[0].code == "no_volume_near_transfer"
    assert result.reasons[0].values["side"] == "after"
    none_before = calc.transfer_balance("T1", 60.0, "L", tank((20, 1460.0)), **FEED)
    assert none_before.reasons[0].values["side"] == "before"
    # As of a moment before it ended, it had not happened; a value recorded later is not used.
    signal = tank((10, 1400.0), (20, 1460.0))
    during = calc.transfer_balance(
        "T1", 60.0, "L", signal, **FEED, as_of=T0 + timedelta(minutes=15)
    )
    assert (during.status, codes(during)) == ("insufficient", ["transfer_not_ended"])


@pytest.mark.parametrize(
    ("recorded", "unit", "signal_unit", "code"),
    [
        (60.0, "kg", "L", "wrong_unit"),
        (60.0, "L", "m3", "wrong_unit"),
        (-60.0, "L", "L", "negative_value"),
        (float("nan"), "L", "L", "non_finite_value"),
    ],
)
def test_transfer_balance_is_invalid_when_an_input_breaks_a_rule(recorded, unit, signal_unit, code):
    signal = tank((10, 1400.0), (20, 1460.0), unit=signal_unit)
    result = calc.transfer_balance("T1", recorded, unit, signal, **FEED)
    assert (result.value, result.status, codes(result)) == (None, "invalid", [code])


def test_a_recorded_volume_of_zero_is_insufficient_never_a_division_by_zero():
    result = calc.transfer_balance("T1", 0.0, "L", tank((10, 1400.0), (20, 1460.0)), **FEED)
    assert (result.status, codes(result)) == ("insufficient", ["zero_denominator"])


def recovery(value: float | None, name: str = "x") -> Result:
    status = "usable" if value is not None else "insufficient"
    return Result("protein_a_recovery", value, "%", status, (), (name,), "ratio_percent/1")


def test_a_metric_is_placed_among_the_comparable_batches_by_their_median_and_range():
    others = [recovery(v, f"b{i}") for i, v in enumerate((93.6, 91.1, 92.4, 93.0))]
    result = calc.set_position(recovery(73.4), others)
    # Sorted: 91.1, 92.4, 93.0, 93.6. Median (92.4 + 93.0) / 2 = 92.7; 73.4 - 92.7 = -19.3.
    assert (result.metric, result.unit, result.status) == (
        "protein_a_recovery_among_comparable",
        "%",
        "usable",
    )
    assert result.value == pytest.approx(-19.3)
    assert codes(result) == ["below_comparable_range"]
    assert result.reasons[0].values == {
        "count": 4,
        "median": pytest.approx(92.7),
        "lowest": 91.1,
        "highest": 93.6,
        "without_value": 0,
    }
    assert result.inputs == ("x", "b0", "b1", "b2", "b3")
    assert result.calculation_version == "set_position/1"
    assert codes(calc.set_position(recovery(92.0), others)) == ["within_comparable_range"]
    assert codes(calc.set_position(recovery(93.6), others)) == ["within_comparable_range"]
    assert codes(calc.set_position(recovery(95.0), others[:3])) == ["above_comparable_range"]
    assert calc.set_position(recovery(95.0), others[:3]).reasons[0].values["median"] == 92.4


def test_too_few_comparable_batches_with_a_value_place_nothing():
    others = [recovery(93.6), recovery(91.1), recovery(None), recovery(None)]
    result = calc.set_position(recovery(90.0), others)
    assert (result.value, result.status) == (None, "insufficient")
    assert codes(result) == ["too_few_comparable_batches"]
    assert result.reasons[0].values == {"count": 2, "minimum": 3, "without_value": 2}
    missing = calc.set_position(recovery(None), [recovery(93.6)] * 3)
    assert (missing.status, codes(missing)) == ("insufficient", ["input_not_usable"])


def grams(value: float | None, name: str) -> Result:
    status = "usable" if value is not None else "insufficient"
    return Result(f"{name}_mass", value, "g", status, (), (name,), "pool_mass/1")


def test_split_balance_is_the_sum_of_the_parts_against_the_whole_in_percent():
    parts = [grams(2500.0, "c1"), grams(2480.0, "c2"), grams(2970.0, "c3")]
    result = calc.split_balance(grams(8000.0, "ds"), parts)
    # 2500 + 2480 + 2970 = 7950; 100 * (7950 - 8000) / 8000 = -0.625 %.
    assert (result.metric, result.unit, result.status) == ("split_balance", "%", "usable")
    assert result.value == pytest.approx(-0.625) and result.reasons == ()
    assert result.inputs == ("ds", "c1", "c2", "c3")
    assert result.calculation_version == "split_balance/1"


def test_a_split_whose_parts_do_not_add_up_is_suspect_either_way():
    short = calc.split_balance(grams(8000.0, "ds"), [grams(2500.0, "c1"), grams(2480.0, "c2")])
    assert short.status == "suspect" and short.value == pytest.approx(-37.75)
    assert short.reasons[0].values == {"tolerance_percent": 3.0, "parts": 2}
    over = calc.split_balance(grams(8000.0, "ds"), [grams(4500.0, "c1"), grams(4000.0, "c2")])
    assert (over.status, codes(over)) == ("suspect", ["outside_split_tolerance"])


def test_a_split_with_a_part_or_the_whole_missing_is_insufficient_never_a_partial_sum():
    missing = calc.split_balance(grams(8000.0, "ds"), [grams(2500.0, "c1"), grams(None, "c2")])
    assert (missing.value, missing.status, codes(missing)) == (
        None,
        "insufficient",
        ["input_not_usable"],
    )
    assert codes(calc.split_balance(grams(None, "ds"), [grams(1.0, "c1")])) == ["input_not_usable"]
    assert codes(calc.split_balance(grams(8000.0, "ds"), [])) == ["no_parts"]
    assert codes(calc.split_balance(grams(0.0, "ds"), [grams(1.0, "c1")])) == ["zero_denominator"]
