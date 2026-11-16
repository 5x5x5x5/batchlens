"""Settings, all from the environment, each with a safe default.

Secrets (the app key) are never logged or stored by BatchLens.

| Variable | Default | Meaning |
|---|---|---|
| ``PLANTCRAFT_URL`` | ``http://127.0.0.1:8060`` | PlantCraft API v1, as this server reaches it |
| ``PLANTCRAFT_PUBLIC_URL`` | empty (same origin) | PlantCraft as the browser reaches it (sign-in page) |
| ``PLANTCRAFT_APP_KEY`` | empty | App key: what the app reads and publishes on its own |
| ``PLANTCRAFT_APP_KEY_FILE`` | empty | File holding the app key (a Docker secret) |
| ``BATCHLENS_DATA_DIR`` | ``var`` | Folder of the SQLite database |
| ``BATCHLENS_ROOT_PATH`` | ``/batchlens`` | Path prefix of the interface and API |
"""

from __future__ import annotations

from dataclasses import dataclass

from plantcraft_sdk.server.settings import AppSettings

from batchlens import APP_ID


@dataclass
class Settings(AppSettings):
    APP_ID = APP_ID

    root_path: str = "/batchlens"

    @classmethod
    def from_environment(cls) -> Settings:
        return cls(**cls.common(APP_ID, "/batchlens"))
