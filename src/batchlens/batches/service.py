"""The batches' rules, without HTTP. The routers call these; only this module touches the store.

This slice only reads batches and loads the seeded demo: there is no create, change or delete
route yet, so there is nothing to audit.
"""

from __future__ import annotations

from batchlens.batches.models import Batch, BatchRecord, PhaseExecution
from batchlens.batches.store import BatchStore


class BatchService:
    def __init__(self, store: BatchStore):
        self.store = store

    def summaries(self) -> list[tuple[Batch, tuple[PhaseExecution, ...]]]:
        return self.store.summaries()

    def get(self, batch_id: str) -> BatchRecord | None:
        return self.store.get(batch_id)

    def reference(self) -> BatchRecord | None:
        found = self.store.reference_id()
        return self.store.get(found) if found else None

    def save(self, record: BatchRecord) -> None:
        self.store.save(record)
