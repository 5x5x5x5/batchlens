"""A batch against the reference batch: where its titer left the reference's.

An observation, not a diagnosis: it says at which sample the titer was first, and from then on
always, below the reference by more than a tolerance. It says nothing about why, and it is the
first sample at which the gap is *seen*, which is later than whatever began it.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from batchlens.calc.results import (
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

DIVERGENCE_VERSION = "titer_divergence/1"
# Below the reference by more than this fraction of the reference's titer counts as below.
DIVERGENCE_TOLERANCE_FRACTION = 0.15
# A sample is compared with the reference sample nearest in culture age, at most this far away.
PAIRING_WINDOW_HOURS = 6.0
# Both are illustrative defaults (docs/scientific-assumptions.md), not acceptance limits.


def _problems(titer: Sequence[Measurement]) -> list[Reason]:
    found = [p for m in titer for p in value_problems(m.id, m.value, m.unit, "g/L")]
    found += [
        Reason("times_not_increasing", {"id": after.id, "at": iso(after.at)})
        for before, after in zip(titer, titer[1:])
        if after.at <= before.at
    ]
    return found


def titer_divergence(
    titer: Sequence[Measurement],
    reference: Sequence[Measurement],
    *,
    batch_start: datetime,
    reference_start: datetime,
    as_of: datetime | None = None,
    tolerance_fraction: float = DIVERGENCE_TOLERANCE_FRACTION,
    pairing_window_hours: float = PAIRING_WINDOW_HOURS,
) -> Result:
    """The culture age, in days, of the first titer sample that is below its reference sample
    by more than the tolerance and after which every later paired sample is below too; no value
    (``no_divergence``) when the batch ends within the tolerance.

    Each sample, in collection order, is paired with the reference sample nearest in culture
    age (time since the start of each batch's production phase), within the pairing window. A
    sample without such a pair is left out and named; nothing is interpolated.
    """

    def answer(value: float | None, status: str, reasons: list[Reason], inputs=()) -> Result:
        return Result(
            "titer_divergence",
            value,
            "days",
            status,
            tuple(reasons),
            tuple(inputs),
            DIVERGENCE_VERSION,
        )

    used, notes = available(titer, as_of)
    known, _ = available(reference, as_of)
    problems = _problems(used) + _problems(known)
    if problems:
        return invalid("titer_divergence", "days", DIVERGENCE_VERSION, problems)

    def age(sample: Measurement, start: datetime) -> float:
        return (sample.at - start).total_seconds() / 86400

    pairs: list[tuple[Measurement, Measurement]] = []
    unpaired: list[str] = []
    for sample in used:
        nearest = min(
            known,
            key=lambda other: abs(age(other, reference_start) - age(sample, batch_start)),
            default=None,
        )
        gap = None if nearest is None else age(nearest, reference_start) - age(sample, batch_start)
        if gap is None or abs(gap) * 24 > pairing_window_hours:
            unpaired.append(sample.id)
        else:
            pairs.append((sample, nearest))
    if unpaired:
        left_out = {"ids": unpaired, "pairing_window_hours": float(pairing_window_hours)}
        notes = [Reason("samples_without_reference_pair", left_out), *notes]
    if len(pairs) < 2:
        short = Reason("fewer_than_two_reference_pairs", {"pairs": len(pairs)})
        return insufficient("titer_divergence", "days", DIVERGENCE_VERSION, short, *notes)

    tolerance_percent = 100 * float(tolerance_fraction)
    inputs = [item.id for pair in pairs for item in pair]
    # Walk back from the last pair while each one is below: the run that reaches the end.
    first = len(pairs)
    while first > 0:
        sample, other = pairs[first - 1]
        if not other.value - sample.value > tolerance_fraction * other.value:
            break
        first -= 1
    if first == len(pairs):
        none = Reason(
            "no_divergence", {"pairs": len(pairs), "tolerance_percent": tolerance_percent}
        )
        return answer(None, USABLE, [none, *notes], inputs)
    sample, other = pairs[first]
    found = Reason(
        "diverged_from_reference",
        {
            "result_id": sample.id,
            "reference_result_id": other.id,
            "collected_at": iso(sample.at),
            "titer": sample.value,
            "reference_titer": other.value,
            "deficit_percent": 100 * (other.value - sample.value) / other.value,
            "tolerance_percent": tolerance_percent,
            "later_samples_below": len(pairs) - first - 1,
        },
    )
    return answer(age(sample, batch_start), USABLE, [found, *notes], inputs)
