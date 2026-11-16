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
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from batchlens.demo.generator import (
    BIOREACTOR,
    DOWNSTREAM,
    FEED_TANK,
    HARVEST_SKID,
    LOOP_ROLES,
    ONLINE_UNITS,
    PROTEIN_A_SKID,
    SEED_TRAIN,
    demo_campaign,
    loop_series,
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
# The control loops' fast signals come from a source and a file of their own, which holds the
# last LOOP_HOURS only: loop monitoring looks at what a loop is doing now.
LOOP_SOURCE_NAME = "BatchLens synthetic loops"
LOOP_SOURCE_ID = "batchlens-synthetic-loops"
LOOP_HOURS = 48
# loop id -> (name, the role it controls, PlantCraft's loop type, what it does).
LOOPS = {
    "TIC-2001": (
        "BR-2001 temperature control",
        "temperature",
        "temperature",
        "Jacket temperature of the production bioreactor",
    ),
    "AIC-2001": ("BR-2001 pH control", "ph", "composition", "pH of the culture by CO2 and base"),
    "AIC-2002": (
        "BR-2001 dissolved oxygen control",
        "do",
        "composition",
        "Dissolved oxygen of the culture by oxygen sparge",
    ),
}
# "<role>.pv", ".sp" and ".op" -> tag (the loops file's column).
LOOP_TAGS = {
    f"{role}.{part}": f"LOOP.{loop_id}.{part.upper()}"
    for loop_id, (_, role, _, _) in LOOPS.items()
    for part in ("pv", "sp", "op")
}
assert {role for _, role, _, _ in LOOPS.values()} == set(LOOP_ROLES)
# asset id -> (kind, name, parent). Roles are free text in PlantCraft's map, so the bioreactor
# is plain equipment and no asset type has to be made before the import.
ASSETS = {
    UNIT: ("unit", "mAb drug substance", None),
    **{
        asset_id: ("equipment", f"Seed bioreactor {short} {litres:.0f} L", UNIT)
        for (_, asset_id, litres), short in zip(SEED_TRAIN, ("N-2", "N-1"))
    },
    FEED_TANK: ("equipment", "Feed medium hold tank", UNIT),
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


def recorded(
    live_from: datetime | None = None, until: datetime | None = None
) -> dict[datetime, dict[str, float]]:
    """Every online value of the demo batches: ``{instant: {tag: value}}``. With ``live_from``
    the campaign is the live one, and ``until`` (now) leaves out what has not happened yet."""

    observations, _ground_truth = demo_campaign(live_from)
    rows: dict[datetime, dict[str, float]] = {}
    for batch in observations:
        for role, points in batch.online.items():
            for moment, value in points:
                if until is None or moment <= until:
                    rows.setdefault(moment, {})[TAGS[role]] = value
    return rows


def loop_rows(
    live_from: datetime | None = None, until: datetime | None = None
) -> dict[datetime, dict[str, float]]:
    """The loops' fast values over the last ``LOOP_HOURS`` before ``until`` (without it: before
    the end of the campaign's last culture): ``{instant: {tag: value}}``."""

    observations, _ground_truth = demo_campaign(live_from)
    if until is None:
        until = observations[-1].record.phase("production_culture").end
    since = until - timedelta(hours=LOOP_HOURS)
    rows: dict[datetime, dict[str, float]] = {}
    for batch in observations:
        culture = batch.record.phase("production_culture")
        if culture.end <= since or culture.start > until:
            continue
        for key, points in loop_series(batch, since, until).items():
            for moment, value in points:
                rows.setdefault(moment, {})[LOOP_TAGS[key]] = value
    return rows


class PlantFiles(NamedTuple):
    csv: Path
    map: Path
    loops: Path


def plant_map(csv_path: Path, loops_path: Path) -> dict[str, object]:
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
            {"source_id": SOURCE_ID, "name": SOURCE_NAME, "type": "csv", "path": str(csv_path)},
            {
                "source_id": LOOP_SOURCE_ID,
                "name": LOOP_SOURCE_NAME,
                "type": "csv",
                "path": str(loops_path),
            },
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
                # Followed by PlantCraft Analytics' Signal quality monitor.
                "monitor": True,
            }
            for role, tag in TAGS.items()
        ]
        + [
            # A loop's signals belong to the loop only (the loops sheet binds them by role).
            {
                "tag": LOOP_TAGS[f"{role}.{part}"],
                "source_id": LOOP_SOURCE_ID,
                "name": f"{loop_id} {label}",
                "unit": "%" if part == "op" else ONLINE_UNITS[role],
                "asset_id": "",
                "role": "",
                "monitor": False,
            }
            for loop_id, (_, role, _, _) in LOOPS.items()
            for part, label in (("pv", "value"), ("sp", "setpoint"), ("op", "output"))
        ],
        "loops": [
            {
                "loop_id": loop_id,
                "name": name,
                "asset_id": BIOREACTOR,
                "service": service,
                "pv": LOOP_TAGS[f"{role}.pv"],
                "sp": LOOP_TAGS[f"{role}.sp"],
                "op": LOOP_TAGS[f"{role}.op"],
                "loop_type": loop_type,
            }
            for loop_id, (name, role, loop_type, service) in LOOPS.items()
        ],
    }


def write_plant_files(
    folder: Path,
    time_zone: str = "UTC",
    *,
    live_from: datetime | None = None,
    until: datetime | None = None,
) -> PlantFiles:
    """Writes ``bioreactor.csv``, ``bioreactor-loops.csv`` and ``plant-map.json`` into ``folder``. The CSV's times are on
    the wall clock of ``time_zone`` (the zone PlantCraft reads CSV files in); the map names the
    CSV by its absolute path, as PlantCraft's server will open it. Raises ``ValueError`` for a
    time zone this computer does not know.

    ``live_from`` and ``until`` as in ``recorded``. Each CSV is replaced in one step, so writing
    it again while PlantCraft reads it never shows half a file."""

    try:
        zone = ZoneInfo(time_zone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown time zone: {time_zone}") from exc
    folder.mkdir(parents=True, exist_ok=True)

    def write(name: str, rows: dict[datetime, dict[str, float]], columns: list[str]) -> Path:
        path = folder.resolve() / name
        draft = path.with_suffix(".csv.part")
        with draft.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["time", *columns])
            for moment in sorted(rows):
                stamp = moment.astimezone(zone).strftime("%Y-%m-%d %H:%M:%S")
                writer.writerow([stamp, *(rows[moment].get(tag, "") for tag in columns)])
        draft.replace(path)
        return path

    csv_path = write("bioreactor.csv", recorded(live_from, until), list(TAGS.values()))
    loops_path = write(
        "bioreactor-loops.csv", loop_rows(live_from, until), list(LOOP_TAGS.values())
    )
    map_path = folder.resolve() / "plant-map.json"
    map_path.write_text(
        json.dumps(plant_map(csv_path, loops_path), indent=2) + "\n", encoding="utf-8"
    )
    return PlantFiles(csv_path, map_path, loops_path)
