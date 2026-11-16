"""Run the analysis over many seeded batches and count what it found against what was true.

Every batch is made by the demo generator with one thing varied: nothing (normal), a fall in
specific productivity from a given day, a lower Protein A recovery, or bad records. Each is
compared with several normal batches taken in turn as the reference, at several tolerances.
The same inputs always give the same numbers.
"""

from __future__ import annotations

import statistics
from typing import Any

from batchlens import calc
from batchlens.analysis.metrics import batch_metrics, measurements
from batchlens.demo.generator import (
    CAMPAIGN_START,
    VERSION,
    VOLUME_UNIT,
    GroundTruth,
    Observations,
    Scenario,
    generate,
)

TITER_TOLERANCES = (0.05, 0.10, 0.15, 0.20)
RECOVERY_TOLERANCES = (5.0, 10.0, 15.0)
ONSET_DAYS = (5.0, 7.0, 9.0)
QP_FACTORS = (0.55, 0.70, 0.85)
RECOVERIES = (0.74, 0.80, 0.86)
BAD_RECORDS = (
    {"mis_keyed_sample": 8},
    {"online_gap_days": (13.4, 14.25)},
    {"mis_keyed_sample": 8, "online_gap_days": (13.4, 14.25)},
)
FIRST_SEED, FIRST_REFERENCE_SEED = 1000, 9000
DEFAULT_BATCHES, DEFAULT_REFERENCES = 20, 5

Case = tuple[str, Observations, GroundTruth, dict[str, calc.Result]]


def _case(kind: str, seed: int, **changes: Any) -> Case:
    observations, truth = generate(
        Scenario(f"B{seed}", CAMPAIGN_START, label=kind, **changes), seed
    )
    volume = calc.Online("volume", VOLUME_UNIT, observations.online["volume"])
    results = {r.metric: r for r in batch_metrics(observations.record, volume)}
    return kind, observations, truth, results


def cases(batches: int) -> list[Case]:
    """``batches`` seeds of every variant, each batch with its own seed."""

    variants: list[tuple[str, dict[str, Any]]] = [("normal", {})]
    variants += [
        ("reduced_productivity", {"qp_shift_day": day, "qp_shift_factor": factor})
        for day in ONSET_DAYS
        for factor in QP_FACTORS
    ]
    variants += [("reduced_recovery", {"protein_a_recovery": level}) for level in RECOVERIES]
    variants += [("bad_records", changes) for changes in BAD_RECORDS]
    seed, made = FIRST_SEED, []
    for _ in range(batches):
        for kind, changes in variants:
            made.append(_case(kind, seed, **changes))
            seed += 1
    return made


def _spread(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "min": min(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "max": max(values),
    }


def _divergence(case: Case, reference: Case, tolerance: float) -> calc.Result:
    _, observations, _, _ = case
    _, other, _, _ = reference
    return calc.titer_divergence(
        measurements(observations.record, "titer"),
        measurements(other.record, "titer"),
        batch_start=observations.record.phases[0].start,
        reference_start=other.record.phases[0].start,
        tolerance_fraction=tolerance,
    )


def _titer_scores(made: list[Case], references: list[Case]) -> list[dict[str, Any]]:
    rows = []
    for tolerance in TITER_TOLERANCES:
        quiet = {"comparisons": 0, "found": 0}
        changed = {"comparisons": 0, "found": 0}
        factors = {
            factor: {
                "qp_factor": factor,
                "comparisons": 0,
                "found": 0,
                "found_before_onset": 0,
                "delays": [],
            }
            for factor in QP_FACTORS
        }
        for case in made:
            kind, _, truth, _ = case
            if kind == "bad_records":
                continue
            for reference in references:
                found = _divergence(case, reference, tolerance).value
                if kind != "reduced_productivity":
                    quiet["comparisons"] += 1
                    quiet["found"] += found is not None
                    continue
                item = factors[truth.qp_shift_factor]
                changed["comparisons"] += 1
                item["comparisons"] += 1
                if found is not None:
                    changed["found"] += 1
                    item["found"] += 1
                    item["found_before_onset"] += found < truth.qp_shift_day
                    item["delays"].append(found - truth.qp_shift_day)
        for item in factors.values():
            item["delay_days"] = _spread(item.pop("delays"))
        rows.append(
            {
                "tolerance_percent": 100 * tolerance,
                "without_culture_change": quiet,
                "with_culture_change": changed,
                "by_qp_factor": list(factors.values()),
            }
        )
    return rows


def _recovery_scores(made: list[Case], references: list[Case]) -> list[dict[str, Any]]:
    rows = []
    for tolerance in RECOVERY_TOLERANCES:
        no_loss = {"comparisons": 0, "found": 0}
        yield_alarms = {"comparisons": 0, "found": 0}
        levels = {level: {"recovery": level, "comparisons": 0, "found": 0} for level in RECOVERIES}
        for kind, _, truth, results in made:
            if kind == "bad_records":
                continue
            for _, _, _, other in references:

                def short(metric: str) -> bool:
                    found = calc.recovery_shortfall(
                        results[metric], other[metric], tolerance_points=tolerance
                    )
                    return found.value is not None

                yield_alarms["comparisons"] += 1
                yield_alarms["found"] += short("harvest_to_load_yield")
                if kind == "reduced_recovery":
                    item = levels[round(truth_level(truth), 2)]
                else:
                    item = no_loss
                item["comparisons"] += 1
                item["found"] += short("protein_a_recovery")
        rows.append(
            {
                "tolerance_points": tolerance,
                "protein_a_without_loss": no_loss,
                "protein_a_by_true_recovery": list(levels.values()),
                "yield_false_alarms": yield_alarms,
            }
        )
    return rows


def truth_level(truth: GroundTruth) -> float:
    """The scenario's recovery level: the true recovery carries 0.5 % of batch-to-batch
    variation, so it is matched to the nearest level the benchmark set."""

    return min(RECOVERIES, key=lambda level: abs(level - truth.protein_a_recovery))


def _bad_record_scores(made: list[Case], references: list[Case]) -> dict[str, Any]:
    bad = [case for case in made if case[0] == "bad_records"]
    mis_keyed = [case for case in bad if case[2].mis_keyed_sample is not None]
    gap = [case for case in bad if case[2].online_gap_days is not None]

    def answered(group: list[Case], *metrics: str) -> int:
        return sum(case[3][metric].value is not None for case in group for metric in metrics)

    return {
        "batches": len(bad),
        "mis_keyed_sample": {
            "batches": len(mis_keyed),
            "culture_metrics_answered": answered(mis_keyed, "ivcd", "qp"),
            "titer_findings_answered": sum(
                _divergence(case, reference, calc.DIVERGENCE_TOLERANCE_FRACTION).status
                == calc.USABLE
                for case in mis_keyed
                for reference in references
            ),
        },
        "historian_gap": {
            "batches": len(gap),
            "harvest_mass_answered": answered(gap, "harvest_mass"),
            "yield_findings_answered": sum(
                calc.recovery_shortfall(
                    case[3]["harvest_to_load_yield"], reference[3]["harvest_to_load_yield"]
                ).status
                != calc.INSUFFICIENT
                for case in gap
                for reference in references
            ),
        },
        "protein_a_recovery_answered": answered(bad, "protein_a_recovery"),
    }


def _errors(made: list[Case]) -> dict[str, Any]:
    """How far each computed metric is from the generator's true value, in percent of it, over
    the batches whose records are good."""

    truths = {
        "ivcd": lambda t: t.ivcd,
        "qp": lambda t: t.qp_culture_average,
        "harvest_mass": lambda t: t.harvest_mass,
        "harvest_to_load_yield": lambda t: 100 * t.harvest_to_load_yield,
        "protein_a_recovery": lambda t: 100 * t.protein_a_recovery,
    }
    found: dict[str, Any] = {}
    for metric, true_value in truths.items():
        errors = [
            100 * abs(results[metric].value - true_value(truth)) / true_value(truth)
            for kind, _, truth, results in made
            if kind != "bad_records"
        ]
        found[metric] = {
            "batches": len(errors),
            "mean_abs": statistics.fmean(errors),
            "max_abs": max(errors),
        }
    return found


def run(batches: int = DEFAULT_BATCHES, references: int = DEFAULT_REFERENCES) -> dict[str, Any]:
    """The whole benchmark as plain data (docs/verification-report.md is ``render`` of it)."""

    made = cases(batches)
    reference_cases = [_case("normal", FIRST_REFERENCE_SEED + index) for index in range(references)]
    kinds = [case[0] for case in made]
    return {
        "generator": VERSION,
        "settings": {
            "batches_per_variant": batches,
            "titer_tolerance_default_percent": 100 * calc.DIVERGENCE_TOLERANCE_FRACTION,
            "recovery_tolerance_default_points": calc.RECOVERY_TOLERANCE_POINTS,
            "pairing_window_hours": calc.PAIRING_WINDOW_HOURS,
            "onset_days": list(ONSET_DAYS),
            "qp_factors": list(QP_FACTORS),
            "recoveries": list(RECOVERIES),
        },
        "counts": {
            "references": references,
            "normal": kinds.count("normal"),
            "reduced_productivity": kinds.count("reduced_productivity"),
            "reduced_recovery": kinds.count("reduced_recovery"),
            "bad_records": kinds.count("bad_records"),
            "comparisons": len(made) * references,
        },
        "bad_records": _bad_record_scores(made, reference_cases),
        "titer_divergence": _titer_scores(made, reference_cases),
        "recovery_shortfall": _recovery_scores(made, reference_cases),
        "calculation_error_percent": _errors(made),
    }
