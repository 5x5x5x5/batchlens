"""HTTP routes: the batches, read only. Records come from the app's own store through the
service; assets, signals and series come from PlantCraft as the signed-in person
(``api/plant.py``); every number is computed by ``analysis`` and ``calc`` on request."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from plantcraft_sdk.utc import utc_iso

from batchlens.analysis.metrics import batch_metrics, beside_reference
from batchlens.api import plant
from batchlens.api.deps import CurrentUser, RuntimeDep, batch_or_404
from batchlens.i18n import t

router = APIRouter(prefix="/api", tags=["batches"])


def _as_of(
    as_of: Annotated[
        str | None,
        Query(
            max_length=40,
            description="Answer with only what was collected and available at this instant "
            "(ISO 8601; without an offset it is UTC).",
        ),
    ] = None,
) -> datetime | None:
    if as_of is None:
        return None
    try:
        moment = datetime.fromisoformat(as_of.strip().replace("Z", "+00:00"))
        # In UTC from here on. An offset can push a valid text outside the years a datetime
        # holds (0001-01-01T00:00+05:00): that is a bad as_of, not a server error.
        return moment.astimezone(UTC) if moment.tzinfo else moment.replace(tzinfo=UTC)
    except (ValueError, OverflowError) as exc:
        detail = t("as_of is an ISO 8601 time, like 2026-07-06T06:00:00Z.")
        raise HTTPException(status_code=422, detail=detail) from exc


AsOf = Annotated[datetime | None, Depends(_as_of)]


def _plain(row: Any) -> dict[str, Any]:
    """A record as JSON: every instant as PlantCraft writes them (UTC, ``...Z``)."""

    return {
        key: utc_iso(value) if isinstance(value, datetime) else value
        for key, value in asdict(row).items()
    }


def _stamp(moment: datetime | None) -> str | None:
    return utc_iso(moment) if moment is not None else None


@router.get("/batches")
def list_batches(rt: RuntimeDep, user: CurrentUser) -> dict[str, Any]:
    client = rt.user_client(user)
    summaries = rt.batches.summaries()
    cultures = {
        batch.batch_id: next((p for p in phases if p.kind == "production_culture"), None)
        for batch, phases in summaries
    }
    names = plant.asset_names(client, {p.asset_id for p in cultures.values() if p is not None})
    rows = []
    for batch, phases in summaries:
        culture = cultures[batch.batch_id]
        rows.append(
            {
                **_plain(batch),
                # The batch's window: from its first phase execution to the end of its last.
                "start": _stamp(min((p.start for p in phases), default=None)),
                "end": _stamp(max((p.end for p in phases), default=None)),
                "asset_id": culture.asset_id if culture else None,
                "asset_name": names.get(culture.asset_id) if culture else None,
            }
        )
    return {"time_zone": plant.time_zone(client), "batches": rows}


@router.get("/batches/{batch_id}")
def get_batch(batch_id: str, rt: RuntimeDep, user: CurrentUser) -> dict[str, Any]:
    record = batch_or_404(rt, batch_id)
    client = rt.user_client(user)
    names = plant.asset_names(client, {phase.asset_id for phase in record.phases})
    return {
        "time_zone": plant.time_zone(client),
        "batch": _plain(record.batch),
        "phases": [
            {**_plain(phase), "asset_name": names.get(phase.asset_id)} for phase in record.phases
        ],
        "pools": [_plain(pool) for pool in record.pools],
    }


@router.get("/batches/{batch_id}/samples")
def batch_samples(batch_id: str, rt: RuntimeDep, _user: CurrentUser, as_of: AsOf) -> dict[str, Any]:
    record = batch_or_404(rt, batch_id)
    samples = []
    for sample in record.samples:
        if as_of is not None and sample.collected_at > as_of:
            continue
        results = [
            _plain(result)
            for result in record.results
            if result.sample_id == sample.sample_id
            and (as_of is None or result.result_available_at <= as_of)
        ]
        samples.append({**_plain(sample), "results": sorted(results, key=lambda r: r["analyte"])})
    return {"batch_id": batch_id, "as_of": _stamp(as_of), "samples": samples}


@router.get("/batches/{batch_id}/metrics")
def batch_metrics_route(
    batch_id: str, rt: RuntimeDep, user: CurrentUser, as_of: AsOf
) -> dict[str, Any]:
    record = batch_or_404(rt, batch_id)
    client = rt.user_client(user)

    def metrics_of(item):
        volume = plant.volume(client, item.phase("production_culture"), as_of)
        return batch_metrics(item, volume, as_of=as_of)

    reference = rt.batches.reference()
    if reference is not None and reference.batch.batch_id == batch_id:
        reference = None  # the reference batch is not compared with itself
    return {
        "batch_id": batch_id,
        "as_of": _stamp(as_of),
        "reference_batch_id": reference.batch.batch_id if reference else None,
        "metrics": beside_reference(
            metrics_of(record), metrics_of(reference) if reference else None
        ),
    }


@router.get("/batches/{batch_id}/trends")
def batch_trends(batch_id: str, rt: RuntimeDep, user: CurrentUser, as_of: AsOf) -> dict[str, Any]:
    record = batch_or_404(rt, batch_id)
    culture = record.phase("production_culture")
    answer: dict[str, Any] = {"batch_id": batch_id, "as_of": _stamp(as_of)}
    if culture is None:
        return {
            **answer,
            "asset_id": None,
            "start": None,
            "end": None,
            "step_seconds": None,
            "signals": [],
        }
    step, signals = plant.trends(rt.user_client(user), culture, as_of)
    return {
        **answer,
        "asset_id": culture.asset_id,
        "start": utc_iso(culture.start),
        "end": utc_iso(culture.end),
        "step_seconds": step,
        "signals": signals,
    }
