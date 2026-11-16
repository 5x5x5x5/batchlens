"""Loads the generated demo batches into the app's store (``batchlens seed-demo``).

Only the observations are stored. The generator's ground truth never reaches the database.
"""

from __future__ import annotations

import logging

from batchlens.batches.service import BatchService
from batchlens.demo.generator import demo_campaign

LOGGER = logging.getLogger(__name__)


def seed_demo(batches: BatchService, *, reset: bool = False) -> list[str]:
    """Stores the demo batches that are not there yet, under their stable ids, and answers
    which it loaded: running it again loads nothing and leaves what people corrected alone.
    ``reset`` loads all of them again as generated."""

    observations, _ground_truth = demo_campaign()
    seeded = []
    for item in observations:
        batch_id = item.record.batch.batch_id
        if reset or batches.get(batch_id) is None:
            batches.save(item.record)
            seeded.append(batch_id)
    LOGGER.info(
        "Seeded %d synthetic demo batches: %s", len(seeded), ", ".join(seeded) or "none new"
    )
    return seeded
