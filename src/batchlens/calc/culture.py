"""Cell culture: the integral of viable cell density (IVCD), specific productivity (qP), a
passage's growth rate and the density a culture was started at.

Times are sample collection times; elapsed days are seconds / 86400.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime

from batchlens.calc.results import (
    INSUFFICIENT,
    SUSPECT,
    USABLE,
    Measurement,
    Reason,
    Result,
    available,
    insufficient,
    invalid,
    iso,
    value_problems,
)

VCD_UNIT = "1e6 cells/mL"
IVCD_UNIT = "1e6 cell-days/mL"
TITER_UNIT = "g/L"
QP_UNIT = "pg/cell/day"
IVCD_VERSION = "ivcd/1"
QP_VERSION = "qp/1"
GROWTH_UNIT = "1/day"
GROWTH_VERSION = "growth_rate/1"
INOCULATION_VERSION = "inoculation_density/1"
# How long after a phase began a cell count still stands for the density it began at.
# Illustrative default.
INOCULATION_WINDOW_HOURS = 6.0
# The longest span between two cell counts the trapezoid bridges. Illustrative default.
MAX_GAP_DAYS = 3.0


def _days(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 86400


def ivcd(
    vcd: Sequence[Measurement],
    *,
    as_of: datetime | None = None,
    max_gap_days: float = MAX_GAP_DAYS,
) -> Result:
    """``sum(0.5 * (X[i] + X[i+1]) * (t[i+1] - t[i]))`` over consecutive cell counts, given in
    collection order."""

    used, notes = available(vcd, as_of)
    problems = [p for m in used for p in value_problems(m.id, m.value, m.unit, VCD_UNIT)]
    problems += [
        Reason("times_not_increasing", {"id": after.id, "at": iso(after.at)})
        for before, after in zip(used, used[1:])
        if after.at <= before.at
    ]
    if problems:
        return invalid("ivcd", IVCD_UNIT, IVCD_VERSION, problems)
    if len(used) < 2:
        return insufficient(
            "ivcd",
            IVCD_UNIT,
            IVCD_VERSION,
            Reason("fewer_than_two_samples", {"count": len(used)}),
            *notes,
        )
    total = 0.0
    for before, after in zip(used, used[1:]):
        gap = _days(before.at, after.at)
        if gap > max_gap_days:
            reason = Reason(
                "gap_exceeds_maximum",
                {
                    "from": iso(before.at),
                    "to": iso(after.at),
                    "gap_days": gap,
                    "max_gap_days": float(max_gap_days),
                },
            )
            return insufficient("ivcd", IVCD_UNIT, IVCD_VERSION, reason, *notes)
        total += 0.5 * (before.value + after.value) * gap
    return Result(
        "ivcd", total, IVCD_UNIT, USABLE, tuple(notes), tuple(m.id for m in used), IVCD_VERSION
    )


def specific_productivity(
    vcd: Sequence[Measurement],
    titer: Sequence[Measurement],
    *,
    as_of: datetime | None = None,
    max_gap_days: float = MAX_GAP_DAYS,
) -> Result:
    """Culture-average qP: ``1000 * (titer_last - titer_first) / IVCD``, from the first to the
    last sample that has both a cell count and a titer.

    1 pg/cell/day x 1e6 cell-days/mL = 1e6 pg/mL = 1 mg/L, hence the factor 1000 for g/L. A
    concentration-basis estimate: it ignores the volume change of a fed batch.
    """

    counts, count_notes = available(vcd, as_of)
    titers, titer_notes = available(titer, as_of)
    notes = count_notes + titer_notes
    problems = [p for m in titers for p in value_problems(m.id, m.value, m.unit, TITER_UNIT)]
    # Two titers of one instant cannot be told apart by time: never keep one and drop the other.
    problems += [
        Reason("times_not_increasing", {"id": after.id, "at": iso(after.at)})
        for before, after in zip(titers, titers[1:])
        if after.at <= before.at
    ]
    if problems:
        return invalid("qp", QP_UNIT, QP_VERSION, problems)
    by_time = {m.at: m for m in titers}
    paired = sorted(m.at for m in counts if m.at in by_time)
    if len(paired) < 2:
        return insufficient(
            "qp",
            QP_UNIT,
            QP_VERSION,
            Reason("fewer_than_two_paired_samples", {"count": len(paired)}),
            *notes,
        )
    first, last = by_time[paired[0]], by_time[paired[-1]]
    window = [m for m in counts if first.at <= m.at <= last.at]
    integral = ivcd(window, max_gap_days=max_gap_days)
    if integral.value is None:
        return Result(
            "qp", None, QP_UNIT, integral.status, integral.reasons + tuple(notes), (), QP_VERSION
        )
    if integral.value == 0:
        return insufficient(
            "qp", QP_UNIT, QP_VERSION, Reason("zero_denominator", {"metric": "ivcd"}), *notes
        )
    value = 1000 * (last.value - first.value) / integral.value
    status = USABLE
    if value < 0:
        status, notes = SUSPECT, [*notes, Reason("negative_productivity", {})]
    return Result(
        "qp",
        value,
        QP_UNIT,
        status,
        tuple(notes),
        integral.inputs + (first.id, last.id),
        QP_VERSION,
    )


def growth_rate(
    metric: str, vcd: Sequence[Measurement], *, as_of: datetime | None = None
) -> Result:
    """The average specific growth rate of one passage: ``ln(X_last / X_first) / days`` between
    its first and its last cell count, given in collection order."""

    used, notes = available(vcd, as_of)
    problems = [p for m in used for p in value_problems(m.id, m.value, m.unit, VCD_UNIT)]
    if problems:
        return invalid(metric, GROWTH_UNIT, GROWTH_VERSION, problems)
    if len(used) < 2:
        reason = Reason("fewer_than_two_samples", {"count": len(used)})
        return insufficient(metric, GROWTH_UNIT, GROWTH_VERSION, reason, *notes)
    first, last = used[0], used[-1]
    if last.at <= first.at:
        reason = Reason("times_not_increasing", {"id": last.id, "at": iso(last.at)})
        return invalid(metric, GROWTH_UNIT, GROWTH_VERSION, [reason])
    if first.value == 0 or last.value == 0:
        zero = first if first.value == 0 else last
        return insufficient(
            metric, GROWTH_UNIT, GROWTH_VERSION, Reason("zero_cell_count", {"id": zero.id}), *notes
        )
    value = math.log(last.value / first.value) / _days(first.at, last.at)
    return Result(
        metric, value, GROWTH_UNIT, USABLE, tuple(notes), (first.id, last.id), GROWTH_VERSION
    )


def inoculation_density(
    vcd: Sequence[Measurement],
    *,
    phase_start: datetime,
    as_of: datetime | None = None,
    window_hours: float = INOCULATION_WINDOW_HOURS,
) -> Result:
    """The first cell count of a culture, when it was collected within ``window_hours`` of the
    phase's start. A later count is not the density the culture began at, and is not used."""

    def answer(*reasons: Reason) -> Result:
        return insufficient("inoculation_density", VCD_UNIT, INOCULATION_VERSION, *reasons)

    used, notes = available(vcd, as_of)
    if not used:
        return answer(Reason("no_cell_count", {}), *notes)
    first = min(used, key=lambda m: m.at)
    problems = value_problems(first.id, first.value, first.unit, VCD_UNIT)
    if problems:
        return invalid("inoculation_density", VCD_UNIT, INOCULATION_VERSION, problems)
    hours = (first.at - phase_start).total_seconds() / 3600
    if not 0 <= hours <= window_hours:
        values = {"id": first.id, "hours": hours, "window_hours": float(window_hours)}
        return answer(Reason("no_count_near_inoculation", values), *notes)
    return Result(
        "inoculation_density",
        first.value,
        VCD_UNIT,
        USABLE,
        tuple(notes),
        (first.id,),
        INOCULATION_VERSION,
    )


__all__ = [
    "INOCULATION_WINDOW_HOURS",
    "INSUFFICIENT",
    "MAX_GAP_DAYS",
    "growth_rate",
    "inoculation_density",
    "ivcd",
    "specific_productivity",
]
