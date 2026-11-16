"""Pure calculations: standard library only, no imports from the rest of the app, no I/O.

Every function answers one ``Result`` (``results.py``). The formulas, their units, a worked
example of each and every assumption are in ``docs/scientific-assumptions.md``; change a formula
and its ``calculation_version`` changes with it.
"""

from batchlens.calc.comparison import (
    DIVERGENCE_TOLERANCE_FRACTION,
    PAIRING_WINDOW_HOURS,
    RECOVERY_TOLERANCE_POINTS,
    recovery_shortfall,
    titer_divergence,
)
from batchlens.calc.culture import MAX_GAP_DAYS, ivcd, specific_productivity
from batchlens.calc.mass import (
    HARVEST_TITER_WINDOW_HOURS,
    RECOVERY_SUSPECT_ABOVE_PERCENT,
    VOLUME_MAX_AGE_SECONDS,
    harvest_mass,
    pool_mass,
    ratio_percent,
)
from batchlens.calc.results import (
    INSUFFICIENT,
    INVALID,
    SUSPECT,
    USABLE,
    Measurement,
    Online,
    Pool,
    Reason,
    Result,
    insufficient,
)

__all__ = [
    "DIVERGENCE_TOLERANCE_FRACTION",
    "PAIRING_WINDOW_HOURS",
    "RECOVERY_TOLERANCE_POINTS",
    "recovery_shortfall",
    "titer_divergence",
    "HARVEST_TITER_WINDOW_HOURS",
    "INSUFFICIENT",
    "INVALID",
    "MAX_GAP_DAYS",
    "RECOVERY_SUSPECT_ABOVE_PERCENT",
    "SUSPECT",
    "USABLE",
    "VOLUME_MAX_AGE_SECONDS",
    "Measurement",
    "Online",
    "Pool",
    "Reason",
    "Result",
    "harvest_mass",
    "insufficient",
    "ivcd",
    "pool_mass",
    "ratio_percent",
    "specific_productivity",
]
