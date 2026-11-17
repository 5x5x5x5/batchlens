"""The plant tests read, served by a fake PlantCraft to BatchLens and its four users
(admin, engineer, operator, outsider).

Two parts: the suite's test plant (``plantcraft_sdk.testplant``: the Simulator's loops and 12
hours of their signals ending at ``NOW``), and the synthetic bioprocess plant of
``batchlens.demo.plant``: a unit with a bioreactor, a harvest skid and a Protein A skid, and
the bioreactor's online signals for the demo batches, as a PlantCraft answers them once
``batchlens demo-plant``'s map is imported. The app reads them through the
real client calls, exactly as it would read a live PlantCraft.
"""

from __future__ import annotations

import tomllib
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from plantcraft_sdk.contributes import contributions
from plantcraft_sdk.testing import FakePlantCraft
from plantcraft_sdk.testplant import (
    APP_KEY,
    HOURS,
    NOW,
    SOURCE,
    START,
    plant_series,
    plant_users,
)
from plantcraft_sdk.testplant import plant_assets as assets
from plantcraft_sdk.testplant import plant_signals as signals

from batchlens.demo.generator import BIOREACTOR, ONLINE_UNITS, demo_campaign
from batchlens.demo.plant import ASSETS, DESCRIPTION, SIGNAL_NAMES, SOURCE_ID, TAGS, VESSEL_TAGS

__all__ = ["APP_KEY", "HOURS", "NOW", "SOURCE", "START", "assets", "make_fake", "signals"]
__all__ += ["BIO_SIGNALS", "plant_series"]


MANIFEST = tomllib.loads((Path(__file__).parents[1] / "app.toml").read_text(encoding="utf-8"))

# The bioreactor's signals as PlantCraft names them once the map is imported: role -> signal id.
BIO_SIGNALS = {role_key: f"{SOURCE_ID}:{tag}" for role_key, tag in TAGS.items()}
# The volume signal of each other vessel: asset id -> signal id.
VESSEL_SIGNALS = {asset_id: f"{SOURCE_ID}:{tag}" for asset_id, tag in VESSEL_TAGS.items()}


def bio_assets() -> list[dict[str, Any]]:
    """The plant of ``batchlens.demo.plant``, as API v1 answers it after the map import."""

    return [
        {
            "id": asset_id,
            "name": name,
            "kind": kind,
            "parent_id": parent or "plant",
            "attributes": {"description": DESCRIPTION},
            **({"signals": dict(BIO_SIGNALS)} if asset_id == BIOREACTOR else {}),
            **(
                {"signals": {"volume": VESSEL_SIGNALS[asset_id]}}
                if asset_id in VESSEL_SIGNALS
                else {}
            ),
        }
        for asset_id, (kind, name, parent) in ASSETS.items()
    ]


def bio_signals() -> list[dict[str, Any]]:
    return [
        {
            "id": signal_id,
            "name": f"{BIOREACTOR} {SIGNAL_NAMES[role_key]}",
            "source": SOURCE_ID,
            "unit": ONLINE_UNITS[role_key],
            "description": "",
            "low": None,
            "high": None,
        }
        for role_key, signal_id in BIO_SIGNALS.items()
    ] + [
        {
            "id": signal_id,
            "name": f"{asset_id} {SIGNAL_NAMES['volume']}",
            "source": SOURCE_ID,
            "unit": ONLINE_UNITS["volume"],
            "description": "",
            "low": None,
            "high": None,
        }
        for asset_id, signal_id in VESSEL_SIGNALS.items()
    ]


def bio_series() -> dict[str, pd.Series]:
    """One series per signal carrying every demo batch, one after another."""

    observations, _ = demo_campaign()
    found = {}
    for role_key, signal_id in BIO_SIGNALS.items():
        points = [point for batch in observations for point in batch.online[role_key]]
        found[signal_id] = pd.Series(
            [value for _, value in points], pd.DatetimeIndex([moment for moment, _ in points])
        )
    for asset_id, signal_id in VESSEL_SIGNALS.items():
        points = [point for batch in observations for point in batch.vessels[asset_id]]
        found[signal_id] = pd.Series(
            [value for _, value in points], pd.DatetimeIndex([moment for moment, _ in points])
        )
    return found


def make_fake(*, bioprocess: bool = True, **options) -> FakePlantCraft:
    """The test plant, with what BatchLens's ``app.toml`` contributes already sent (as the
    app does when it starts). ``bioprocess=False`` leaves the synthetic bioprocess plant out:
    what a live PlantCraft looks like before that plant is loaded into it."""

    fake = FakePlantCraft(
        users=plant_users("batchlens"),
        apps=[
            {"id": "batchlens", "name": "BatchLensCraft", "url": "/batchlens/", "version": "0.1.0"}
        ],
        app_keys={"batchlens": APP_KEY},
        assets=assets() + (bio_assets() if bioprocess else []),
        signals=signals() + (bio_signals() if bioprocess else []),
        series={
            **{key: value.copy() for key, value in plant_series().items()},
            **(bio_series() if bioprocess else {}),
        },
        # After the last demo batch (the loops' own data still ends at NOW).
        now=NOW + timedelta(days=30),
        **options,
    )
    fake.client(None, app="batchlens", key=APP_KEY).put_contributions(contributions(MANIFEST))
    return fake
