"""Request dependencies: the runtime, the verified user, access checks and safe reads.

Every route needs a PlantCraft token with access to ``batchlens``
(``plantcraft_sdk.server.access``). Viewers read; editors may also correct a sample's time and
set the reference batch.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException
from plantcraft_sdk.server.access import Access, CurrentUser, runtime

from batchlens.api.runtime import Runtime
from batchlens.batches.models import BatchRecord
from batchlens.i18n import t

ACCESS = Access("BatchLens")
RuntimeDep = Annotated[Runtime, Depends(runtime)]
EditorUser = ACCESS.EditorUser
guarded = ACCESS.guarded

__all__ = ["CurrentUser", "EditorUser", "RuntimeDep", "guarded"]


def now() -> datetime:
    """The clock (tests set it)."""

    return datetime.now(UTC)


def horizon(record: BatchRecord, as_of: datetime | None) -> datetime | None:
    """The instant a view of ``record`` stops at. A batch still running may hold records dated
    ahead of the clock (the demo's live batch is generated whole): nothing later than now is
    shown, whatever was asked. A finished batch is shown as asked."""

    known = [phase.end for phase in record.phases]
    known += [result.result_available_at for result in record.results]
    known += [pool.result_available_at for pool in record.pools]
    moment = now()
    if not known or max(known) <= moment:
        return as_of
    return moment if as_of is None else min(as_of, moment)


def batch_or_404(rt: Runtime, batch_id: str) -> BatchRecord:
    found = rt.batches.get(batch_id)
    if found is None:
        raise HTTPException(status_code=404, detail=t("Batch not found."))
    return found
