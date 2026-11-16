"""The purification train: each step's yield, what is left of the harvest after it, the
genealogy of the pools, and for the steps after capture whether one yielded less than the
reference batch's did.

Every mass is a pool measurement's volume times concentration (``calc.pool_mass``); a step's
yield is the mass out over the mass in; the recovery from harvest is the mass out over the
product mass at harvest. Where pools were merged, the merged mass is checked against the sum
of its parts. Nothing is stored, and ``as_of`` applies to every measurement.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from batchlens import calc
from batchlens.analysis.metrics import _pool, as_calc_pool
from batchlens.batches.models import BatchRecord

# (step, the pool that goes in, the pool that comes out), in process order.
STEPS = (
    ("protein_a_capture", "protein_a_load", "protein_a_eluate"),
    ("viral_inactivation", "protein_a_eluate", "viral_inactivation_pool"),
    ("cation_exchange", "viral_inactivation_pool", "cation_exchange_pool"),
    ("anion_exchange", "cation_exchange_pool", "anion_exchange_pool"),
    ("viral_filtration", "anion_exchange_pool", "viral_filtrate"),
    ("ufdf", "viral_filtrate", "drug_substance"),
)

Train = list[tuple[str, calc.Result, calc.Result, calc.Result, calc.Result]]


def _train(
    record: BatchRecord, harvest: calc.Result, as_of: datetime | None
) -> tuple[Train, calc.Result]:
    """Per step: its name, mass in, mass out, yield and recovery from harvest; and the overall
    recovery from harvest to drug substance."""

    def mass(pool_name: str) -> calc.Result:
        return calc.pool_mass(f"{pool_name}_mass", _pool(record, pool_name, as_of), as_of=as_of)

    rows: Train = []
    for step, pool_in, pool_out in STEPS:
        mass_in, mass_out = mass(pool_in), mass(pool_out)
        rows.append(
            (
                step,
                mass_in,
                mass_out,
                calc.ratio_percent(f"{step}_yield", mass_out, mass_in),
                calc.ratio_percent(f"{step}_from_harvest", mass_out, harvest),
            )
        )
    overall = calc.ratio_percent(
        "harvest_to_drug_substance_recovery", mass("drug_substance"), harvest
    )
    return rows, overall


def _genealogy(record: BatchRecord, as_of: datetime | None) -> list[dict[str, Any]]:
    seen = [p for p in record.pools if as_of is None or p.measured_at <= as_of]
    masses = {
        # Each measurement's own mass, by its id: a pool measured twice keeps both.
        p.measurement_id: calc.pool_mass(f"{p.pool}_mass", as_calc_pool(p), as_of=as_of)
        for p in seen
    }
    nodes = []
    for pool in seen:
        sources = [
            link.from_pool_id
            for link in record.links
            if link.to_pool_id == pool.measurement_id and link.from_pool_id in masses
        ]
        balance = None
        if len(sources) > 1:  # a merge: the whole against the sum of its parts
            balance = calc.merge_balance(
                [masses[source] for source in sources], masses[pool.measurement_id]
            ).to_dict()
        nodes.append(
            {
                "pool": pool.pool,
                "measurement_id": pool.measurement_id,
                "mass": masses[pool.measurement_id].to_dict(),
                "sources": sources,
                "merge_balance": balance,
            }
        )
    return nodes


def downstream(
    record: BatchRecord,
    harvest: calc.Result,
    *,
    as_of: datetime | None = None,
    reference: tuple[BatchRecord, calc.Result] | None = None,
) -> dict[str, Any]:
    """``steps`` (mass in, mass out, step yield, recovery from harvest), ``overall`` (harvest to
    drug substance) and ``genealogy`` (each pool, the pools it was made from, and the mass
    balance of a merge).

    With ``reference`` (the reference batch's record and its harvest mass): each step also
    carries the reference's yield and the difference, ``overall_reference`` is the reference's
    overall recovery, and ``findings`` holds, for each step after capture, whether its yield is
    more than the tolerance below the reference's (``calc.recovery_shortfall``), with the mass
    out of the step against the reference's as its consequence and no cause. The capture
    step's own finding is the Protein A recovery's (``analysis.metrics.findings``).
    """

    rows, overall = _train(record, harvest, as_of)
    beside = _train(reference[0], reference[1], as_of) if reference else None
    other = {row[0]: row for row in beside[0]} if beside else {}
    steps, found = [], []
    for step, mass_in, mass_out, step_yield, from_harvest in rows:
        row = {
            "step": step,
            "mass_in": mass_in.to_dict(),
            "mass_out": mass_out.to_dict(),
            "step_yield": step_yield.to_dict(),
            "from_harvest": from_harvest.to_dict(),
        }
        if beside:
            _, _, their_out, their_yield, _ = other[step]
            both = their_yield.value is not None and step_yield.value is not None
            row["reference_yield"] = their_yield.value
            row["yield_difference"] = step_yield.value - their_yield.value if both else None
            if step != STEPS[0][0]:
                shortfall = calc.recovery_shortfall(step_yield, their_yield)
                masses = mass_out.value is not None and their_out.value is not None
                consequence = {
                    "metric": mass_out.metric,
                    "unit": mass_out.unit,
                    "status": mass_out.status,
                    "value": mass_out.value,
                    "reference": their_out.value,
                    "difference": mass_out.value - their_out.value if masses else None,
                }
                found.append(
                    {
                        "finding": shortfall.metric,
                        "observation": shortfall.to_dict(),
                        "consequence": consequence if shortfall.value is not None else None,
                        "evidence": [],
                        "cause": None,
                    }
                )
        steps.append(row)
    return {
        "steps": steps,
        "overall": overall.to_dict(),
        "overall_reference": beside[1].value if beside else None,
        "genealogy": _genealogy(record, as_of),
        "findings": found,
    }
