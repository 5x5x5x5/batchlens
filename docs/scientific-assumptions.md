# Scientific assumptions

**All values in BatchLens are illustrative.** The data is synthetic, the model that makes it is
a shape generator and not a mechanistic or validated model, and no number, tag, name or limit
comes from a real facility. Nothing here is an acceptance limit, a critical-parameter
classification or a claim of GMP, validation or model validity.

The formulas live in `src/batchlens/calc/` (standard library only). Each answers one result:
`metric`, `value` (or none), `unit`, `status`, `reasons`, `inputs` (the ids of the results,
measurements and signals used) and `calculation_version`.

| Status | Meaning |
|---|---|
| `usable` | Computed from valid inputs |
| `suspect` | Computed, but an input or the result is implausible; the value is shown, flagged |
| `insufficient` | Not computed: something required is missing or not yet available |
| `invalid` | Not computed: an input breaks a rule |

A `usable` result may carry reasons too. They then say what it rests on: a result left out
because it was not yet available, or a mass estimated from concentration times volume.

## Rules every calculation follows

- **Units are exact strings**: `1e6 cells/mL`, `g/L`, `L`, `g`. Any other unit is `invalid`;
  nothing is converted.
- **Times** are sample collection times as UTC instants; elapsed days are seconds / 86400.
- **No look-ahead (`as_of`)**. An assay result or pool measurement is used only when its
  `result_available_at <= as_of`; online series are read only up to `as_of`. Collection time
  places a value on the process timeline, availability time decides whether it may be used, and
  the two are never merged. Without `as_of`, everything recorded is used. The two ratios take
  results that were already computed under `as_of`, so they need no `as_of` of their own.
- **Nothing is repaired**: no clipping, no interpolation across a disallowed gap, no
  extrapolation, no substituted denominator. A negative or non-finite input is `invalid`.
- **Results marked invalid** (`validity` other than `valid`) are left out before any calculation.
- **Scope**: samples are those of the batch's production-culture phase; plant signals are read
  on that phase's asset, inside that phase's time window.

## Settings (illustrative defaults)

| Setting | Default | Where | Meaning |
|---|---|---|---|
| `MAX_GAP_DAYS` | 3 days | `calc/culture.py` | Longest span between two cell counts the trapezoid bridges |
| `HARVEST_TITER_WINDOW_HOURS` | 12 h | `calc/mass.py` | The last culture titer must be collected this close to the end of the phase |
| `VOLUME_MAX_AGE_SECONDS` | 900 s | `calc/mass.py` | The online volume used is the last value at or before the sample, no older than this |
| `RECOVERY_SUSPECT_ABOVE_PERCENT` | 105 % | `calc/mass.py` | A yield or recovery above this is shown, flagged `suspect` |

## The calculations

The worked examples are the oracles of `tests/test_calc.py`.

### 1. IVCD (`ivcd/1`), `1e6 cell-days/mL`

`IVCD = sum(0.5 * (X[i] + X[i+1]) * (t[i+1] - t[i]))` over consecutive viable cell density
samples `X` in `1e6 cells/mL`, `t` in days.

Example, samples at days 0, 1.25, 3.0 and 3.5 with 0.5, 1.5, 4.0 and 5.0:
`0.5*(0.5+1.5)*1.25 + 0.5*(1.5+4.0)*1.75 + 0.5*(4.0+5.0)*0.5 = 1.25 + 4.8125 + 2.25 = 8.3125`.

- `insufficient`: fewer than two samples; a gap longer than `MAX_GAP_DAYS`.
- `invalid`: a negative or non-finite count; duplicate or non-increasing times; a wrong unit.
- Assumption: a straight line between samples. With daily samples in exponential growth the
  trapezoid overestimates slightly.

### 2. Specific productivity qP (`qp/1`), `pg/cell/day`

`qP = 1000 * (titer_last - titer_first) / IVCD`, titer in `g/L`, over the window from the first
to the last sample that has both a cell count and a titer (available at `as_of`).

Unit check: 1 pg/cell/day x 1e6 cell-days/mL = 1e6 pg/mL = 1 mg/L, hence the factor 1000.

Example, same samples with titers 0.0 and 0.16625 g/L at days 0 and 3.5:
`1000 * 0.16625 / 8.3125 = 20.0`.

- It is a **culture average**, one number for the whole window.
- Assumption: a **concentration-basis estimate that ignores the volume change of a fed
  batch**. Feeds dilute the titer, so true cell-specific productivity is somewhat higher.
- `insufficient`: fewer than two samples with both results; IVCD `insufficient`; IVCD zero.
- `invalid`: a wrong titer unit, a negative or non-finite titer; IVCD `invalid`.
- `suspect`: a negative value (the titer fell).

### 3. Product mass at harvest (`harvest_mass/1`), `g`

`mass = titer_last * V(t_sample)`: the last titer sample collected in the production phase,
times the bioreactor volume read from the online signal at that sample's collection time (the
last value at or before it, at most `VOLUME_MAX_AGE_SECONDS` old; never a later value, never
interpolated).

Example: 5.0 g/L and 1990 L (read 10 minutes before the sample) give 9950 g.

- Assumption: **titer is per litre of supernatant and the volume is whole broth, so no
  packed-cell-volume correction is applied**. This overstates the mass by roughly the cell
  volume fraction.
- Assumption: the harvest mass rests on **one** titer result, so its assay error passes
  straight into the mass and into the harvest-to-load yield.
- `insufficient`: `as_of` before the phase ended; no titer sample in the phase; the last one
  collected more than `HARVEST_TITER_WINDOW_HOURS` before the end; its result not yet available;
  no volume value near the sample; the bioreactor asset or its volume signal not found in
  PlantCraft, or the series unreadable.
- `invalid`: a wrong unit, a negative or non-finite titer or volume.

### 4. Pool masses (`pool_mass/1`), `g`

`mass = volume_L * concentration_g_per_L` for the Protein A load and the Protein A eluate, each
from one pool measurement. Always labelled as estimated from concentration times volume, with
the assay method named.

Example: 1900 L x 4.8 g/L = 9120 g (load); 450 L x 18.5 g/L = 8325 g (eluate).

- `insufficient`: no measurement; not yet available. `invalid`: wrong unit, negative, non-finite.
- Assumption: the load concentration is the antibody concentration. A plain A280 reading of a
  clarified harvest also sees host proteins; here the value is synthetic and stands for a
  product-specific result.

### 5. Harvest-to-load yield (`ratio_percent/1`), `%`

`100 * load mass / harvest mass`. It covers clarification, hold and transfer together and is
never assumed to be 100. Example: `100 * 9120 / 9950 = 91.66`.

### 6. Protein A recovery (`ratio_percent/1`), `%`

`100 * eluate mass / load mass`. Example: `100 * 8325 / 9120 = 91.28`.

For both ratios:

- `insufficient`: either mass has no value; the denominator is zero. Never 0 %.
- `suspect`: the value is above `RECOVERY_SUSPECT_ABOVE_PERCENT` (value unchanged), or an input
  is `suspect`. Example: `100 * 9700 / 9120 = 106.36` is shown, flagged.
- Assumption for review: the bound is applied to the harvest-to-load yield as well as to the
  recovery.

## The generator's model

`src/batchlens/demo/generator.py`, a deterministic function of (scenario parameters, seed) on
`random.Random(seed)`. Its ground truth (scenario label, parameters, true values) is a separate
object used by tests and described in [demo.md](demo.md); the app never stores, returns or reads
it.

Process: a 2,000 L CHO fed-batch production culture of 14.25 days on one bioreactor, a 6 h
harvest, a 4 h hold and one aggregated 10 h Protein A capture step.

| Part | Model | Parameters |
|---|---|---|
| Viable cell density | Logistic growth from 0.5 to a peak, times `exp(-0.03 * (day - 9))` after day 9 | Peak 20 (x 1 ± 3 %), rate 0.75 /day (x 1 ± 2 %), in `1e6 cells/mL` |
| Titer | Running sum of `qP * dIVCD / 1000`, IVCD by trapezoid over the noise-free density at the sample times | qP 30 pg/cell/day (x 1 ± 2 %) |
| Viability | `98 - 0.05 * day²` % | |
| Glucose | `6.0 - 0.18 * X * (day mod 1)` g/L, a daily sawtooth | +0.8 g/L after a productivity shift |
| Lactate | `0.3 + 1.7 * exp(-((day - 4) / 2)²)` g/L | +0.25 g/L per day after a productivity shift |
| Volume | 1400 L, plus ten daily 60 L feeds from day 3 (2000 L from day 12) | Online noise 0.5 L |
| pH, dissolved oxygen | `7.0 + 0.03 * sin(2π day)`; 40 % air saturation | Noise 0.01; 1.5 |
| Temperature | 36.5 °C, one planned shift to 33.0 °C at day 6 over 2 h | Noise 0.05 |
| Samples | One an hour after inoculation, then daily within ± 3 h | 15 per batch |
| Assay noise (1 SD, relative) | VCD 3 %, viability 0.5 %, glucose and lactate 3 %, titer 2 %, pool concentration 1 % | |
| Result availability | Cell counts and metabolites 0.5 to 3 h after collection; titer 18 to 30 h; pools 2 to 4 h after measurement | |
| Harvest-to-load yield | 0.93 (x 1 ± 0.5 %) of the true harvest mass | Load volume 1920 ± 10 L |
| Protein A recovery | 0.92 (x 1 ± 0.5 %) of the load mass | Eluate at about 18 g/L |
| Online signals | One value every 10 minutes during the production phase | |

Because titer is generated from qP and the running IVCD, `tests/test_generator.py` checks that
the calculations recover the generator's own parameters within three standard deviations of the
assay noise. The scenarios are in [demo.md](demo.md).
