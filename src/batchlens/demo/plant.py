"""The synthetic plant itself: the unit, the bioreactor and the two skids, and the bioreactor's
four online signals, as files a live PlantCraft imports (``batchlens demo-plant``).

Two files, made from the same seeded generator as the demo batches:

| File | For PlantCraft's |
|---|---|
| ``bioreactor.csv`` | CSV data source: one row per instant, one column per tag |
| ``plant-map.json`` | plant map import: the source, the assets, and each signal with its unit and role |

**Time zone.** A CSV has no offsets, and PlantCraft 0.6.0 reads a CSV source's times on the wall
clock of its scenario's source time zone (``scenario.source.timezone``; the source's own
``timezone`` setting does not change it). ``time_zone`` must be that zone, or every value lands
hours off, silently. The instants are the same whatever the zone.

An administrator imports the map in PlantCraft (docs/demo.md); BatchLens writes nothing to
PlantCraft itself and never publishes these values as its own series. The tests' fake
PlantCraft (``tests/plant.py``) serves this same plant. Standard library only.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import NamedTuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from batchlens.demo.generator import (
    BIOREACTOR,
    DOWNSTREAM,
    HARVEST_SKID,
    ONLINE_UNITS,
    PROTEIN_A_SKID,
    demo_campaign,
)

UNIT = "U-MAB"
# PlantCraft makes a source's id from its name; a signal's id is then "<SOURCE_ID>:<tag>".
SOURCE_NAME = "BatchLens synthetic"
SOURCE_ID = "batchlens-synthetic"
SIGNAL_NAMES = {
    "ph": "pH",
    "do": "Dissolved oxygen",
    "temperature": "Temperature",
    "volume": "Volume",
}
# role -> tag (the CSV column).
TAGS = {role: f"BIO.{BIOREACTOR}.{role.upper()}" for role in ONLINE_UNITS}
# asset id -> (kind, name, parent). Roles are free text in PlantCraft's map, so the bioreactor
# is plain equipment and no asset type has to be made before the import.
ASSETS = {
    UNIT: ("unit", "mAb drug substance (synthetic)", None),
    BIOREACTOR: ("equipment", "Production bioreactor 2000 L", UNIT),
    HARVEST_SKID: ("equipment", "Harvest clarification skid", UNIT),
    PROTEIN_A_SKID: ("equipment", "Protein A chromatography skid", UNIT),
    **{
        asset_id: ("equipment", name, UNIT)
        for (_, asset_id, _, _, _), name in zip(
            DOWNSTREAM,
            (
                "Viral inactivation vessel",
                "Cation-exchange chromatography skid",
                "Anion-exchange chromatography skid",
                "Viral filtration skid",
                "UF/DF skid",
            ),
        )
    },
}
DESCRIPTION = "Synthetic demo equipment of BatchLens. Not a real asset."


def recorded() -> dict[datetime, dict[str, float]]:
    """Every online value of the demo batches: ``{instant: {tag: value}}``."""

    observations, _ground_truth = demo_campaign()
    rows: dict[datetime, dict[str, float]] = {}
    for batch in observations:
        for role, points in batch.online.items():
            for moment, value in points:
                rows.setdefault(moment, {})[TAGS[role]] = value
    return rows


class PlantFiles(NamedTuple):
    csv: Path
    map: Path


def plant_map(csv_path: Path) -> dict[str, object]:
    """PlantCraft's plant map (format ``processcraft-map``) of the synthetic plant."""

    sheets: dict[str, list[dict[str, object]]] = {"unit": [], "equipment": []}
    for asset_id, (kind, name, parent) in ASSETS.items():
        sheets[kind].append(
            {
                "asset_id": asset_id,
                "name": name,
                "parent_id": parent or "",
                "description": DESCRIPTION,
            }
        )
    return {
        "format": "processcraft-map",
        "sources": [
            {"source_id": SOURCE_ID, "name": SOURCE_NAME, "type": "csv", "path": str(csv_path)}
        ],
        **sheets,
        "signals": [
            {
                "tag": tag,
                "source_id": SOURCE_ID,
                "name": f"{BIOREACTOR} {SIGNAL_NAMES[role]}",
                "unit": ONLINE_UNITS[role],
                "asset_id": BIOREACTOR,
                "role": role,
                # Recorded history, not a live feed: nothing for data quality to follow.
                "monitor": False,
            }
            for role, tag in TAGS.items()
        ],
    }


def write_plant_files(folder: Path, time_zone: str = "UTC") -> PlantFiles:
    """Writes ``bioreactor.csv`` and ``plant-map.json`` into ``folder``. The CSV's times are on
    the wall clock of ``time_zone`` (the zone PlantCraft reads CSV files in); the map names the
    CSV by its absolute path, as PlantCraft's server will open it. Raises ``ValueError`` for a
    time zone this computer does not know."""

    try:
        zone = ZoneInfo(time_zone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown time zone: {time_zone}") from exc
    folder.mkdir(parents=True, exist_ok=True)
    csv_path = folder.resolve() / "bioreactor.csv"
    rows = recorded()
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["time", *TAGS.values()])
        for moment in sorted(rows):
            values = rows[moment]
            stamp = moment.astimezone(zone).strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([stamp, *(values.get(tag, "") for tag in TAGS.values())])
    map_path = folder.resolve() / "plant-map.json"
    map_path.write_text(json.dumps(plant_map(csv_path), indent=2) + "\n", encoding="utf-8")
    return PlantFiles(csv_path, map_path)
