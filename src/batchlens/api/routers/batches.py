"""HTTP routes: the batches. Reading, and the two things an editor may change. Records come from the app's own store through the
service; assets, signals and series come from PlantCraft as the signed-in person
(``api/plant.py``); every number is computed by ``analysis`` and ``calc`` on request."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from plantcraft_sdk.utc import utc_iso

from batchlens.analysis.downstream import downstream
from batchlens.analysis.metrics import batch_metrics, beside_reference, findings
from batchlens.api import plant
from batchlens.api.deps import CurrentUser, EditorUser, RuntimeDep, batch_or_404
from batchlens.batches.drafts import SampleTimeCorrection
from batchlens.batches.service import NotFound, RuleBroken
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
def get_batch(batch_id: str, rt: RuntimeDep, user: CurrentUser, as_of: AsOf) -> dict[str, Any]:
    record = batch_or_404(rt, batch_id)
    client = rt.user_client(user)
    names = plant.asset_names(client, {phase.asset_id for phase in record.phases})
    # From the start of the batch to the last moment anything about it became known: the span
    # an as-of view moves over.
    known = [phase.end for phase in record.phases]
    known += [result.result_available_at for result in record.results]
    known += [pool.result_available_at for pool in record.pools]
    phases = []
    for phase in record.phases:
        if as_of is not None and phase.start > as_of:
            continue  # it had not begun
        row = {**_plain(phase), "asset_name": names.get(phase.asset_id)}
        if as_of is not None and phase.end > as_of:
            row["end"] = None  # in progress: its end was not known yet
        phases.append(row)
    return {
        "time_zone": plant.time_zone(client),
        "as_of": _stamp(as_of),
        "timeline": {
            "start": _stamp(min((phase.start for phase in record.phases), default=None)),
            "end": _stamp(max(known, default=None)),
        },
        "batch": _plain(record.batch),
        "phases": phases,
        "pools": [
            _plain(pool)
            for pool in record.pools
            if as_of is None or pool.result_available_at <= as_of
        ],
        # What people changed, with the values they replaced.
        "corrections": [_plain(item) for item in rt.batches.corrections(batch_id)],
    }


@router.get("/batches/{batch_id}/samples")
def batch_samples(
    batch_id: str,
    rt: RuntimeDep,
    _user: CurrentUser,
    as_of: AsOf,
    align_to: Annotated[
        str | None,
        Query(
            max_length=64,
            description="Another batch: each sample also gets the instant of the same culture "
            "age on that batch's timeline, to lay one batch over the other.",
        ),
    ] = None,
) -> dict[str, Any]:
    record = batch_or_404(rt, batch_id)
    culture = record.phase("production_culture")
    other = batch_or_404(rt, align_to).phase("production_culture") if align_to else None
    corrected = {item.record_id for item in rt.batches.corrections(batch_id)}
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
        # Culture age: time since the start of the batch's production phase.
        age = sample.collected_at - culture.start if culture else None
        samples.append(
            {
                **_plain(sample),
                "corrected": sample.sample_id in corrected,
                "culture_day": age.total_seconds() / 86400 if age is not None else None,
                "aligned_at": _stamp(other.start + age) if other and age is not None else None,
                "results": sorted(results, key=lambda r: r["analyte"]),
            }
        )
    return {
        "batch_id": batch_id,
        "as_of": _stamp(as_of),
        "aligned_to": align_to,
        "samples": samples,
    }


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
    results = metrics_of(record)
    reference_results = metrics_of(reference) if reference else None

    def harvest_of(found):
        return next(item for item in found if item.metric == "harvest_mass")

    beside = (
        downstream(reference, harvest_of(reference_results), as_of=as_of) if reference else None
    )
    train = downstream(record, harvest_of(results), as_of=as_of, reference=beside)
    train["overall_reference"] = beside["overall"]["value"] if beside else None
    return {
        "batch_id": batch_id,
        "as_of": _stamp(as_of),
        "reference_batch_id": reference.batch.batch_id if reference else None,
        "metrics": beside_reference(results, reference_results),
        "findings": findings(record, reference, results, reference_results, as_of=as_of),
        # The purification train: step yields, recovery from harvest, pool genealogy.
        "downstream": train,
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


# What an editor may change -------------------------------------------------------------------


@router.patch("/batches/{batch_id}/samples/{sample_id}")
def correct_sample(
    batch_id: str, sample_id: str, draft: SampleTimeCorrection, rt: RuntimeDep, user: EditorUser
) -> dict[str, Any]:
    """Correct a sample's collection time. The value it replaces is kept (``corrections`` on
    the batch) and the change is audited in PlantCraft."""

    try:
        correction = rt.batches.correct_sample_time(
            batch_id, sample_id, draft.instant, draft.reason, user.username
        )
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=t("Sample not found.")) from exc
    except RuleBroken as exc:
        if exc.code == "outside_phase":
            detail = t("The collection time must lie inside the sample's phase execution.")
        else:
            detail = t("The collection time must be before the sample's results were reported.")
        raise HTTPException(status_code=422, detail=detail) from exc
    rt.audit(
        user,
        "sample.corrected",
        sample_id,
        {
            "batch": batch_id,
            "field": correction.field,
            "old": correction.old_value,
            "new": correction.new_value,
            "reason": correction.reason,
        },
    )
    return {
        "sample_id": sample_id,
        "collected_at": correction.new_value,
        "correction": _plain(correction),
    }


@router.put("/batches/{batch_id}/reference")
def set_reference(batch_id: str, rt: RuntimeDep, user: EditorUser) -> dict[str, Any]:
    """Make this batch the one the others are compared with."""

    try:
        previous = rt.batches.set_reference(batch_id)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=t("Batch not found.")) from exc
    if previous != batch_id:
        rt.audit(user, "batch.reference_set", batch_id, {"previous": previous})
    return {"reference_batch_id": batch_id}
