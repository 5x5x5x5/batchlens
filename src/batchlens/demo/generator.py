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
    Transfer,
)

# Raised when what the generator makes changes, so a database seeded by an older one is
# recognised (demo/seed.py). 2: the rest of the purification train and the pool genealogy.
# 3: the seed train before the production culture. 4: transfers.
VERSION = "synthetic-generator/4"
PRODUCT = "mAb-X"
# Asset ids of the synthetic plant (tests/plant.py serves them from the fake PlantCraft).
BIOREACTOR = "BR-2001"
# The seed train, in process order: (phase kind, asset id, working volume in litres). Each
# passage grows for SEED_DAYS from SEED_DENSITY to about seven times that, and is then moved
# into the next vessel.
SEED_TRAIN = (("seed_n2", "BR-1001", 50.0), ("seed_n1", "BR-1002", 250.0))
SEED_DAYS = 3
SEED_DENSITY = 0.5  # 1e6 cells/mL, the target after every transfer, the production one too
SEED_RATE = math.log(7.0) / SEED_DAYS  # per day
FEED_TANK = "MH-1201"  # the feed medium's hold tank
TRANSFER_MINUTES = {"passage": 30, "inoculation": 30, "feed": 10}  # how long each takes
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
# The bioreactor's control loops, by the role of the signal each one controls. A loop's values
# are fast (loop monitoring wants seconds, not the 10 minutes of the recorded signals) and are
# made on request for a window of time (``loop_series``), not kept with the batch.
LOOP_INTERVAL_SECONDS = 30
LOOP_ROLES = ("temperature", "ph", "do")
# role: the output's load (%) at culture day 0 and at day 14, its gain in % per unit of error,
# its noise (%), the noise of the fast value between two recorded ones, and how much of the
# recorded value's distance from the setpoint the fast value keeps. Illustrative.
LOOP_SHAPE = {
    "temperature": (42.0, 30.0, 20.0, 0.4, 0.01, 1.0),  # jacket valve: less heating as cells warm
    "ph": (30.0, 14.0, 150.0, 0.5, 0.003, 1.0),  # CO2 and base: less as lactate is consumed
    # Oxygen sparge: more as the cell density grows. The recorded dissolved oxygen scatters by
    # 1.5 % around its setpoint, which a loop monitor reads as a loop that is not holding; the
    # controller's own value keeps 15 % of that scatter, as a filtered measurement would.
    "do": (8.0, 58.0, 2.0, 0.8, 0.05, 0.15),
}

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
    # The N-1 passage's growth rate is multiplied by this. Below about 0.8 the whole N-1
    # vessel holds too few cells for the production culture's target, and the culture starts
    # at a lower density.
    n1_growth_factor: float = 1.0
    # Record-keeping problems, not process ones: the culture itself is unchanged.
    # The sample (counted from 0) whose collection time was keyed in as the one before it.
    mis_keyed_sample: int | None = None
    # The feed (counted from 0) whose volume was written down with a digit dropped: 6 L for
    # 60 L. The feed itself was the usual one.
    mis_recorded_feed: int | None = None
    # Culture days between which the historian kept nothing.
    online_gap_days: tuple[float, float] | None = None
    # A purification step's nominal yield, where it is not DOWNSTREAM's: {phase kind: fraction}.
    downstream_yields: dict[str, float] = field(default_factory=dict)


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
    # The true growth rate of each seed passage, per day: {phase kind: rate}.
    seed_growth_rates: dict[str, float] = field(default_factory=dict)
    inoculation_density: float = SEED_DENSITY  # 1e6 cells/mL, the production culture's start
    mis_recorded_transfer: str | None = None  # the transfer id


def _vcd(day: float, peak: float, rate: float, first: float = SEED_DENSITY) -> float:
    """Logistic growth from ``first`` (1e6 cells/mL) to ``peak``, then a slow decline from
    day 9."""

    grown = peak / (1 + (peak - first) / first * math.exp(-rate * day))
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


def loop_setpoint(role: str, day: float) -> float:
    if role == "temperature":
        return round(36.5 - 3.5 * min(1.0, max(0.0, (day - TEMPERATURE_SHIFT_DAY) * 12)), 2)
    return {"ph": 7.0, "do": 40.0}[role]


def loop_series(
    batch: Observations, since: datetime, until: datetime
) -> dict[str, list[tuple[datetime, float]]]:
    """The control loops' value, setpoint and output (``"<role>.pv"``, ``.sp``, ``.op``) every
    ``LOOP_INTERVAL_SECONDS`` of the batch's culture between ``since`` and ``until``.

    The fast value follows the recorded values of the same signal (straight lines between
    them, plus a little noise that is zero at the recorded instants): through every one of them
    for temperature and pH, and for dissolved oxygen keeping a part of their scatter around the
    setpoint (``LOOP_SHAPE``). The output is a
    load that moves over the culture plus a proportional answer to the error, clipped to
    0..100 %. That is the shape of a loop that is working, not a model of a controller. Each
    point has its own random stream, so any window gives the same values and no value that
    existed before the loops is changed. Nothing is made across a hole in the recorded values."""

    start = batch.record.phase("production_culture").start
    batch_id = batch.record.batch.batch_id
    series: dict[str, list[tuple[datetime, float]]] = {}
    for role in LOOP_ROLES:
        first, last, gain, noise, between, kept = LOOP_SHAPE[role]
        recorded = batch.online[role]
        values, setpoints, outputs = [], [], []
        for (left_at, left), (right_at, right) in zip(recorded, recorded[1:]):
            if right_at <= since or left_at > until:
                continue
            if (right_at - left_at).total_seconds() > ONLINE_INTERVAL_SECONDS:
                continue  # a hole in the record: no fast values either
            steps = ONLINE_INTERVAL_SECONDS // LOOP_INTERVAL_SECONDS
            for step in range(steps):
                moment = left_at + timedelta(seconds=step * LOOP_INTERVAL_SECONDS)
                if not since <= moment <= until:
                    continue
                seconds = (moment - start).total_seconds()
                rng = random.Random(f"{batch_id}/loop/{role}/{int(seconds)}")
                day = seconds / 86400
                setpoint = loop_setpoint(role, day)
                recorded_here = left + (right - left) * step / steps
                value = setpoint + kept * (recorded_here - setpoint)
                value += rng.gauss(0, between) if step else 0
                load = first + (last - first) / (1 + math.exp(-(day - CULTURE_DAYS / 2)))
                output = load + gain * (setpoint - value) + rng.gauss(0, noise)
                values.append((moment, round(value, 3)))
                setpoints.append((moment, setpoint))
                outputs.append((moment, round(min(100.0, max(0.0, output)), 1)))
        series[f"{role}.pv"], series[f"{role}.sp"], series[f"{role}.op"] = (
            values,
            setpoints,
            outputs,
        )
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

    # The seed train, from a generator of its own, so that adding it left every other value
    # of a batch as it was. Each passage is seeded at the target density unless the vessel
    # before it held too few cells; the production culture likewise (``first``).
    seeding = random.Random(f"{seed}/seed-train")
    seed_phases, seed_samples, seed_results, seed_rates = [], [], [], {}
    # Transfers, again from a generator of their own.
    moving = random.Random(f"{seed}/transfers")
    transfers: list[Transfer] = []

    def moved(kind: str, source: str, target: str, end: datetime, litres: float) -> None:
        transfers.append(
            Transfer(
                f"{batch_id}-T{len(transfers) + 1:02d}",
                batch_id,
                kind,
                source,
                target,
                end - timedelta(minutes=TRANSFER_MINUTES[kind]),
                end,
                round(litres, 1),
                VOLUME_UNIT,
                "",
                provenance,
            )
        )

    first, passage_start = SEED_DENSITY, start - timedelta(days=SEED_DAYS * len(SEED_TRAIN))
    for position, (kind, asset_id, litres) in enumerate(SEED_TRAIN):
        factor = scenario.n1_growth_factor if kind == "seed_n1" else 1.0
        rate_here = SEED_RATE * seeding.gauss(1, 0.02) * factor
        seed_rates[kind] = rate_here
        short = kind.removeprefix("seed_").upper()
        phase = PhaseExecution(
            f"{batch_id}-{short}",
            batch_id,
            kind,
            asset_id,
            passage_start,
            passage_start + timedelta(days=SEED_DAYS),
            provenance,
        )
        seed_phases.append(phase)
        # One count an hour after seeding, one each day, one an hour before the transfer.
        ages = [1 / 24, *(d + seeding.uniform(-3, 3) / 24 for d in range(1, SEED_DAYS))]
        for index, age in enumerate([*ages, SEED_DAYS - 1 / 24]):
            collected = passage_start + timedelta(seconds=round(age * 86400))
            sample_id = f"{batch_id}-{short}-S{index + 1:02d}"
            seed_samples.append(Sample(sample_id, batch_id, phase.phase_id, collected, provenance))
            values = {"vcd": first * math.exp(rate_here * age), "viability": 98.5 - 0.1 * age}
            for analyte, value in values.items():
                measured = value * seeding.gauss(1, NOISE[analyte])
                seed_results.append(
                    AssayResult(
                        f"{sample_id}-{analyte}",
                        sample_id,
                        analyte,
                        round(measured, DECIMALS[analyte]),
                        UNITS[analyte],
                        METHODS[analyte],
                        collected + timedelta(seconds=round(seeding.uniform(0.5, 3) * 3600)),
                        "valid",
                        provenance,
                    )
                )
        # What the next vessel starts at: the target, or all this one held, diluted into it.
        next_litres = (
            SEED_TRAIN[position + 1][2] if position + 1 < len(SEED_TRAIN) else START_LITRES
        )
        grown = first * math.exp(rate_here * SEED_DAYS)
        last = position + 1 == len(SEED_TRAIN)
        moved(
            "inoculation" if last else "passage",
            asset_id,
            BIOREACTOR if last else SEED_TRAIN[position + 1][1],
            phase.end,
            # What reaches the target density in the next vessel, or all there is.
            min(litres, SEED_DENSITY * next_litres / grown) * moving.gauss(1, 0.005),
        )
        first = min(SEED_DENSITY, grown * litres / next_litres)
        passage_start = phase.end
    for feed in range(FEEDS):
        litres = FEED_LITRES * moving.gauss(1, 0.005)
        if feed == scenario.mis_recorded_feed:
            litres /= 10
        moved("feed", FEED_TANK, BIOREACTOR, start + timedelta(days=FIRST_FEED_DAY + feed), litres)
    mis_recorded = (
        None
        if scenario.mis_recorded_feed is None
        else transfers[len(SEED_TRAIN) + scenario.mis_recorded_feed].transfer_id
    )

    # Roughly daily samples at irregular times: one an hour after inoculation, then each day
    # within three hours of the same clock time.
    days = [1 / 24] + [day + rng.uniform(-3, 3) / 24 for day in range(1, 15)]
    samples, results = [], []
    integral = titer = 0.0
    for index, day in enumerate(days):
        density = _vcd(day, peak, rate, first)
        if index:
            before = days[index - 1]
            step = 0.5 * (_vcd(before, peak, rate, first) + density) * (day - before)
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
        true_yields[kind] = scenario.downstream_yields.get(kind, nominal) * later.gauss(1, 0.005)
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
        (*seed_phases, *phases, *more_phases),
        (*seed_samples, *samples),
        tuple(sorted([*seed_results, *results], key=lambda result: result.result_id)),
        tuple(sorted(pools, key=lambda item: (item.measured_at, item.measurement_id))),
        tuple(links),
        tuple(transfers),
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
        seed_rates,
        first,
        mis_recorded,
    )
    return Observations(record, _online(rng, start, scenario.online_gap_days)), truth_out


CAMPAIGN_START = datetime(2026, 7, 1, 6, 0, tzinfo=UTC)
DAYS_BETWEEN_BATCHES = 21


# The last three batches of the campaign before this one: normal, kept to compare with.
EARLIER = (("BK-0007", 97), ("BK-0008", 98), ("BK-0009", 99))
# The batches the demo marks as comparable (ordinary batch context a person assigns, like the
# reference): the earlier campaign's and this campaign's first two.
COMPARABLE = ("BK-0007", "BK-0008", "BK-0009", "BL-0001", "BL-0002")
LIVE_BATCH = "BL-0007"
LIVE_CULTURE_DAYS = 9  # how far into its culture the live batch is when the demo starts


def live_start(now: datetime) -> datetime:
    """When the live batch's culture began, for a demo started at ``now``: 06:00 UTC,
    ``LIVE_CULTURE_DAYS`` days before today, so every batch keeps its time of day."""

    day = now.astimezone(UTC).replace(hour=6, minute=0, second=0, microsecond=0)
    return day - timedelta(days=LIVE_CULTURE_DAYS)


def demo_campaign(
    live_from: datetime | None = None,
) -> tuple[list[Observations], dict[str, GroundTruth]]:
    """The demo batches, one after another on the same bioreactor (docs/demo.md): three
    normal ones from an earlier campaign (``EARLIER``), then the six of this campaign.

    With ``live_from`` (``live_start``), the same six moved in time to end before a seventh,
    ``LIVE_BATCH``, whose culture begins then: generated whole like the others, its later
    records dated ahead of the clock. The app shows nothing later than now, and the plant
    files hold nothing later than now. Moving a batch in time changes none of its values."""

    first = (
        CAMPAIGN_START
        if live_from is None
        else live_from - timedelta(days=6 * DAYS_BETWEEN_BATCHES)
    )

    def start(index: int) -> datetime:
        return first + timedelta(days=DAYS_BETWEEN_BATCHES * index)

    scenarios = [
        *(
            (Scenario(batch_id, start(index - len(EARLIER))), seed)
            for index, (batch_id, seed) in enumerate(EARLIER)
        ),
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
                mis_recorded_feed=6,
                online_gap_days=(13.4, 14.25),
            ),
            105,
        ),
        # Its last seed passage grew slowly: the culture began with too few cells.
        (Scenario("BL-0006", start(5), label="low_inoculum", n1_growth_factor=0.4), 107),
    ]
    if live_from is not None:
        live = Scenario(
            LIVE_BATCH,
            start(6),
            label="reduced_culture_productivity",
            qp_shift_day=7.0,
            qp_shift_factor=0.6,
        )
        # The live batch keeps the seed it had before the sixth finished batch was added.
        scenarios.append((live, 106))
    made = [generate(scenario, seed) for scenario, seed in scenarios]
    return [observations for observations, _ in made], {t.batch_id: t for _, t in made}
