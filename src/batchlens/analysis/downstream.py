"""The purification train: each step's yield, what is left of the harvest after it, and the
genealogy of the pools.

Every mass is a pool measurement's volume times concentration (``calc.pool_mass``); a step's
yield is the mass out over the mass in; the recovery from harvest is the mass out over the
product mass at harvest. Where pools were merged, the merged mass is checked against the sum
of its parts. Nothing is stored, and ``as_of`` applies to every measurement.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from batchlens import calc
from batchlens.analysis.metrics import _pool
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


def downstream(
    record: BatchRecord,
    harvest: calc.Result,
    *,
    as_of: datetime | None = None,
    reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """``steps`` (mass in, mass out, step yield, recovery from harvest; with ``reference``,
    another batch's answer, also that batch's yield and the difference), ``overall`` (harvest
    to drug substance) and ``genealogy`` (each pool, the pools it was made from, and the mass
    balance of a merge)."""

    def mass(pool_name: str) -> calc.Result:
        return calc.pool_mass(f"{pool_name}_mass", _pool(record, pool_name, as_of), as_of=as_of)

    beside = {row["step"]: row["step_yield"] for row in (reference or {}).get("steps", [])}
    steps = []
    for step, pool_in, pool_out in STEPS:
        mass_in, mass_out = mass(pool_in), mass(pool_out)
        step_yield = calc.ratio_percent(f"{step}_yield", mass_out, mass_in)
        row = {
            "step": step,
            "mass_in": mass_in.to_dict(),
            "mass_out": mass_out.to_dict(),
            "step_yield": step_yield.to_dict(),
            "from_harvest": calc.ratio_percent(f"{step}_from_harvest", mass_out, harvest).to_dict(),
        }
        if reference is not None:
            other = beside.get(step, {}).get("value")
            both = other is not None and step_yield.value is not None
            row["reference_yield"] = other
            row["yield_difference"] = step_yield.value - other if both else None
        steps.append(row)
    overall = calc.ratio_percent(
        "harvest_to_drug_substance_recovery", mass("drug_substance"), harvest
    )

    seen = [p for p in record.pools if as_of is None or p.measured_at <= as_of]
    masses = {
        p.measurement_id: calc.pool_mass(
            f"{p.pool}_mass", _pool(record, p.pool, as_of), as_of=as_of
        )
        for p in seen
    }
    genealogy = []
    for pool in seen:
        sources = [
            link.from_pool_id
            for link in record.links
            if link.to_pool_id == pool.measurement_id and link.from_pool_id in masses
        ]
        merged = len(sources) > 1
        balance = (
            calc.merge_balance([masses[s] for s in sources], masses[pool.measurement_id])
            if merged
            else None
        )
        genealogy.append(
            {
                "pool": pool.pool,
                "measurement_id": pool.measurement_id,
                "mass": masses[pool.measurement_id].to_dict(),
                "sources": sources,
                "merge_balance": balance.to_dict() if balance else None,
            }
        )
    return {"steps": steps, "overall": overall.to_dict(), "genealogy": genealogy}
