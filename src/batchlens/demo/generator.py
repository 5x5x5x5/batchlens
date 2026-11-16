"""Four synthetic mAb batches, as a deterministic function of (scenario parameters, seed).

Illustrative throughout: a 2,000 L CHO fed-batch production culture of about 14 days on one
bioreactor, harvest, and one aggregated Protein A capture step. It is a shape generator, not a
mechanistic or validated model, and no number, tag, name or limit comes from a real facility
(docs/scientific-assumptions.md lists the model and every parameter).

``generate`` answers observations (what the app may see) and ground truth (the scenario label
and its parameters) as separate objects. Ground truth is for tests and documents only: it is
never stored in the app's database, returned by the API or read by ``calc`` or ``analysis``.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from batchlens.batches.models import (
    AssayResult,
    Batch,
    BatchRecord,
    PhaseExecution,
    PoolMeasurement,
    Sample,
)

VERSION = "synthetic-generator/1"
PRODUCT = "mAb-X (synthetic)"
# Asset ids of the synthetic plant (tests/plant.py serves them from the fake PlantCraft).
BIOREACTOR = "BR-2001"
HARVEST_SKID = "HV-2101"
PROTEIN_A_SKID = "CH-3001"
# The bioreactor's online signals: role -> unit.
ONLINE_UNITS = {"ph": "pH", "do": "% air sat.", "temperature": "°C", "volume": "L"}
VOLUME_UNIT = ONLINE_UNITS["volume"]
ONLINE_INTERVAL_SECONDS = 600

CULTURE_DAYS = 14.25  # the last sample is taken near day 14
TEMPERATURE_SHIFT_DAY = 6.0  # the one planned shift, 36.5 to 33.0 °C
FIRST_FEED_DAY, FEEDS, FEED_LITRES, START_LITRES = 3, 10, 60.0, 1400.0  # 2,000 L after day 12

METHODS = {
    "vcd": "Automated cell counter, trypan blue exclusion",
    "viability": "Automated cell counter, trypan blue exclusion",
    "glucose": "Enzymatic biochemistry analyser",
    "lactate": "Enzymatic biochemistry analyser",
    "titer": "Protein A HPLC",
}
UNITS = {
    "vcd": "1e6 cells/mL",
    "viability": "%",
    "glucose": "g/L",
    "lactate": "g/L",
    "titer": "g/L",
}
POOL_METHOD = "UV absorbance at 280 nm"
# Assay noise, one standard deviation relative to the value.
NOISE = {"vcd": 0.03, "viability": 0.005, "glucose": 0.03, "lactate": 0.03, "titer": 0.02}
DECIMALS = {"vcd": 2, "viability": 1, "glucose": 2, "lactate": 2, "titer": 3}


@dataclass(frozen=True)
class Scenario:
    batch_id: str
    start: datetime
    label: str = "normal"
    is_reference: bool = False
    qp: float = 30.0  # pg/cell/day
    qp_shift_day: float | None = None  # from this day on, qP is multiplied by qp_shift_factor
    qp_shift_factor: float = 1.0
    harvest_to_load_yield: float = 0.93
    protein_a_recovery: float = 0.92


@dataclass(frozen=True)
class Observations:
    """What the app may see: the batch's records, and the bioreactor's online values during its
    production phase as ``{role: [(instant, value), ...]}``."""

    record: BatchRecord
    online: dict[str, list[tuple[datetime, float]]]


@dataclass(frozen=True)
class GroundTruth:
    batch_id: str
    scenario: str
    seed: int
    qp_nominal: float
    qp_shift_day: float | None
    qp_shift_factor: float
    ivcd: float  # trapezoid over the noise-free cell density at the sample times
    qp_culture_average: float  # 1000 * true final titer / ivcd
    harvest_mass: float  # g, true final titer times true volume
    harvest_to_load_yield: float  # fraction
    protein_a_recovery: float  # fraction


def _vcd(day: float, peak: float, rate: float) -> float:
    """Logistic growth from 0.5e6 cells/mL to ``peak``, then a slow decline from day 9."""

    grown = peak / (1 + (peak - 0.5) / 0.5 * math.exp(-rate * day))
    return grown * math.exp(-0.03 * max(0.0, day - 9))


def _volume(day: float) -> float:
    feeds = min(FEEDS, max(0, math.floor(day) - FIRST_FEED_DAY + 1))
    return START_LITRES + FEED_LITRES * feeds


def _online(rng: random.Random, start: datetime) -> dict[str, list[tuple[datetime, float]]]:
    series: dict[str, list[tuple[datetime, float]]] = {role: [] for role in ONLINE_UNITS}
    for index in range(int(CULTURE_DAYS * 86400 / ONLINE_INTERVAL_SECONDS) + 1):
        seconds = index * ONLINE_INTERVAL_SECONDS
        moment, day = start + timedelta(seconds=seconds), seconds / 86400
        shift = min(1.0, max(0.0, (day - TEMPERATURE_SHIFT_DAY) * 12))  # ramp over 2 h
        values = {
            "ph": 7.0 + 0.03 * math.sin(2 * math.pi * day) + rng.gauss(0, 0.01),
            "do": 40.0 + rng.gauss(0, 1.5),
            "temperature": 36.5 - 3.5 * shift + rng.gauss(0, 0.05),
            "volume": _volume(day) + rng.gauss(0, 0.5),
        }
        for role, value in values.items():
            series[role].append((moment, round(value, 2 if role != "volume" else 1)))
    return series


def generate(scenario: Scenario, seed: int) -> tuple[Observations, GroundTruth]:
    """One batch. The same scenario and seed give identical output on every run and machine."""

    rng = random.Random(seed)
    batch_id, start = scenario.batch_id, scenario.start
    provenance = f"{VERSION} seed={seed}"
    # Ordinary batch-to-batch variability.
    peak, rate = 20.0 * rng.gauss(1, 0.03), 0.75 * rng.gauss(1, 0.02)
    qp = scenario.qp * rng.gauss(1, 0.02)

    culture_end = start + timedelta(days=CULTURE_DAYS)
    harvest_end = culture_end + timedelta(hours=6)
    capture_start = harvest_end + timedelta(hours=4)
    capture_end = capture_start + timedelta(hours=10)
    phases = (
        PhaseExecution(
            f"{batch_id}-P1",
            batch_id,
            "production_culture",
            BIOREACTOR,
            start,
            culture_end,
            provenance,
        ),
        PhaseExecution(
            f"{batch_id}-P2",
            batch_id,
            "harvest",
            HARVEST_SKID,
            culture_end,
            harvest_end,
            provenance,
        ),
        PhaseExecution(
            f"{batch_id}-P3",
            batch_id,
            "protein_a_capture",
            PROTEIN_A_SKID,
            capture_start,
            capture_end,
            provenance,
        ),
    )

    # Roughly daily samples at irregular times: one an hour after inoculation, then each day
    # within three hours of the same clock time.
    days = [1 / 24] + [day + rng.uniform(-3, 3) / 24 for day in range(1, 15)]
    samples, results = [], []
    integral = titer = 0.0
    for index, day in enumerate(days):
        density = _vcd(day, peak, rate)
        if index:
            before = days[index - 1]
            step = 0.5 * (_vcd(before, peak, rate) + density) * (day - before)
            shifted = (
                scenario.qp_shift_day is not None and 0.5 * (before + day) >= scenario.qp_shift_day
            )
            # Titer follows qP and the running IVCD, so calc can be checked against qp.
            titer += qp * (scenario.qp_shift_factor if shifted else 1.0) * step / 1000
            integral += step
        late = scenario.qp_shift_day is not None and day >= scenario.qp_shift_day
        truth = {
            "vcd": density,
            "viability": 98.0 - 0.05 * day * day,
            # A daily sawtooth of consumption and feed; shifted when productivity falls.
            "glucose": 6.0 - 0.18 * density * (day % 1) + (0.8 if late else 0.0),
            "lactate": 0.3
            + 1.7 * math.exp(-(((day - 4) / 2) ** 2))
            + (0.25 * (day - scenario.qp_shift_day) if late else 0.0),
            "titer": titer,
        }
        collected = start + timedelta(seconds=round(day * 86400))
        sample_id = f"{batch_id}-S{index + 1:02d}"
        samples.append(Sample(sample_id, batch_id, phases[0].phase_id, collected, provenance))
        for analyte, value in truth.items():
            # Cell counts and metabolites within hours; titer many hours later.
            hours = rng.uniform(18, 30) if analyte == "titer" else rng.uniform(0.5, 3)
            measured = max(0.0, value * rng.gauss(1, NOISE[analyte]))
            results.append(
                AssayResult(
                    f"{sample_id}-{analyte}",
                    sample_id,
                    analyte,
                    round(measured, DECIMALS[analyte]),
                    UNITS[analyte],
                    METHODS[analyte],
                    collected + timedelta(seconds=round(hours * 3600)),
                    "valid",
                    provenance,
                )
            )

    harvest_mass = titer * _volume(days[-1])
    step_yield = scenario.harvest_to_load_yield * rng.gauss(1, 0.005)
    recovery = scenario.protein_a_recovery * rng.gauss(1, 0.005)
    load_mass, load_volume = harvest_mass * step_yield, 1920.0 + rng.uniform(-10, 10)
    eluate_mass = load_mass * recovery
    eluate_volume = eluate_mass / 18.0 * rng.uniform(0.97, 1.03)

    def pool(name: str, mass: float, volume: float, measured_at: datetime) -> PoolMeasurement:
        return PoolMeasurement(
            f"{batch_id}-{name}",
            batch_id,
            phases[2].phase_id,
            name,
            round(volume, 1),
            "L",
            round(mass / volume * rng.gauss(1, 0.01), 2),
            "g/L",
            POOL_METHOD,
            measured_at,
            measured_at + timedelta(seconds=round(rng.uniform(2, 4) * 3600)),
            provenance,
        )

    pools = (
        pool("protein_a_load", load_mass, load_volume, capture_start - timedelta(hours=1)),
        pool("protein_a_eluate", eluate_mass, eluate_volume, capture_end + timedelta(minutes=30)),
    )
    record = BatchRecord(
        Batch(batch_id, PRODUCT, scenario.is_reference, start, provenance),
        phases,
        tuple(samples),
        tuple(sorted(results, key=lambda result: result.result_id)),
        pools,
    )
    truth_out = GroundTruth(
        batch_id,
        scenario.label,
        seed,
        qp,
        scenario.qp_shift_day,
        scenario.qp_shift_factor,
        integral,
        1000 * titer / integral,
        harvest_mass,
        step_yield,
        recovery,
    )
    return Observations(record, _online(rng, start)), truth_out


CAMPAIGN_START = datetime(2026, 7, 1, 6, 0, tzinfo=UTC)
DAYS_BETWEEN_BATCHES = 21


def demo_campaign() -> tuple[list[Observations], dict[str, GroundTruth]]:
    """The four demo batches, one after another on the same bioreactor (docs/demo.md)."""

    def start(index: int) -> datetime:
        return CAMPAIGN_START + timedelta(days=DAYS_BETWEEN_BATCHES * index)

    scenarios = [
        (Scenario("BL-0001", start(0), is_reference=True), 101),
        (Scenario("BL-0002", start(1)), 102),
        (
            Scenario(
                "BL-0003",
                start(2),
                label="reduced_culture_productivity",
                qp_shift_day=7.0,
                qp_shift_factor=0.55,
            ),
            103,
        ),
        (
            Scenario(
                "BL-0004", start(3), label="reduced_protein_a_recovery", protein_a_recovery=0.74
            ),
            104,
        ),
    ]
    made = [generate(scenario, seed) for scenario, seed in scenarios]
    return [observations for observations, _ in made], {t.batch_id: t for _, t in made}
