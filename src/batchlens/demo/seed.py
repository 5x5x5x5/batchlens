"""Loads the generated demo batches into the app's store (``batchlens seed-demo``).

Only the observations are stored. The generator's ground truth never reaches the database.
"""

from __future__ import annotations

import logging

from batchlens.batches.service import BatchService
from batchlens.demo.generator import demo_campaign

LOGGER = logging.getLogger(__name__)


def seed_demo(batches: BatchService) -> list[str]:
    """Stores the demo batches under their stable ids; running it again changes nothing."""

    observations, _ground_truth = demo_campaign()
    for item in observations:
        batches.save(item.record)
    seeded = [item.record.batch.batch_id for item in observations]
    LOGGER.info("Seeded %d synthetic demo batches: %s", len(seeded), ", ".join(seeded))
    return seeded
