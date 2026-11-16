"""Synthetic mAb batches, as a deterministic function of (scenario parameters, seed).

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
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from batchlens.batches.models import (
    AssayResult,
    Batch,
    BatchRecord,
    PhaseExecution,
    PoolLink,
    PoolMeasurement,
    Sample,
)

# Raised when what the generator makes changes, so a database seeded by an older one is
# recognised (demo/seed.py). 2: the rest of the purification train and the pool genealogy.
VERSION = "synthetic-generator/2"
PRODUCT = "mAb-X (synthetic)"
# Asset ids of the synthetic plant (tests/plant.py serves them from the fake PlantCraft).
BIOREACTOR = "BR-2001"
HARVEST_SKID = "HV-2101"
PROTEIN_A_SKID = "CH-3001"
# The rest of the purification train, in process order:
# (phase kind, asset id, the pool it produces, nominal step yield, hours it takes).
DOWNSTREAM = (
    ("viral_inactivation", "VI-3101", "viral_inactivation_pool", 0.98, 3),
    ("cation_exchange", "CH-3201", "cation_exchange_pool", 0.90, 8),
    ("anion_exchange", "CH-3301", "anion_exchange_pool", 0.96, 6),
    ("viral_filtration", "VF-3401", "viral_filtrate", 0.98, 5),
    ("ufdf", "UF-3501", "drug_substance", 0.95, 8),
)
HOLD_HOURS = 2  # between two downstream steps
# Litres of the pool each step produces per gram of product in it (the last one is the drug
# substance at 50 g/L).
POOL_LITRES_PER_GRAM = {
    "viral_inactivation_pool": 1 / 16.0,
    "cation_exchange_pool": 1 / 12.0,
    "anion_exchange_pool": 1 / 10.0,
    "viral_filtrate": 1 / 9.5,
    "drug_substance": 1 / 50.0,
}
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
    # Record-keeping problems, not process ones: the culture itself is unchanged.
    # The sample (counted from 0) whose collection time was keyed in as the one before it.
    mis_keyed_sample: int | None = None
    # Culture days between which the historian kept nothing.
    online_gap_days: tuple[float, float] | None = None


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
    mis_keyed_sample: str | None = None  # the sample id
    online_gap_days: tuple[float, float] | None = None
    # The true yield of every purification step: {phase kind: fraction}.
    step_yields: dict[str, float] = field(default_factory=dict)


def _vcd(day: float, peak: float, rate: float) -> float:
    """Logistic growth from 0.5e6 cells/mL to ``peak``, then a slow decline from day 9."""

    grown = peak / (1 + (peak - 0.5) / 0.5 * math.exp(-rate * day))
    return grown * math.exp(-0.03 * max(0.0, day - 9))


def _volume(day: float) -> float:
    feeds = min(FEEDS, max(0, math.floor(day) - FIRST_FEED_DAY + 1))
    return START_LITRES + FEED_LITRES * feeds


def _online(
    rng: random.Random, start: datetime, gap: tuple[float, float] | None = None
) -> dict[str, list[tuple[datetime, float]]]:
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
        if gap is not None and gap[0] <= day <= gap[1]:
            continue  # drawn (so the noise is the same as without a gap) but never kept
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
        recorded_at = collected
        if index == scenario.mis_keyed_sample:
            recorded_at = samples[-1].collected_at  # keyed in as the sample before it
        sample_id = f"{batch_id}-S{index + 1:02d}"
        samples.append(Sample(sample_id, batch_id, phases[0].phase_id, recorded_at, provenance))
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

    load = pool("protein_a_load", load_mass, load_volume, capture_start - timedelta(hours=1))
    eluate = pool(
        "protein_a_eluate", eluate_mass, eluate_volume, capture_end + timedelta(minutes=30)
    )

    # Everything after the capture step draws from its own generator, so that adding the rest
    # of the train left every earlier value as it was.
    later = random.Random(f"{seed}/downstream")

    def later_pool(
        name: str, phase_id: str, mass: float, volume: float, at: datetime
    ) -> PoolMeasurement:
        return PoolMeasurement(
            f"{batch_id}-{name}",
            batch_id,
            phase_id,
            name,
            round(volume, 1),
            "L",
            round(mass / volume * later.gauss(1, 0.01), 2),
            "g/L",
            POOL_METHOD,
            at,
            at + timedelta(seconds=round(later.uniform(2, 4) * 3600)),
            provenance,
        )

    # The capture step ran as two cycles; their eluates were merged into the one eluate pool.
    share = later.uniform(0.48, 0.52)
    cycles = [
        later_pool(
            f"protein_a_eluate_cycle_{number}",
            phases[2].phase_id,
            eluate_mass * part,
            eluate_volume * part,
            capture_start + timedelta(hours=5 * number - 1),
        )
        for number, part in ((1, share), (2, 1 - share))
    ]
    pools, links = [load, *cycles, eluate], []

    def link(source: PoolMeasurement, target: PoolMeasurement) -> None:
        links.append(
            PoolLink(
                f"{batch_id}-L{len(links) + 1:02d}",
                batch_id,
                source.measurement_id,
                target.measurement_id,
                provenance,
            )
        )

    for cycle in cycles:
        link(load, cycle)
        link(cycle, eluate)
    true_yields = {"protein_a_capture": recovery}
    more_phases, previous, mass, clock = [], eluate, eluate_mass, capture_end
    for number, (kind, asset_id, pool_name, nominal, hours) in enumerate(DOWNSTREAM, start=4):
        begin = clock + timedelta(hours=HOLD_HOURS)
        clock = begin + timedelta(hours=hours)
        phase = PhaseExecution(
            f"{batch_id}-P{number}", batch_id, kind, asset_id, begin, clock, provenance
        )
        true_yields[kind] = nominal * later.gauss(1, 0.005)
        mass *= true_yields[kind]
        made = later_pool(
            pool_name,
            phase.phase_id,
            mass,
            mass * POOL_LITRES_PER_GRAM[pool_name] * later.uniform(0.97, 1.03),
            clock + timedelta(minutes=30),
        )
        link(previous, made)
        more_phases.append(phase)
        pools.append(made)
        previous = made
    record = BatchRecord(
        Batch(batch_id, PRODUCT, scenario.is_reference, start, provenance),
        (*phases, *more_phases),
        tuple(samples),
        tuple(sorted(results, key=lambda result: result.result_id)),
        tuple(sorted(pools, key=lambda item: (item.measured_at, item.measurement_id))),
        tuple(links),
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
        None if scenario.mis_keyed_sample is None else samples[scenario.mis_keyed_sample].sample_id,
        scenario.online_gap_days,
        true_yields,
    )
    return Observations(record, _online(rng, start, scenario.online_gap_days)), truth_out


CAMPAIGN_START = datetime(2026, 7, 1, 6, 0, tzinfo=UTC)
DAYS_BETWEEN_BATCHES = 21


def demo_campaign() -> tuple[list[Observations], dict[str, GroundTruth]]:
    """The five demo batches, one after another on the same bioreactor (docs/demo.md)."""

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
        (
            Scenario(
                "BL-0005",
                start(4),
                label="data_problem",
                mis_keyed_sample=8,
                online_gap_days=(13.4, 14.25),
            ),
            105,
        ),
    ]
    made = [generate(scenario, seed) for scenario, seed in scenarios]
    return [observations for observations, _ in made], {t.batch_id: t for _, t in made}
