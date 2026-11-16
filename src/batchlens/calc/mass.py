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
# All four are illustrative defaults (docs/scientific-assumptions.md), not acceptance limits.


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
            Reason("phase_not_ended", {"phase_end": iso(phase_end), "as_of": iso(as_of)})
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
