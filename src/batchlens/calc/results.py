"""What every calculation takes and answers.

| Status | Meaning |
|---|---|
| ``usable`` | Computed from valid inputs |
| ``suspect`` | Computed, but an input or the result is implausible; the value is shown, flagged |
| ``insufficient`` | Not computed: something required is missing or not yet available |
| ``invalid`` | Not computed: an input breaks a rule |

A reason is a machine-readable code and the values involved; words come at the edge (the
interface translates the code). A ``usable`` result may carry reasons too: they then say what
it rests on (a result left out because it was not yet available, a mass estimated from
concentration times volume).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

USABLE = "usable"
SUSPECT = "suspect"
INSUFFICIENT = "insufficient"
INVALID = "invalid"


def iso(moment: datetime) -> str:
    """A UTC instant as ``2026-07-04T21:00:00Z``."""

    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Reason:
    code: str
    values: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Result:
    metric: str
    value: float | None
    unit: str
    status: str
    reasons: tuple[Reason, ...]
    inputs: tuple[str, ...]
    calculation_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "value": self.value,
            "unit": self.unit,
            "status": self.status,
            "reasons": [{"code": r.code, "values": dict(r.values)} for r in self.reasons],
            "inputs": list(self.inputs),
            "calculation_version": self.calculation_version,
        }


@dataclass(frozen=True)
class Measurement:
    """One offline result: where it sits on the process timeline (``at``, the sample's
    collection time) and from when it may be used (``available_at``). Never merged."""

    id: str
    at: datetime
    value: float
    unit: str
    available_at: datetime
    method: str = ""


@dataclass(frozen=True)
class Pool:
    """A pool's volume and concentration, as measured."""

    id: str
    volume: float
    volume_unit: str
    concentration: float
    concentration_unit: str
    method: str
    available_at: datetime


@dataclass(frozen=True)
class Online:
    """An online signal's recorded values, oldest first."""

    signal_id: str
    unit: str
    points: Sequence[tuple[datetime, float]]


def insufficient(metric: str, unit: str, version: str, *reasons: Reason) -> Result:
    return Result(metric, None, unit, INSUFFICIENT, tuple(reasons), (), version)


def invalid(metric: str, unit: str, version: str, reasons: Iterable[Reason]) -> Result:
    return Result(metric, None, unit, INVALID, tuple(reasons), (), version)


def available(items: Sequence[Any], as_of: datetime | None) -> tuple[list[Any], list[Reason]]:
    """The items whose result was available at ``as_of``, and the reason naming the others."""

    if as_of is None:
        return list(items), []
    used = [item for item in items if item.available_at <= as_of]
    pending = [item.id for item in items if item.available_at > as_of]
    if not pending:
        return used, []
    return used, [Reason("result_not_yet_available", {"ids": pending, "as_of": iso(as_of)})]


def value_problems(item_id: str, value: float, unit: str, expected: str) -> list[Reason]:
    """Why a value cannot be used: a unit other than the exact expected string (never converted),
    a value that is not finite, a negative value."""

    if unit != expected:
        return [Reason("wrong_unit", {"id": item_id, "unit": unit, "expected": expected})]
    if not math.isfinite(value):
        return [Reason("non_finite_value", {"id": item_id})]
    if value < 0:
        return [Reason("negative_value", {"id": item_id, "value": value})]
    return []
