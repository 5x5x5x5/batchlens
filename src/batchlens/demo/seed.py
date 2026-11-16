"""Loads the generated demo batches into the app's store (``batchlens seed-demo``).

Only the observations are stored. The generator's ground truth never reaches the database.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime

from batchlens.batches.service import BatchService
from batchlens.demo.generator import COMPARABLE, LIVE_BATCH, demo_campaign, live_start

LOGGER = logging.getLogger(__name__)


def live_from(batches: BatchService) -> datetime | None:
    """When the stored live batch's culture began; None when there is none."""

    stored = batches.get(LIVE_BATCH)
    culture = stored.phase("production_culture") if stored is not None else None
    return culture.start if culture is not None else None


def seed_demo(
    batches: BatchService, *, reset: bool = False, live_at: datetime | None = None
) -> list[str]:
    """Stores the demo batches that are not there yet, or were made by an older version of the
    generator, under their stable ids, and answers which it loaded. Running it again loads
    nothing and leaves what people changed alone.

    Loading a batch again (an older generator's, or every batch with ``reset``) puts its
    records back as generated: a sample time a person had corrected is undone, which is logged
    with the sample's id; the history of corrections is kept. The reference batch a person
    chose stays the reference unless ``reset`` asks for the demo as generated.

    With ``live_at`` (now), the campaign is the live one (``demo_campaign``): its dates are
    fixed the first time, from ``live_at``, and kept on every later run, so a demo left
    running moves on through the live batch. The first time is a ``reset``: batches stored
    with other dates are replaced."""

    anchor = None
    if live_at is not None:
        anchor = None if reset else live_from(batches)
        if anchor is None:
            anchor, reset = live_start(live_at), True
    observations, _ground_truth = demo_campaign(anchor)
    chosen = None if reset else getattr(batches.reference(), "batch", None)
    # The set of comparable batches is a person's too: marked as the demo has it the first
    # time and on ``reset``, left as people made it otherwise.
    mark = reset or not batches.comparable_ids()
    seeded = []
    for item in observations:
        record, batch_id = item.record, item.record.batch.batch_id
        stored = batches.get(batch_id)
        if not reset and stored is not None and stored.batch.provenance == record.batch.provenance:
            continue
        if chosen is not None:  # exactly one reference, and it is the one already chosen
            flagged = replace(record.batch, is_reference=batch_id == chosen.batch_id)
            record = replace(record, batch=flagged)
        if stored is not None:
            generated = {sample.sample_id: sample.collected_at for sample in record.samples}
            undone = sorted(
                sample.sample_id
                for sample in stored.samples
                if generated.get(sample.sample_id) not in (None, sample.collected_at)
            )
            if undone:
                LOGGER.warning(
                    "Loading %s again as generated: corrected sample times undone for %s",
                    batch_id,
                    ", ".join(undone),
                )
        batches.save(record)
        if mark:
            batches.set_comparable(batch_id, batch_id in COMPARABLE)
        seeded.append(batch_id)
    LOGGER.info(
        "Seeded %d synthetic demo batches: %s", len(seeded), ", ".join(seeded) or "none new"
    )
    return seeded
