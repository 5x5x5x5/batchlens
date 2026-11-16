"""Product mass: at harvest, in a pool, and the ratio of two masses (yield, recovery).

Every mass here is an estimate from a concentration times a volume, and says so with the assay
method in its reasons.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from batchlens.calc.results import (
    INSUFFICIENT,
    INVALID,
    SUSPECT,
    USABLE,
    Measurement,
    Online,
    Pool,
    Reason,
    Result,
    available,
    insufficient,
    invalid,
    iso,
    value_problems,
)

MASS_UNIT = "g"
HARVEST_VERSION = "harvest_mass/1"
POOL_VERSION = "pool_mass/1"
RATIO_VERSION = "ratio_percent/1"
# The last culture titer must be collected within this window before the phase ends.
HARVEST_TITER_WINDOW_HOURS = 12.0
# The online volume used is the last value at or before the sample, no older than this.
VOLUME_MAX_AGE_SECONDS = 900.0
# A step recovery or yield above this is shown, flagged suspect.
RECOVERY_SUSPECT_ABOVE_PERCENT = 105.0
# Pools merged into one: the merged mass may differ from the sum of the parts by this much.
MERGE_TOLERANCE_PERCENT = 3.0
MERGE_VERSION = "merge_balance/1"
# A transfer: the volume that arrived may differ from the recorded one by this much.
TRANSFER_TOLERANCE_PERCENT = 5.0
TRANSFER_VERSION = "transfer_balance/1"
# All six are illustrative defaults (docs/scientific-assumptions.md), not acceptance limits.


def _estimated(method: str) -> Reason:
    return Reason("estimated_from_concentration_times_volume", {"method": method})


def harvest_mass(
    titer: Sequence[Measurement],
    volume: Online,
    *,
    phase_start: datetime,
    phase_end: datetime,
    as_of: datetime | None = None,
    window_hours: float = HARVEST_TITER_WINDOW_HOURS,
    volume_max_age_seconds: float = VOLUME_MAX_AGE_SECONDS,
) -> Result:
    """The last culture titer times the bioreactor volume at that sample's collection time.

    The titer is per litre of supernatant and the volume is whole broth: no packed-cell-volume
    correction is applied.
    """

    def missing(*reasons: Reason) -> Result:
        return insufficient("harvest_mass", MASS_UNIT, HARVEST_VERSION, *reasons)

    if as_of is not None and as_of < phase_end:
        return missing(
            # The end itself is not given: as of then, it had not happened.
            Reason("phase_not_ended", {"as_of": iso(as_of)})
        )
    in_phase = sorted((m for m in titer if phase_start <= m.at <= phase_end), key=lambda m: m.at)
    if not in_phase:
        return missing(Reason("no_titer_in_phase", {}))
    last = in_phase[-1]
    if phase_end - last.at > timedelta(hours=window_hours):
        return missing(
            Reason(
                "no_titer_near_phase_end",
                {"last_titer_at": iso(last.at), "window_hours": window_hours},
            )
        )
    used, notes = available([last], as_of)
    if not used:
        return missing(*notes)
    problems = value_problems(last.id, last.value, last.unit, "g/L")
    if volume.unit != "L":
        problems.append(
            Reason("wrong_unit", {"id": volume.signal_id, "unit": volume.unit, "expected": "L"})
        )
    if problems:
        return invalid("harvest_mass", MASS_UNIT, HARVEST_VERSION, problems)
    oldest = last.at - timedelta(seconds=volume_max_age_seconds)
    near = [value for moment, value in volume.points if oldest <= moment <= last.at]
    if not near:
        return missing(
            Reason(
                "no_volume_near_sample",
                {"sample_at": iso(last.at), "max_age_seconds": volume_max_age_seconds},
            )
        )
    problems = value_problems(volume.signal_id, near[-1], volume.unit, "L")
    if problems:
        return invalid("harvest_mass", MASS_UNIT, HARVEST_VERSION, problems)
    return Result(
        "harvest_mass",
        last.value * near[-1],
        MASS_UNIT,
        USABLE,
        (_estimated(last.method),),
        (last.id, volume.signal_id),
        HARVEST_VERSION,
    )


def pool_mass(metric: str, pool: Pool | None, *, as_of: datetime | None = None) -> Result:
    """``volume_L * concentration_g_per_L`` of one pool measurement."""

    if pool is None:
        return insufficient(metric, MASS_UNIT, POOL_VERSION, Reason("measurement_missing", {}))
    used, notes = available([pool], as_of)
    if not used:
        return insufficient(metric, MASS_UNIT, POOL_VERSION, *notes)
    problems = value_problems(pool.id, pool.volume, pool.volume_unit, "L")
    problems += value_problems(pool.id, pool.concentration, pool.concentration_unit, "g/L")
    if problems:
        return invalid(metric, MASS_UNIT, POOL_VERSION, problems)
    return Result(
        metric,
        pool.volume * pool.concentration,
        MASS_UNIT,
        USABLE,
        (_estimated(pool.method),),
        (pool.id,),
        POOL_VERSION,
    )


def ratio_percent(
    metric: str,
    numerator: Result,
    denominator: Result,
    *,
    suspect_above: float = RECOVERY_SUSPECT_ABOVE_PERCENT,
) -> Result:
    """``100 * numerator / denominator`` of two masses. A missing or zero denominator is
    ``insufficient``, never 0 %; a value above ``suspect_above`` is shown, flagged."""

    for part in (numerator, denominator):
        if part.value is None:
            reason = Reason("input_not_usable", {"metric": part.metric, "status": part.status})
            return insufficient(metric, "%", RATIO_VERSION, reason)
    if denominator.value == 0:
        reason = Reason("zero_denominator", {"metric": denominator.metric})
        return insufficient(metric, "%", RATIO_VERSION, reason)
    value = 100 * numerator.value / denominator.value
    reasons = [
        Reason("input_suspect", {"metric": part.metric})
        for part in (numerator, denominator)
        if part.status == SUSPECT
    ]
    if value > suspect_above:
        reasons.append(Reason("above_plausibility_bound", {"bound_percent": float(suspect_above)}))
    return Result(
        metric,
        value,
        "%",
        SUSPECT if reasons else USABLE,
        tuple(reasons),
        numerator.inputs + denominator.inputs,
        RATIO_VERSION,
    )


__all__ = ["INSUFFICIENT", "INVALID", "harvest_mass", "pool_mass", "ratio_percent"]


def merge_balance(
    parts: Sequence[Result],
    whole: Result,
    *,
    tolerance_percent: float = MERGE_TOLERANCE_PERCENT,
) -> Result:
    """Pools merged into one: ``100 * (whole - sum(parts)) / sum(parts)``, the mass the merged
    pool has beyond (or short of) what went into it. Outside the tolerance it is ``suspect``:
    mass does not appear, and what disappears should be accounted for. A part without a value
    makes it ``insufficient``; a partial sum is never used."""

    def missing(reason: Reason) -> Result:
        return insufficient("merge_balance", "%", MERGE_VERSION, reason)

    if not parts:
        return missing(Reason("no_sources", {}))
    for part in (*parts, whole):
        if part.value is None:
            return missing(
                Reason("input_not_usable", {"metric": part.metric, "status": part.status})
            )
    total = sum(part.value for part in parts)
    if total == 0:
        return missing(Reason("zero_denominator", {"metric": "merged_parts"}))
    value = 100 * (whole.value - total) / total
    outside = abs(value) > tolerance_percent
    reasons = (
        [Reason("outside_merge_tolerance", {"tolerance_percent": float(tolerance_percent)})]
        if outside
        else []
    )
    return Result(
        "merge_balance",
        value,
        "%",
        SUSPECT if outside else USABLE,
        tuple(reasons),
        tuple(i for part in parts for i in part.inputs) + whole.inputs,
        MERGE_VERSION,
    )


def transfer_balance(
    transfer_id: str,
    recorded: float,
    unit: str,
    destination: Online,
    *,
    start: datetime,
    end: datetime,
    as_of: datetime | None = None,
    tolerance_percent: float = TRANSFER_TOLERANCE_PERCENT,
    volume_max_age_seconds: float = VOLUME_MAX_AGE_SECONDS,
) -> Result:
    """A recorded transfer against the vessel it went into: ``100 * (arrived - recorded) /
    recorded``, where ``arrived`` is the destination's volume signal just after the transfer
    minus just before it (the last value at or before ``start`` and the first at or after
    ``end``, each no further away than the maximum age). Outside the tolerance it is
    ``suspect``: the record and the vessel disagree, and which is wrong is not decided here.
    Without a value on either side it is ``insufficient``; nothing is interpolated."""

    def missing(*reasons: Reason) -> Result:
        return insufficient("transfer_balance", "%", TRANSFER_VERSION, *reasons)

    if as_of is not None and as_of < end:
        return missing(Reason("transfer_not_ended", {"as_of": iso(as_of)}))
    problems = value_problems(transfer_id, recorded, unit, "L")
    if destination.unit != "L":
        wrong = {"id": destination.signal_id, "unit": destination.unit, "expected": "L"}
        problems.append(Reason("wrong_unit", wrong))
    if problems:
        return invalid("transfer_balance", "%", TRANSFER_VERSION, problems)
    if recorded == 0:
        return missing(Reason("zero_denominator", {"metric": "recorded_volume"}))
    reach = timedelta(seconds=volume_max_age_seconds)
    latest = end + reach if as_of is None else min(end + reach, as_of)
    before = [value for moment, value in destination.points if start - reach <= moment <= start]
    after = [value for moment, value in destination.points if end <= moment <= latest]
    for side, values in (("before", before), ("after", after)):
        if not values:
            where = {"side": side, "max_age_seconds": volume_max_age_seconds}
            return missing(Reason("no_volume_near_transfer", where))
    for value in (before[-1], after[0]):
        problems += value_problems(destination.signal_id, value, destination.unit, "L")
    if problems:
        return invalid("transfer_balance", "%", TRANSFER_VERSION, problems)
    arrived = after[0] - before[-1]
    value = 100 * (arrived - recorded) / recorded
    outside = abs(value) > tolerance_percent
    seen = {"arrived": arrived, "recorded": recorded, "tolerance_percent": float(tolerance_percent)}
    return Result(
        "transfer_balance",
        value,
        "%",
        SUSPECT if outside else USABLE,
        (Reason("outside_transfer_tolerance" if outside else "transfer_balanced", seen),),
        (transfer_id, destination.signal_id),
        TRANSFER_VERSION,
    )
