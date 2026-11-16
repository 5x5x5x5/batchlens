"""A batch and what happened to it, as the app records it.

Four things that are not each other: a batch is not an asset (it is a window on shared
equipment); a phase execution is what happened on an asset between two instants, not a recipe;
an assay result is not an online sample; the time a sample was collected is not the time its
result became available. Every instant is UTC, every quantity carries its unit, and every row
says where it came from (``provenance``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

PHASE_KINDS = ("production_culture", "harvest", "protein_a_capture")
POOLS = ("protein_a_load", "protein_a_eluate")


@dataclass(frozen=True)
class Batch:
    batch_id: str
    product: str
    # Ordinary batch context a person assigns: the batch others are compared with.
    is_reference: bool
    created_at: datetime
    provenance: str


@dataclass(frozen=True)
class PhaseExecution:
    phase_id: str
    batch_id: str
    kind: str
    asset_id: str  # PlantCraft's asset id; the asset itself stays there
    start: datetime
    end: datetime
    provenance: str


@dataclass(frozen=True)
class Sample:
    sample_id: str
    batch_id: str
    phase_id: str
    collected_at: datetime
    provenance: str


@dataclass(frozen=True)
class AssayResult:
    result_id: str
    sample_id: str
    analyte: str
    value: float
    unit: str
    method: str
    result_available_at: datetime
    validity: str  # "valid" or "invalid"
    provenance: str


@dataclass(frozen=True)
class PoolMeasurement:
    measurement_id: str
    batch_id: str
    phase_id: str
    pool: str
    volume: float
    volume_unit: str
    concentration: float
    concentration_unit: str
    method: str
    measured_at: datetime
    result_available_at: datetime
    provenance: str


@dataclass(frozen=True)
class BatchRecord:
    """The aggregate: one batch and everything recorded about it, oldest first."""

    batch: Batch
    phases: tuple[PhaseExecution, ...]
    samples: tuple[Sample, ...]
    results: tuple[AssayResult, ...]
    pools: tuple[PoolMeasurement, ...]

    def phase(self, kind: str) -> PhaseExecution | None:
        return next((phase for phase in self.phases if phase.kind == kind), None)
