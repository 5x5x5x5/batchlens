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

# What a batch is a batch of. A solution lot (a medium, a buffer) is a batch of its own kind:
# it is prepared, held, sampled and assayed like one, and product batches draw from it.
BATCH_KINDS = ("product", "medium", "buffer")
PHASE_KINDS = (
    "solution_prep",
    "solution_hold",
    "seed_n2",
    "seed_n1",
    "production_culture",
    "harvest",
    "protein_a_capture",
    "viral_inactivation",
    "cation_exchange",
    "anion_exchange",
    "viral_filtration",
    "ufdf",
)
POOLS = (
    "protein_a_load",
    "protein_a_eluate_cycle_1",
    "protein_a_eluate_cycle_2",
    "protein_a_eluate",
    "viral_inactivation_pool",
    "cation_exchange_pool",
    "anion_exchange_pool",
    "viral_filtrate",
    "drug_substance",
)


@dataclass(frozen=True)
class Batch:
    batch_id: str
    product: str
    # Ordinary batch context a person assigns: the batch others are compared with.
    is_reference: bool
    created_at: datetime
    provenance: str
    kind: str = "product"  # one of BATCH_KINDS; for a solution lot, ``product`` names the solution


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
class PoolLink:
    """Genealogy: material of one pool went into another. Several links into one pool are a
    merge; several out of one are a split."""

    link_id: str
    batch_id: str
    from_pool_id: str  # a pool measurement's id
    to_pool_id: str
    provenance: str


TRANSFER_KINDS = ("passage", "inoculation", "feed", "buffer")


@dataclass(frozen=True)
class Transfer:
    """Material moved from one asset into another between two instants, as it was recorded:
    a seed passage moved on, the production culture inoculated, a feed added, a buffer drawn by
    a purification step. The volume is
    the recorded one (a totaliser, a weight, a batch record entry), not read from a signal.
    ``from_lot_id`` names the solution lot drawn from; empty when the material is the batch's
    own."""

    transfer_id: str
    batch_id: str
    kind: str
    from_asset_id: str
    to_asset_id: str
    start: datetime
    end: datetime
    volume: float
    volume_unit: str
    from_lot_id: str
    provenance: str


@dataclass(frozen=True)
class Correction:
    """A change a person made to a record: the value before, the value after, who, when and
    why. The original is never lost."""

    correction_id: str
    batch_id: str
    record_id: str
    field: str
    old_value: str
    new_value: str
    reason: str
    corrected_by: str
    corrected_at: datetime


@dataclass(frozen=True)
class BatchRecord:
    """The aggregate: one batch and everything recorded about it, oldest first."""

    batch: Batch
    phases: tuple[PhaseExecution, ...]
    samples: tuple[Sample, ...]
    results: tuple[AssayResult, ...]
    pools: tuple[PoolMeasurement, ...]
    links: tuple[PoolLink, ...] = ()
    transfers: tuple[Transfer, ...] = ()

    def phase(self, kind: str) -> PhaseExecution | None:
        return next((phase for phase in self.phases if phase.kind == kind), None)
