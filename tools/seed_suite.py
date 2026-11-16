#!/usr/bin/env python3
"""Gives the suite's modules something of the synthetic mAb plant to show.

    python tools/seed_suite.py http://127.0.0.1:8088 [bioreactor.csv TIME_ZONE]

- Historian (with the bioreactor's file and the zone its times are in): that file and the
  loops' file beside it as CSV sources checked every minute, their signals archived.
- Analytics: the expected range of each bioreactor signal, for its Signal quality monitor;
  the bioreactor's three control loops listed and a first round of loop performance asked for.
- View and Alarms: their own first steps for a new plant (a unit overview of the loops, two
  draft rules switched off), which need the loops to exist.
- View: a dashboard of the bioreactor's four signals, and a process display of the train.
- Alarms: four rules on the bioreactor's signals, with illustrative limits.
- Documents: this repository's verification report, assumptions and tour, linked to the unit.

Running it again changes nothing: what is already there by name is kept, and a module that is
not installed is skipped. It signs in as the local demo's person (as the administrator of
``PLANTCRAFT_BASIC_AUTH_*`` when sign-in is on) and calls the modules' own
interface routes, as their pages do. Those are not PlantCraft's API v1 and were tried on the
modules of PlantCraft 0.6.0 only. Standard library only.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("batchlens.seed_suite")
DOCS = Path(__file__).resolve().parents[1] / "docs"
UNIT, BIOREACTOR = "U-MAB", "BR-2001"
SOURCE = "batchlens-synthetic"
LOOP_SOURCE = "batchlens-synthetic-loops"
LOOP_UNITS = {"TIC-2001": "°C", "AIC-2001": "pH", "AIC-2002": "% air sat."}  # loop -> unit
START = {"units": [UNIT], "assets": [{"id": UNIT, "name": "mAb drug substance"}]}
SIGNALS = {  # role -> (label, unit)
    "ph": ("pH", "pH"),
    "do": ("Dissolved oxygen", "% air sat."),
    "temperature": ("Temperature", "°C"),
    "volume": ("Volume", "L"),
}
# The train in process order: asset id, name on the display, View's symbol.
TRAIN = (
    (BIOREACTOR, "Production bioreactor", "reactor.stirred"),
    ("HV-2101", "Harvest", "filter.cartridge"),
    ("CH-3001", "Protein A", "column.packed"),
    ("VI-3101", "Viral inactivation", "vessel.tank"),
    ("CH-3201", "Cation exchange", "column.packed"),
    ("CH-3301", "Anion exchange", "column.packed"),
    ("VF-3401", "Viral filtration", "filter.cartridge"),
    ("UF-3501", "UF/DF", "filter.cartridge"),
)
# role -> (low, high): the range Analytics' Signal quality monitor expects. Illustrative.
RANGES = {
    "ph": (6.8, 7.3),
    "do": (30.0, 60.0),
    "temperature": (32.0, 37.5),
    "volume": (1400.0, 2000.0),
}
# name, role, kind, limit, deadband. Limits are illustrative, like the app's tolerances.
RULES = (
    ("BR-2001 dissolved oxygen low", "do", "low", 30.0, 1.0),
    ("BR-2001 pH low", "ph", "low", 6.8, 0.02),
    ("BR-2001 pH high", "ph", "high", 7.3, 0.02),
    ("BR-2001 temperature high", "temperature", "high", 37.5, 0.2),
)
DOCUMENTS = (
    ("verification-report.md", "BatchLens verification report"),
    ("scientific-assumptions.md", "BatchLens scientific assumptions"),
    ("demo.md", "BatchLens demo and tour"),
)


class Suite:
    """The suite at one address, as the signed-in person of the local demo."""

    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        self.call("GET", "/api/session")
        if os.environ.get("PLANTCRAFT_BASIC_AUTH_ENABLED") == "true":  # sign-in is on
            secret = (
                Path(os.environ["PLANTCRAFT_BASIC_AUTH_PASSWORD_FILE"]).read_text().rstrip("\r\n")
            )
            name = os.environ["PLANTCRAFT_BASIC_AUTH_USERNAME"]
            self.call("POST", "/api/login", {"username": name, "password": secret})

    def call(self, method: str, path: str, body: Any = None, raw: bytes | None = None) -> Any:
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        kind = "application/octet-stream" if raw is not None else "application/json"
        request = urllib.request.Request(self.base + path, data=data, method=method)  # noqa: S310
        request.add_header("Content-Type", kind)
        with self.opener.open(request, timeout=30) as response:
            text = response.read().decode("utf-8")
        return json.loads(text) if text.strip().startswith(("{", "[")) else text

    def has(self, prefix: str) -> bool:
        try:
            self.call("GET", f"/{prefix}/healthz")
        except (urllib.error.URLError, OSError):
            return False
        return True


def dashboard() -> dict[str, Any]:
    def item(role: str) -> dict[str, str]:
        return {"asset_id": BIOREACTOR, "role": role, "label": SIGNALS[role][0]}

    cards: list[dict[str, Any]] = [
        {
            "card_id": "now",
            "title": "Bioreactor, last 24 hours",
            "kind": "table",
            "items": [item(role) for role in SIGNALS],
            "window": "24h",
            "width": 12,
            "height": 3,
        }
    ]
    cards += [
        {
            "card_id": f"trend-{role}",
            "title": f"{SIGNALS[role][0]}, last 7 days",
            "kind": "trend",
            "items": [item(role)],
            "window": "7d",
            "width": 6,
            "height": 4,
        }
        for role in SIGNALS
    ]
    return {
        "name": "Bioreactor BR-2001",
        "description": "The production bioreactor's online signals. Synthetic demo data.",
        "context_kind": None,
        "refresh_seconds": 60,
        "cards": cards,
    }


def diagram() -> dict[str, Any]:
    """The train left to right in process order, the bioreactor's values under it."""

    page, width, height, top, pitch = "p1", 80.0, 100.0, 300.0, 185.0
    elements: list[dict[str, Any]] = [
        {
            "id": "title",
            "page": page,
            "type": "text",
            "x": 40.0,
            "y": 40.0,
            "text": "mAb drug substance train",
            "size": 18,
            "align": "start",
            "bold": True,
        }
    ]
    for index, (asset_id, label, symbol) in enumerate(TRAIN):
        left = 80.0 + pitch * index
        elements.append(
            {
                "id": f"e-{asset_id}",
                "page": page,
                "type": "symbol",
                "symbol": symbol,
                "x": left,
                "y": top,
                "w": width,
                "h": height,
                "rotate": 0,
                "flip": False,
                "label": label,
                "label_position": "below",
                "asset_id": asset_id,
            }
        )
        if index:
            middle = top + height / 2
            elements.append(
                {
                    "id": f"l-{asset_id}",
                    "page": page,
                    "type": "line",
                    "kind": "process",
                    "points": [[left - pitch + width + 10, middle], [left - 10, middle]],
                    "arrow": "end",
                }
            )
    for row, role in enumerate(SIGNALS):
        elements.append(
            {
                "id": f"v-{role}",
                "page": page,
                "type": "value",
                "x": 60.0,
                "y": top + height + 60 + 28 * row,
                "item": {"asset_id": BIOREACTOR, "role": role, "roles": [], "label": ""},
                "label": SIGNALS[role][0],
                "show_label": True,
                "show_unit": True,
                "size": 13,
                "limits": {},
            }
        )
    return {
        "name": "mAb process train",
        "description": "The synthetic mAb train in process order, with the bioreactor's values.",
        "width": 1600,
        "height": 900,
        "grid": 10,
        "refresh_seconds": 60,
        "default_window": "24h",
        "pages": [{"id": page, "name": "Train"}],
        "parts": [],
        "elements": elements,
    }


def signal_id(role: str) -> str:
    return f"{SOURCE}:BIO.{BIOREACTOR}.{role.upper()}"


def seed(suite: Suite, csv_path: str | None = None, time_zone: str = "UTC") -> dict[str, int]:
    made = {"sources": 0, "points": 0, "ranges": 0, "dashboards": 0, "diagrams": 0}
    made |= {"rules": 0, "documents": 0}
    if suite.has("hist") and csv_path:
        loops_path = str(Path(csv_path).with_name("bioreactor-loops.csv"))
        recorded = [
            (f"BIO.{BIOREACTOR}.{role.upper()}", f"{BIOREACTOR} {label}", unit)
            for role, (label, unit) in SIGNALS.items()
        ]
        fast = [
            (f"LOOP.{loop_id}.{part.upper()}", f"{loop_id} {label}", "%" if part == "op" else unit)
            for loop_id, unit in LOOP_UNITS.items()
            for part, label in (("pv", "value"), ("sp", "setpoint"), ("op", "output"))
        ]
        files = (
            (SOURCE, "BatchLens synthetic bioreactor", csv_path, recorded),
            (LOOP_SOURCE, "BatchLens synthetic loops", loops_path, fast),
        )
        known = {source["id"] for source in suite.call("GET", "/hist/api/sources")}
        for source_id, name, path, tags in files:
            if source_id not in known:
                source = {
                    "id": source_id,
                    "name": name,
                    "kind": "csv",
                    "endpoint": path,
                    "options": {"timezone": time_zone, "check_minutes": 1},
                }
                suite.call("POST", "/hist/api/sources", source)
                made["sources"] += 1
            listed = suite.call("GET", f"/hist/api/points?source={source_id}")
            rows = listed["items"] if isinstance(listed, dict) else listed
            have = {point.get("tag") for point in rows}
            points = [
                {"tag": tag, "source_id": source_id, "name": label, "unit": unit}
                for tag, label, unit in tags
                if tag not in have
            ]
            if points:
                suite.call("POST", "/hist/api/points", {"points": points})
                made["points"] += len(points)
    if suite.has("link"):
        try:  # Analytics lists a new plant's signals on its own schedule: ask now
            suite.call("POST", "/link/api/signals/sync")
        except urllib.error.HTTPError as error:
            LOGGER.info("Analytics did not sync its signals now (%s)", error.code)
        for role, (low, high) in RANGES.items():
            path = "/link/api/signals/" + urllib.parse.quote(signal_id(role), safe=":")
            try:
                current = suite.call("GET", path).get("settings") or {}
            except urllib.error.HTTPError:
                continue  # Analytics has not listed the signal yet; the next start sets it
            if (current.get("low"), current.get("high")) != (low, high):
                suite.call("PATCH", path, {"low": low, "high": high})
                made["ranges"] += 1
        for path, body in (
            ("/link/api/signal-quality/run", None),
            ("/link/api/loops/sync", None),
            ("/link/api/round", {}),
        ):
            try:
                suite.call("POST", path, body)
            except urllib.error.HTTPError as error:  # 409: one is already waiting
                LOGGER.info("Analytics did not take %s now (%s)", path, error.code)
    if suite.has("dash"):
        if dashboard()["name"] not in {
            d["name"] for d in suite.call("GET", "/dash/api/dashboards")
        }:
            suite.call("POST", "/dash/api/dashboards", dashboard())
            made["dashboards"] += 1
        if diagram()["name"] not in {d["name"] for d in suite.call("GET", "/dash/api/diagrams")}:
            suite.call("POST", "/dash/api/diagrams", diagram())
            made["diagrams"] += 1
        # View's own first step for a new plant: an overview of the unit's loops.
        made["dashboards"] += suite.call("POST", "/dash/api/start/unit-overviews", START)["counts"][
            "created"
        ]
    if suite.has("alarm"):
        taken = {rule["name"] for rule in suite.call("GET", "/alarm/api/rules")}
        for name, role, kind, limit, deadband in RULES:
            if name in taken:
                continue
            rule = {
                "name": name,
                "signal_id": signal_id(role),
                "kind": kind,
                "limit": limit,
                "unit": SIGNALS[role][1],
                "deadband": deadband,
                "on_delay_seconds": 600,
                "priority": "medium",
                "cause": "An illustrative limit of the synthetic demo, not a process limit.",
            }
            suite.call("POST", "/alarm/api/rules/from-signal", rule)
            made["rules"] += 1
        # Alarms' own first step: a loop in poor shape, a signal without data; switched off.
        made["rules"] += suite.call("POST", "/alarm/api/start/draft-rules", START)["counts"][
            "created"
        ]
    if suite.has("doc"):
        taken = {doc["title"] for doc in suite.call("GET", "/doc/api/documents")}
        for filename, title in DOCUMENTS:
            if title in taken:
                continue
            query = urllib.parse.urlencode({"filename": filename, "title": title, "unit": UNIT})
            sent = suite.call(
                "POST", f"/doc/api/documents?{query}", raw=(DOCS / filename).read_bytes()
            )
            suite.call("PUT", f"/doc/api/documents/{sent['doc_id']}/assets", {"assets": [UNIT]})
            made["documents"] += 1
    return made


def main(argv: list[str]) -> int:
    if len(argv) not in (1, 3):
        sys.stderr.write(__doc__ or "")
        return 2
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        made = seed(Suite(argv[0]), *argv[1:])
    except urllib.error.HTTPError as error:
        LOGGER.error("%s %s: %s", error.code, error.url, error.read().decode("utf-8")[:300])
        return 1
    LOGGER.info("suite modules: %s", json.dumps(made))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
