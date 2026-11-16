"""The plant tests read, served by a fake PlantCraft to BatchlensCraft and its four users
(admin, engineer, operator, outsider).

Two parts: the suite's test plant (``plantcraft_sdk.testplant``: the Simulator's loops and 12
hours of their signals ending at ``NOW``), and the synthetic bioprocess plant of
``batchlens.demo.generator``: a unit with a bioreactor, a harvest skid and a Protein A skid,
and the bioreactor's online signals for the four demo batches. The app reads them through the
real client calls, exactly as it would read a live PlantCraft.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pandas as pd
from plantcraft_sdk.assets import STARTER_TYPES, role
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

from batchlens.demo.generator import (
    BIOREACTOR,
    HARVEST_SKID,
    ONLINE_UNITS,
    PROTEIN_A_SKID,
    demo_campaign,
)

__all__ = ["APP_KEY", "HOURS", "NOW", "SOURCE", "START", "assets", "make_fake", "signals"]
__all__ += ["BIO_SIGNALS", "plant_series"]


MANIFEST = tomllib.loads((Path(__file__).parents[1] / "app.toml").read_text(encoding="utf-8"))

# The bioreactor's signals as PlantCraft would name them: role -> signal id.
BIO_SIGNALS = {
    role_key: f"{SOURCE}:BIO.{BIOREACTOR}.{role_key.upper()}" for role_key in ONLINE_UNITS
}
NAMES = {"ph": "pH", "do": "Dissolved oxygen", "temperature": "Temperature", "volume": "Volume"}
# An admin's own asset type: a bioreactor is equipment with these signal roles.
BIOREACTOR_TYPE = {
    "id": "bioreactor",
    "name": "Bioreactor",
    "description": "A stirred-tank bioreactor (synthetic demo).",
    "icon": "box",
    "parent": "equipment",
    "attributes": [],
    "roles": [role(key, NAMES[key], unit=unit) for key, unit in ONLINE_UNITS.items()],
    "children": [],
}


def bio_assets() -> list[dict[str, Any]]:
    def equipment(asset_id: str, name: str, kind: str = "equipment", **more: Any) -> dict[str, Any]:
        return {
            "id": asset_id,
            "name": name,
            "kind": kind,
            "parent_id": "U-MAB",
            "attributes": {},
            **more,
        }

    return [
        {
            "id": "U-MAB",
            "name": "mAb drug substance (synthetic)",
            "kind": "unit",
            "parent_id": "plant",
            "attributes": {},
        },
        equipment(
            BIOREACTOR, "Production bioreactor 2000 L", "bioreactor", signals=dict(BIO_SIGNALS)
        ),
        equipment(HARVEST_SKID, "Harvest clarification skid"),
        equipment(PROTEIN_A_SKID, "Protein A chromatography skid"),
    ]


def bio_signals() -> list[dict[str, Any]]:
    return [
        {
            "id": signal_id,
            "name": f"{BIOREACTOR} {NAMES[role_key]}",
            "source": SOURCE,
            "unit": ONLINE_UNITS[role_key],
            "description": f"{NAMES[role_key]} of {BIOREACTOR} (synthetic)",
            "low": None,
            "high": None,
        }
        for role_key, signal_id in BIO_SIGNALS.items()
    ]


def bio_series() -> dict[str, pd.Series]:
    """One series per signal carrying all four batches, one after another."""

    observations, _ = demo_campaign()
    found = {}
    for role_key, signal_id in BIO_SIGNALS.items():
        points = [point for batch in observations for point in batch.online[role_key]]
        found[signal_id] = pd.Series(
            [value for _, value in points], pd.DatetimeIndex([moment for moment, _ in points])
        )
    return found


def make_fake(*, bioprocess: bool = True, **options) -> FakePlantCraft:
    """The test plant, with what BatchlensCraft's ``app.toml`` contributes already sent (as the
    app does when it starts). ``bioprocess=False`` leaves the synthetic bioprocess plant out:
    what a live PlantCraft looks like before that plant is loaded into it."""

    fake = FakePlantCraft(
        users=plant_users("batchlens"),
        apps=[
            {"id": "batchlens", "name": "BatchlensCraft", "url": "/batchlens/", "version": "0.1.0"}
        ],
        app_keys={"batchlens": APP_KEY},
        assets=assets() + (bio_assets() if bioprocess else []),
        asset_types=[*STARTER_TYPES, BIOREACTOR_TYPE],
        signals=signals() + (bio_signals() if bioprocess else []),
        series={
            **{key: value.copy() for key, value in plant_series().items()},
            **(bio_series() if bioprocess else {}),
        },
        now=NOW,
        **options,
    )
    fake.client(None, app="batchlens", key=APP_KEY).put_contributions(contributions(MANIFEST))
    return fake
