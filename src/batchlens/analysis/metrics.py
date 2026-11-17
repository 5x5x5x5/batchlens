"""A batch's metrics, computed on request from its records and the bioreactor's volume signal.

Nothing here is stored. Samples are scoped to one phase (a seed passage's growth rate rests
on that passage's counts only, everything else on the production phase's), results marked
invalid are left out, and ``as_of`` is passed on to every calculation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from batchlens import calc
from batchlens.analysis.transfers import hours_since_feed
from batchlens.batches.models import BatchRecord, PoolMeasurement
from batchlens.calc.comparison import DIVERGENCE_VERSION
from batchlens.calc.mass import HARVEST_VERSION

METRICS = (
    "seed_n2_growth_rate",
    "seed_n1_growth_rate",
    "inoculation_density",
    "ivcd",
    "qp",
    "harvest_mass",
    "protein_a_load_mass",
    "protein_a_eluate_mass",
    "harvest_to_load_yield",
    "protein_a_recovery",
)


def measurements(
    record: BatchRecord,
    analyte: str,
    as_of: datetime | None = None,
    kind: str = "production_culture",
) -> list[calc.Measurement]:
    """The valid results of one analyte on the samples of one phase (the production culture
    unless ``kind`` names another), in collection order.
    With ``as_of``, a sample collected later does not exist yet: it is left out altogether,
    not reported as a result that is still pending."""

    culture = record.phase(kind)
    collected = {
        sample.sample_id: sample.collected_at
        for sample in record.samples
        if culture is not None
        and sample.phase_id == culture.phase_id
        and (as_of is None or sample.collected_at <= as_of)
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


def _pool(record: BatchRecord, name: str, as_of: datetime | None = None) -> calc.Pool | None:
    """The pool's measurement; with ``as_of``, none if it had not been measured yet."""

    for pool in record.pools:
        if pool.pool == name and (as_of is None or pool.measured_at <= as_of):
            return as_calc_pool(pool)
    return None


def as_calc_pool(pool: PoolMeasurement) -> calc.Pool:
    """One pool measurement as the calculations take it."""

    return calc.Pool(
        pool.measurement_id,
        pool.volume,
        pool.volume_unit,
        pool.concentration,
        pool.concentration_unit,
        pool.method,
        pool.result_available_at,
    )


def batch_metrics(
    record: BatchRecord, volume: calc.Online | calc.Reason, *, as_of: datetime | None = None
) -> list[calc.Result]:
    """Every metric of ``METRICS``, in that order. ``volume`` is the bioreactor's volume signal
    over the production phase, or the reason it could not be read."""

    vcd, titer = measurements(record, "vcd", as_of), measurements(record, "titer", as_of)
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
    load = calc.pool_mass(
        "protein_a_load_mass", _pool(record, "protein_a_load", as_of), as_of=as_of
    )
    eluate = calc.pool_mass(
        "protein_a_eluate_mass", _pool(record, "protein_a_eluate", as_of), as_of=as_of
    )
    if culture is None:
        started = calc.insufficient(
            "inoculation_density",
            calc.culture.VCD_UNIT,
            calc.culture.INOCULATION_VERSION,
            calc.Reason("phase_missing"),
        )
    else:
        started = calc.inoculation_density(vcd, phase_start=culture.start, as_of=as_of)
    return [
        # A batch with no record of a seed passage has no counts for it: insufficient.
        *(
            calc.growth_rate(
                f"{kind}_growth_rate", measurements(record, "vcd", as_of, kind), as_of=as_of
            )
            for kind in ("seed_n2", "seed_n1")
        ),
        started,
        calc.ivcd(vcd, as_of=as_of),
        calc.specific_productivity(vcd, titer, as_of=as_of),
        harvest,
        load,
        eluate,
        calc.ratio_percent("harvest_to_load_yield", load, harvest),
        calc.ratio_percent("protein_a_recovery", eluate, load),
    ]


def beside_reference(
    results: list[calc.Result],
    reference: list[calc.Result] | None,
    comparable: list[list[calc.Result]] | None = None,
) -> list[dict[str, Any]]:
    """Each result as plain data, with the reference batch's value of the same metric and the
    difference (this batch minus the reference) when both have a value, and where it sits
    among the comparable batches' (``calc.set_position``; none when no batch is comparable).
    ``comparable`` holds one list of results per comparable batch."""

    by_metric = {result.metric: result for result in reference or []}
    others = [{result.metric: result for result in batch} for batch in comparable or []]
    found = []
    for result in results:
        other = by_metric.get(result.metric)
        both = other is not None and result.value is not None and other.value is not None
        found.append(
            {
                **result.to_dict(),
                "reference": {"value": other.value, "status": other.status} if other else None,
                "difference": result.value - other.value if both else None,
                "comparable": calc.set_position(
                    result, [batch[result.metric] for batch in others if result.metric in batch]
                ).to_dict()
                if others
                else None,
            }
        )
    return found


# Each step recovery a finding is raised for, and the mass that comes out of that step.
STEPS = {
    "harvest_to_load_yield": "protein_a_load_mass",
    "protein_a_recovery": "protein_a_eluate_mass",
}


def _consequence(
    metric: str, results: dict[str, calc.Result], reference: dict[str, calc.Result]
) -> dict[str, Any]:
    """A mass of this batch against the reference batch's, with the status of this batch's."""

    own, other = results[metric], reference[metric]
    both = own.value is not None and other.value is not None
    return {
        "metric": metric,
        "unit": own.unit,
        "status": own.status,
        "value": own.value,
        "reference": other.value,
        "difference": own.value - other.value if both else None,
    }


def sample_evidence(
    record: BatchRecord,
    reference: BatchRecord,
    culture_start: datetime,
    pairs: list[tuple[str, str, str]],
    as_of: datetime | None,
) -> list[dict[str, Any]]:
    """Every result of the samples a divergence rests on, beside the reference sample's result
    of the same analyte: numbers to read, with nothing concluded from them."""

    def usable(batch: BatchRecord) -> dict[str, Any]:
        return {
            result.result_id: result
            for result in batch.results
            if result.validity == "valid" and (as_of is None or result.result_available_at <= as_of)
        }

    own, other = usable(record), usable(reference)
    collected = {sample.sample_id: sample.collected_at for sample in record.samples}
    reference_collected = {s.sample_id: s.collected_at for s in reference.samples}
    groups = []
    for at, result_id, reference_result_id in pairs:
        sample_id, reference_sample_id = (
            own[result_id].sample_id,
            other[reference_result_id].sample_id,
        )
        beside = {r.analyte: r for r in other.values() if r.sample_id == reference_sample_id}
        rows = []
        for result in sorted(own.values(), key=lambda r: r.analyte):
            if result.sample_id != sample_id:
                continue
            match = beside.get(result.analyte)
            same_unit = match is not None and match.unit == result.unit
            rows.append(
                {
                    "analyte": result.analyte,
                    "unit": result.unit,
                    "result_id": result.result_id,
                    "value": result.value,
                    "reference_result_id": match.result_id if match else None,
                    "reference_value": match.value if same_unit else None,
                    "difference": result.value - match.value if same_unit else None,
                }
            )
        groups.append(
            {
                "at": at,
                "sample_id": sample_id,
                "reference_sample_id": reference_sample_id,
                "culture_day": (collected[sample_id] - culture_start).total_seconds() / 86400,
                # Glucose and lactate swing with every feed: how long after one each sample
                # was taken says whether their difference means anything.
                "hours_since_feed": hours_since_feed(record, collected[sample_id]),
                "reference_hours_since_feed": hours_since_feed(
                    reference, reference_collected[reference_sample_id]
                ),
                "results": rows,
            }
        )
    return groups


def findings(
    record: BatchRecord,
    reference: BatchRecord | None,
    results: list[calc.Result],
    reference_results: list[calc.Result] | None,
    *,
    as_of: datetime | None = None,
) -> list[dict[str, Any]]:
    """What stands out against the reference batch. Always the same findings in the same
    order, each in separate parts:

    - ``observation``: a ``calc`` result with the ids it rests on: where the titer left the
      reference's, whether the culture began at a lower density than the reference's, and
      for each step whether it recovered less than the reference's did;
    - ``consequence``: when something was observed, a product mass against the reference's
      (at harvest for the titer, out of the step for a recovery), with its own status;
    - ``evidence``: for a divergence, the other results of the same samples beside the
      reference's; for a low inoculation density, the last sample of the N-1 seed passage
      beside the reference's;
    - ``cause``: always none. The app observes and calculates; it attributes nothing.

    No findings without a reference batch to compare with.
    """

    if reference is None or reference_results is None:
        return []
    own = {result.metric: result for result in results}
    other = {result.metric: result for result in reference_results}
    culture, reference_culture = (item.phase("production_culture") for item in (record, reference))
    evidence: list[dict[str, Any]] = []
    if culture is None or reference_culture is None:
        divergence = calc.insufficient(
            "titer_divergence", "days", DIVERGENCE_VERSION, calc.Reason("phase_missing")
        )
    else:
        divergence = calc.titer_divergence(
            measurements(record, "titer", as_of),
            measurements(reference, "titer", as_of),
            batch_start=culture.start,
            reference_start=reference_culture.start,
            as_of=as_of,
        )
        if divergence.value is not None:
            seen = divergence.reasons[0].values
            pairs = [
                ("divergence", seen["result_id"], seen["reference_result_id"]),
                ("last_sample", divergence.inputs[-2], divergence.inputs[-1]),
            ]
            evidence = sample_evidence(record, reference, culture.start, pairs, as_of)
    found = [
        {
            "finding": "titer_divergence",
            "observation": divergence.to_dict(),
            "consequence": _consequence("harvest_mass", own, other)
            if divergence.value is not None
            else None,
            "evidence": evidence,
            "cause": None,
        }
    ]
    started = calc.inoculation_shortfall(own["inoculation_density"], other["inoculation_density"])
    last_counts = []
    if started.value is not None:
        # Beside it, what the passage before the culture ended at: each batch's last N-1 count
        # and the other results of that sample.
        for item in (record, reference):
            counts = measurements(item, "vcd", as_of, "seed_n1")
            counts = [m for m in counts if as_of is None or m.available_at <= as_of]
            last_counts.append(counts[-1].id if counts else None)
    passage = record.phase("seed_n1")
    found.append(
        {
            "finding": started.metric,
            "observation": started.to_dict(),
            "consequence": _consequence("harvest_mass", own, other)
            if started.value is not None
            else None,
            "evidence": sample_evidence(
                record, reference, passage.start, [("seed_n1_end", *last_counts)], as_of
            )
            if passage is not None and len(last_counts) == 2 and all(last_counts)
            else [],
            "cause": None,
        }
    )
    for step, mass_out in STEPS.items():
        shortfall = calc.recovery_shortfall(own[step], other[step])
        found.append(
            {
                "finding": shortfall.metric,
                "observation": shortfall.to_dict(),
                "consequence": _consequence(mass_out, own, other)
                if shortfall.value is not None
                else None,
                "evidence": [],
                "cause": None,
            }
        )
    return found
