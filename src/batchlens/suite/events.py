"""The events BatchLens writes to PlantCraft: which batch's phase is running on which asset.

One interval event, ``phase.running`` (``[[publishes.events]]`` in ``app.toml``): a ``start``
when a phase execution is under way on its asset, an ``end`` when it is over, with the phase
execution's id as the key. The asset's page in PlantCraft shows them, and the suite's other
apps can scope what they show to the batch on the asset.

**The event's time is when BatchLens reported it, not when the phase began.** PlantCraft stamps
an event when it arrives. The times of the phase execution are in the payload. For that reason
nothing is written for a phase that was over before this server started looking: a ``start``
dated today for a culture of last month would be a false entry in the asset's timeline.

Phases of product batches only. Nothing here reads a calculation or a finding: PlantCraft is
told what was recorded, not what BatchLens makes of it.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import Any

from plantcraft_sdk.events import EventCatalog
from plantcraft_sdk.utc import utc_iso

from batchlens.meta import FILES

LOGGER = logging.getLogger(__name__)
EVENT = "phase.running"
TICK_SECONDS = 60.0


def catalog() -> EventCatalog:
    """The events ``app.toml`` declares."""

    return EventCatalog.from_manifest(FILES.manifest())


class PhasePublisher:
    """Remembers which phase executions it has said are running, so that it writes only when
    one starts or ends. After a restart it says ``start`` again for the ones running now;
    PlantCraft does not write a ``start`` of a condition that is already open twice."""

    def __init__(self, catalog: EventCatalog):
        self.catalog = catalog
        self.open: dict[str, Any] = {}  # phase execution id -> the phase execution

    def changes(self, summaries: list[tuple[Any, tuple[Any, ...]]], now: datetime) -> list[dict]:
        """The events to write at ``now``: an ``end`` for each phase it opened that is over, a
        ``start`` for each phase under way that it has not opened. ``summaries`` is the
        batches' service's: each batch with its phase executions."""

        running = {
            phase.phase_id: phase
            for _, phases in summaries
            for phase in phases
            if phase.start <= now < phase.end
        }
        events = [
            self._event(phase, "end") for key, phase in self.open.items() if key not in running
        ]
        events += [self._event(p, "start") for key, p in running.items() if key not in self.open]
        self.open = running
        return events

    def _event(self, phase: Any, edge: str) -> dict[str, Any]:
        began = utc_iso(phase.start)
        return self.catalog.event(
            EVENT,
            f"asset:{phase.asset_id}",
            summary=f"{phase.batch_id}: {phase.kind.replace('_', ' ')}"
            + (f" (began {began})" if edge == "start" else f" (ended {utc_iso(phase.end)})"),
            payload={
                "batch": phase.batch_id,
                "phase": phase.phase_id,
                "kind": phase.kind,
                "start": began,
                # A phase under way has no end yet: the planned one is not a fact.
                "end": utc_iso(phase.end) if edge == "end" else None,
            },
            key=phase.phase_id,
            phase=edge,
            severity="ok" if edge == "end" else None,
        )


def publish(publisher: PhasePublisher, batches: Any, client: Any, now: datetime) -> int:
    """One look: write what changed since the last one; answers how many events were saved.
    An event PlantCraft refuses (an asset it does not hold) is logged and not sent again
    until the phase's next change."""

    events = publisher.changes(batches.summaries(), now)
    if not events:
        return 0
    receipt = client.post_events(events)
    for error in receipt["errors"]:
        LOGGER.warning("PlantCraft refused a phase event: %s", error)
    return int(receipt["saved"])


def run(batches: Any, client: Any, stop: threading.Event) -> None:
    """Look every ``TICK_SECONDS`` until ``stop``. A failed look is logged and tried again:
    the publisher's memory is put back, so nothing that was not written counts as written."""

    publisher = PhasePublisher(catalog())
    while not stop.is_set():
        before = dict(publisher.open)
        try:
            publish(publisher, batches, client, datetime.now(UTC))
        except Exception:  # noqa: BLE001 - a background duty must outlive PlantCraft's restarts
            publisher.open = before
            LOGGER.warning("Phase events not written; trying again", exc_info=True)
        stop.wait(TICK_SECONDS)
