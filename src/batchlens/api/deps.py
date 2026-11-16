"""Request dependencies: the runtime, the verified user, access checks and safe reads.

Every route needs a PlantCraft token with access to ``batchlens``
(``plantcraft_sdk.server.access``). Viewers read the notes; editors write, change and delete them.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException
from plantcraft_sdk.server.access import Access, CurrentUser, runtime

from batchlens.api.runtime import Runtime
from batchlens.i18n import t

ACCESS = Access("Batchlens")
RuntimeDep = Annotated[Runtime, Depends(runtime)]
EditorUser = ACCESS.EditorUser
guarded = ACCESS.guarded

__all__ = ["CurrentUser", "EditorUser", "RuntimeDep", "guarded"]


def note_or_404(rt: Runtime, note_id: str) -> dict[str, Any]:
    found = rt.notes.get(note_id)
    if found is None:
        raise HTTPException(status_code=404, detail=t("Note not found."))
    return found
