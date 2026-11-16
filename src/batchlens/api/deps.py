"""Request dependencies: the runtime, the verified user, access checks and safe reads.

Every route needs a PlantCraft token with access to ``batchlens``
(``plantcraft_sdk.server.access``). Viewers read; editors may also correct a sample's time and
set the reference batch.
"""

from __future__ import annotations

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


def batch_or_404(rt: Runtime, batch_id: str) -> BatchRecord:
    found = rt.batches.get(batch_id)
    if found is None:
        raise HTTPException(status_code=404, detail=t("Batch not found."))
    return found
