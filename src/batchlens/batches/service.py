"""The batches' rules, without HTTP. The routers call these; only this module touches the store.

Batches are loaded by the seed. A person may change three things: a sample's collection time
(a correction, kept with the value it replaced), which batch is the reference, and which
batches are comparable. The router
audits each change in PlantCraft.
"""

from __future__ import annotations

from datetime import datetime

from batchlens.batches.models import Batch, BatchRecord, Correction, PhaseExecution
from batchlens.batches.store import BatchStore


class NotFound(LookupError):
    """No such batch or sample."""


class RuleBroken(ValueError):
    """The change breaks a rule of the object; ``code`` says which."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


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

    def corrections(self, batch_id: str) -> list[Correction]:
        return self.store.corrections(batch_id)

    def correct_sample_time(
        self, batch_id: str, sample_id: str, collected_at: datetime, reason: str, by: str
    ) -> Correction:
        """A sample's collection time, corrected. It must stay inside the phase execution the
        sample belongs to, and before each of the sample's own results became available."""

        record = self.store.get(batch_id)
        samples = record.samples if record else ()
        sample = next((item for item in samples if item.sample_id == sample_id), None)
        if record is None or sample is None:
            raise NotFound(sample_id)
        phase = next((item for item in record.phases if item.phase_id == sample.phase_id), None)
        if phase is None:
            raise NotFound(sample_id)
        if collected_at == sample.collected_at:
            raise RuleBroken("unchanged")
        if not phase.start <= collected_at <= phase.end:
            raise RuleBroken("outside_phase")
        reported = [r.result_available_at for r in record.results if r.sample_id == sample_id]
        if reported and collected_at >= min(reported):
            raise RuleBroken("after_result")
        try:
            return self.store.correct_sample_time(batch_id, sample_id, collected_at, reason, by)
        except LookupError as exc:  # the sample went away between the check and the write
            raise NotFound(sample_id) from exc

    def set_reference(self, batch_id: str) -> str | None:
        """Make the batch the reference; answers the previous reference's id (the batch's own
        id when it already was, and nothing changed)."""

        if self.store.get(batch_id) is None:
            raise NotFound(batch_id)
        previous = self.store.reference_id()
        if previous != batch_id:
            self.store.set_reference(batch_id)
        return previous

    def comparable_ids(self) -> list[str]:
        return self.store.comparable_ids()

    def set_comparable(self, batch_id: str, comparable: bool) -> bool:
        """Put the batch in the set of comparable batches, or take it out; answers whether
        that changed anything."""

        if self.store.get(batch_id) is None:
            raise NotFound(batch_id)
        if (batch_id in self.store.comparable_ids()) == comparable:
            return False
        self.store.set_comparable(batch_id, comparable)
        return True
