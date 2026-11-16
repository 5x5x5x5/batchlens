"""A batch's metrics, computed on request from its records and the bioreactor's volume signal.

Nothing here is stored. Samples are scoped to the batch's production phase, results marked
invalid are left out, and ``as_of`` is passed on to every calculation.
"""

from __future__ import annotations

from datetime import datetime

from batchlens import calc
from batchlens.batches.models import BatchRecord
from batchlens.calc.mass import HARVEST_VERSION

METRICS = (
    "ivcd",
    "qp",
    "harvest_mass",
    "protein_a_load_mass",
    "protein_a_eluate_mass",
    "harvest_to_load_yield",
    "protein_a_recovery",
)


def measurements(record: BatchRecord, analyte: str) -> list[calc.Measurement]:
    """The valid results of one analyte on the production phase's samples, in collection order."""

    culture = record.phase("production_culture")
    collected = {
        sample.sample_id: sample.collected_at
        for sample in record.samples
        if culture is not None and sample.phase_id == culture.phase_id
    }
    found = [
        calc.Measurement(
            result.result_id,
            collected[result.sample_id],
            result.value,
            result.unit,
            result.result_available_at,
            result.method,
        )
        for result in record.results
        if result.analyte == analyte
        and result.validity == "valid"
        and result.sample_id in collected
    ]
    return sorted(found, key=lambda m: m.at)


def _pool(record: BatchRecord, name: str) -> calc.Pool | None:
    for pool in record.pools:
        if pool.pool == name:
            return calc.Pool(
                pool.measurement_id,
                pool.volume,
                pool.volume_unit,
                pool.concentration,
                pool.concentration_unit,
                pool.method,
                pool.result_available_at,
            )
    return None


def batch_metrics(
    record: BatchRecord, volume: calc.Online | calc.Reason, *, as_of: datetime | None = None
) -> list[calc.Result]:
    """Every metric of ``METRICS``, in that order. ``volume`` is the bioreactor's volume signal
    over the production phase, or the reason it could not be read."""

    vcd, titer = measurements(record, "vcd"), measurements(record, "titer")
    culture = record.phase("production_culture")
    if culture is None:
        harvest = calc.insufficient(
            "harvest_mass", "g", HARVEST_VERSION, calc.Reason("phase_missing")
        )
    elif isinstance(volume, calc.Reason):
        harvest = calc.insufficient("harvest_mass", "g", HARVEST_VERSION, volume)
    else:
        harvest = calc.harvest_mass(
            titer, volume, phase_start=culture.start, phase_end=culture.end, as_of=as_of
        )
    load = calc.pool_mass("protein_a_load_mass", _pool(record, "protein_a_load"), as_of=as_of)
    eluate = calc.pool_mass("protein_a_eluate_mass", _pool(record, "protein_a_eluate"), as_of=as_of)
    return [
        calc.ivcd(vcd, as_of=as_of),
        calc.specific_productivity(vcd, titer, as_of=as_of),
        harvest,
        load,
        eluate,
        calc.ratio_percent("harvest_to_load_yield", load, harvest),
        calc.ratio_percent("protein_a_recovery", eluate, load),
    ]
