"""What the pages read from PlantCraft, as the signed-in person: the name of an asset, the
bioreactor's volume near the harvest sample, and its online signals over a production phase.

Every read is scoped to a phase execution's asset and time window, and cut at ``as_of``. A
missing asset, signal or series is an answer (a ``calc.Reason`` naming what was not found), not
an error: a live PlantCraft may not hold the synthetic plant at all. A refused token (401, 403)
still answers as one.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, TypeVar

from fastapi import HTTPException
from plantcraft_sdk.client import PlantCraftClient
from plantcraft_sdk.utc import utc_iso

from batchlens import calc
from batchlens.api.deps import guarded
from batchlens.batches.models import PhaseExecution

T = TypeVar("T")
# The bioreactor's signal roles the pages show, in this order.
ROLES = ("ph", "do", "temperature", "volume")
TREND_POINTS = 300


def _read(read: Callable[[], T], missing: calc.Reason) -> T | calc.Reason:
    """A PlantCraft read, or why it has no answer: ``missing`` for a 404, the same values under
    ``series_unreadable`` when the data source failed (502)."""

    try:
        return guarded(read, service=False)
    except HTTPException as exc:
        if exc.status_code == 404:
            return missing
        if exc.status_code == 502:
            return calc.Reason("series_unreadable", {**missing.values, "detail": str(exc.detail)})
        raise


def _instant(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def time_zone(client: PlantCraftClient) -> str:
    """The installation's zone, in which the pages show every instant (UTC if it cannot be read)."""

    found = _read(client.installation_time_zone, calc.Reason("installation_not_found"))
    return "UTC" if isinstance(found, calc.Reason) else found


def asset(client: PlantCraftClient, asset_id: str) -> dict[str, Any] | calc.Reason:
    return _read(
        lambda: client.asset(asset_id), calc.Reason("asset_not_found", {"asset_id": asset_id})
    )


def asset_names(client: PlantCraftClient, asset_ids: set[str]) -> dict[str, str | None]:
    """Each asset's name in PlantCraft, or none when the person sees no such asset."""

    found = {asset_id: asset(client, asset_id) for asset_id in sorted(asset_ids)}
    return {
        asset_id: None if isinstance(item, calc.Reason) else item.get("name") or asset_id
        for asset_id, item in found.items()
    }


def _signal(
    client: PlantCraftClient, found: dict[str, Any] | calc.Reason, asset_id: str, role: str
) -> dict[str, Any] | calc.Reason:
    """The signal bound to ``role`` on the asset PlantCraft answered (its own role map)."""

    if isinstance(found, calc.Reason):
        return found
    missing = calc.Reason("signal_not_found", {"asset_id": asset_id, "role": role})
    signal_id = (found.get("signals") or {}).get(role)
    if not signal_id:
        return missing
    return _read(lambda: client.signal(signal_id), missing)


def volume(
    client: PlantCraftClient, culture: PhaseExecution | None, as_of: datetime | None
) -> calc.Online | calc.Reason:
    """The bioreactor's recorded volume over the end of the production phase: the only stretch
    in which ``calc.harvest_mass`` accepts a titer sample."""

    if culture is None:
        return calc.Reason("phase_missing")
    signal = _signal(client, asset(client, culture.asset_id), culture.asset_id, "volume")
    if isinstance(signal, calc.Reason):
        return signal
    reach = timedelta(hours=calc.HARVEST_TITER_WINDOW_HOURS, seconds=calc.VOLUME_MAX_AGE_SECONDS)
    start = max(culture.start, culture.end - reach)
    end = culture.end if as_of is None else min(culture.end, as_of)
    points: list[tuple[datetime, float]] = []
    if start < end:
        missing = calc.Reason("signal_not_found", {"asset_id": culture.asset_id, "role": "volume"})
        series = _read(lambda: client.series(signal["id"], start, end), missing)
        if isinstance(series, calc.Reason):
            return series
        points = [
            (_instant(stamp), float(value))
            for stamp, value in zip(series["t"], series["v"])
            if isinstance(value, int | float) and not isinstance(value, bool)
        ]
    return calc.Online(signal["id"], signal.get("unit") or "", points)


def volume_between(
    client: PlantCraftClient, asset_id: str, start: datetime, end: datetime
) -> calc.Online | calc.Reason:
    """The recorded values of an asset's volume signal between two instants, or why not."""

    signal = _signal(client, asset(client, asset_id), asset_id, "volume")
    if isinstance(signal, calc.Reason):
        return signal
    points: list[tuple[datetime, float]] = []
    if start < end:
        missing = calc.Reason("signal_not_found", {"asset_id": asset_id, "role": "volume"})
        series = _read(lambda: client.series(signal["id"], start, end), missing)
        if isinstance(series, calc.Reason):
            return series
        points = [
            (_instant(stamp), float(value))
            for stamp, value in zip(series["t"], series["v"])
            if isinstance(value, int | float) and not isinstance(value, bool)
        ]
    return calc.Online(signal["id"], signal.get("unit") or "", points)


def _step_means(
    stamps: list[str], values: list[Any], start: datetime, end: datetime, step: int
) -> tuple[list[str], list[float | None]]:
    """One mean per ``step`` seconds from ``start``, over the values recorded in that step; a
    step in which nothing was recorded has no value, so a gap stays a gap."""

    count = max(1, math.ceil((end - start).total_seconds() / step))
    sums, seen = [0.0] * count, [0] * count
    for stamp, value in zip(stamps, values):
        if not isinstance(value, int | float) or isinstance(value, bool):
            continue
        if not math.isfinite(value):
            continue  # never averaged in, never sent on
        index = int((_instant(stamp) - start).total_seconds() // step)
        if 0 <= index < count:
            sums[index] += value
            seen[index] += 1
    marks = [utc_iso(start + timedelta(seconds=index * step)) for index in range(count)]
    return marks, [sums[i] / seen[i] if seen[i] else None for i in range(count)]


def trends(
    client: PlantCraftClient, culture: PhaseExecution, as_of: datetime | None
) -> tuple[int, list[dict[str, Any]]]:
    """The step in seconds and, for each role of ``ROLES``, the mean of the signal's recorded
    values in each step over the production phase (cut at ``as_of``), or why there are none."""

    end = culture.end if as_of is None else min(culture.end, as_of)
    span = max(0.0, (end - culture.start).total_seconds())
    step = max(600, 60 * math.ceil(span / TREND_POINTS / 60))
    found = asset(client, culture.asset_id)
    signals = {role: _signal(client, found, culture.asset_id, role) for role in ROLES}
    ids = [item["id"] for item in signals.values() if not isinstance(item, calc.Reason)]
    series: dict[str, dict[str, Any]] = {}
    failed: dict[str, calc.Reason] = {}
    if ids and span > 0:
        answer = _read(
            # Recorded values, not PlantCraft's stepped means: those hold the last value across
            # a gap, and a trend must not show hours that were never recorded.
            lambda: client.series_many(ids, culture.start, end),
            calc.Reason("signal_not_found", {"asset_id": culture.asset_id}),
        )
        if isinstance(answer, calc.Reason):
            failed = dict.fromkeys(ids, answer)
        else:
            series = {item["signal"]: item for item in answer["series"]}
            failed = {
                error["signal"]: calc.Reason(
                    "signal_not_found" if error.get("status") == 404 else "series_unreadable",
                    {"signal_id": error["signal"], "detail": str(error.get("detail") or "")},
                )
                for error in answer["errors"]
            }
    rows = []
    for role, signal in signals.items():
        reason = signal if isinstance(signal, calc.Reason) else failed.get(signal["id"])
        if reason is None and span <= 0:
            reason = calc.Reason("phase_not_started", {})
        row = {"role": role, "signal_id": None, "name": None, "unit": None, "t": [], "v": []}
        if not isinstance(signal, calc.Reason):
            row.update(signal_id=signal["id"], name=signal.get("name"), unit=signal.get("unit"))
        if reason is None:
            item = series.get(signal["id"], {"t": [], "v": []})
            stamps, values = _step_means(item["t"], item["v"], culture.start, end, step)
            row.update(t=stamps, v=values)
        rows.append(
            {
                **row,
                "status": calc.USABLE if reason is None else calc.INSUFFICIENT,
                "reasons": []
                if reason is None
                else [{"code": reason.code, "values": dict(reason.values)}],
            }
        )
    return step, rows
