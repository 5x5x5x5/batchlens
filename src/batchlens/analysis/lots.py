"""The solution lot a purification step drew from, laid beside the reference batch's lot of the
same solution: evidence for a step that recovered less, with nothing concluded from it.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from batchlens import calc
from batchlens.analysis.metrics import sample_evidence
from batchlens.analysis.transfers import made_at
from batchlens.batches.models import BatchRecord, Transfer

# The finding of each step that draws a buffer, and that step's phase kind.
STEP_OF_FINDING = {
    "protein_a_recovery_shortfall": "protein_a_capture",
    "cation_exchange_yield_shortfall": "cation_exchange",
    "ufdf_yield_shortfall": "ufdf",
}


def _draw(record: BatchRecord, step: str) -> Transfer | None:
    """The buffer the step's asset drew during the step."""

    phase = record.phase(step)
    if phase is None:
        return None
    return next(
        (
            transfer
            for transfer in record.transfers
            if transfer.kind == "buffer"
            and transfer.to_asset_id == phase.asset_id
            and transfer.from_lot_id
        ),
        None,
    )


def _lot_results(
    batch: BatchRecord, lots: Mapping[str, BatchRecord], step: str, as_of: datetime | None
) -> dict[str, calc.Result]:
    """The results of the lot the batch's step drew, by analyte, as ``calc`` takes them."""

    draw = _draw(batch, step)
    lot = lots.get(draw.from_lot_id) if draw is not None else None
    return {
        r.analyte: calc.Result(
            r.analyte, r.value, r.unit, calc.USABLE, (), (r.result_id,), "recorded"
        )
        for r in (lot.results if lot is not None else ())
        if r.validity == "valid" and (as_of is None or r.result_available_at <= as_of)
    }


def lot_evidence(
    record: BatchRecord,
    reference: BatchRecord,
    lots: Mapping[str, BatchRecord],
    step: str,
    as_of: datetime | None = None,
    comparable: tuple[BatchRecord, ...] = (),
) -> list[dict[str, Any]]:
    """One evidence group (the shape of ``sample_evidence``): every result of the lot's sample
    beside the reference batch's lot's, with both lots' ids, the solution, and each lot's age
    in days when its step began to draw it. Empty when either batch has no recorded draw, a
    lot is not stored, or a lot has no result available at ``as_of``.

    With ``comparable`` batches, each row also says where this lot's value sits among the
    lots those batches drew for the same step (``calc.set_position``): two good lots differ
    too, and the range the comparable lots lead to expect says by how much."""

    draws = [_draw(batch, step) for batch in (record, reference)]
    if None in draws:
        return []
    own, other = (lots.get(draw.from_lot_id) for draw in draws)
    if own is None or other is None:
        return []
    made = [made_at(lot) for lot in (own, other)]
    if None in made:
        return []

    def first_result(lot: BatchRecord) -> str | None:
        usable = [
            r
            for r in lot.results
            if r.validity == "valid" and (as_of is None or r.result_available_at <= as_of)
        ]
        return min(usable, key=lambda r: r.result_id).result_id if usable else None

    ids = [first_result(lot) for lot in (own, other)]
    if None in ids:
        return []
    [group] = sample_evidence(own, other, made[0], [("buffer_lot", *ids)], as_of)
    mine = _lot_results(record, lots, step, as_of)
    theirs = [_lot_results(batch, lots, step, as_of) for batch in comparable]
    for row in group["results"]:
        others = [found[row["analyte"]] for found in theirs if row["analyte"] in found]
        row["comparable"] = (
            calc.set_position(mine[row["analyte"]], others).to_dict() if others else None
        )
    return [
        {
            **group,
            "solution": own.batch.product,
            "lot_id": own.batch.batch_id,
            "reference_lot_id": other.batch.batch_id,
            "age_days": (draws[0].start - made[0]).total_seconds() / 86400,
            "reference_age_days": (draws[1].start - made[1]).total_seconds() / 86400,
        }
    ]


def with_lot_evidence(
    findings: list[dict[str, Any]],
    record: BatchRecord,
    reference: BatchRecord | None,
    lots: Mapping[str, BatchRecord],
    as_of: datetime | None = None,
    comparable: tuple[BatchRecord, ...] = (),
) -> list[dict[str, Any]]:
    """The findings, each step shortfall that was found carrying the lot its step drew."""

    if reference is None:
        return findings
    for finding in findings:
        step = STEP_OF_FINDING.get(finding["finding"])
        if step is not None and finding["observation"]["value"] is not None:
            finding["evidence"] = lot_evidence(record, reference, lots, step, as_of, comparable)
    return findings
