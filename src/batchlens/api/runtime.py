"""Everything one BatchLens server holds: settings, the batches and the PlantCraft clients.

Who reads plant data: the pages read with the person's own token, so PlantCraft's permissions
decide what each person sees. The app key (``PLANTCRAFT_APP_KEY``) is for what the app does on
its own, in the background: telling PlantCraft which batch's phase is running on which asset
(``suite/events.py``). Without the key nothing is told.
"""

from __future__ import annotations

import threading
from typing import Any

import httpx
from plantcraft_sdk.auth import TokenVerifier
from plantcraft_sdk.client import PlantCraftClient
from plantcraft_sdk.server.platform import PlatformRuntime
from plantcraft_sdk.server.store import Database

from batchlens import APP_ID, __version__
from batchlens.batches.service import BatchService
from batchlens.batches.store import BatchStore
from batchlens.config import Settings
from batchlens.suite import events


class Runtime(PlatformRuntime):
    def __init__(
        self,
        settings: Settings,
        *,
        verifier: TokenVerifier | None = None,
        service_client: PlantCraftClient | None = None,
        http_client: httpx.Client | None = None,
    ):
        self.settings = settings
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database(settings.database_path, version=__version__)
        self.batches = BatchService(BatchStore(self.db))
        self.connect(
            APP_ID,
            settings,
            verifier=verifier,
            service_client=service_client,
            http_client=http_client,
        )

    def start(self) -> None:
        """Background work starts here: the phase events, when the app has its key."""

        # shortcut: one process assumed; with several workers each would look, and PlantCraft
        # would drop the repeats. Take workers.Leader when BATCHLENS_WORKERS is used.
        self._stop = threading.Event()
        if self.service_client is not None:
            threading.Thread(
                target=events.run,
                args=(self.batches, self.service_client, self._stop),
                name="phase-events",
                daemon=True,
            ).start()

    def shutdown(self) -> None:
        if getattr(self, "_stop", None) is not None:
            self._stop.set()
        self.close_platform()

    def status(self) -> dict[str, Any]:
        return {"service_key": self.has_service_key, "batches": len(self.batches.summaries())}
