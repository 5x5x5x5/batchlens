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
One calculation, the titer divergence, is `usable` with no value when its answer is "none
found"; its reason then says so (`no_divergence`).

## Rules every calculation follows

- **Units are exact strings**: `1e6 cells/mL`, `g/L`, `L`, `g`. Any other unit is `invalid`;
  nothing is converted.
- **Times** are sample collection times as UTC instants; elapsed days are seconds / 86400.
- **No look-ahead (`as_of`)**. An assay result or pool measurement is used only when its
  `result_available_at <= as_of`; online series are read only up to `as_of`. Collection time
  places a value on the process timeline, availability time decides whether it may be used, and
  the two are never merged. A sample collected after `as_of`, a pool measured after it and a
  phase that had not begun do not exist in that view at all; a phase that had not ended has
  no end. Without `as_of`, everything recorded is used. The two ratios take
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
| `INOCULATION_WINDOW_HOURS` | 6 h | `calc/culture.py` | A first cell count collected later than this after the phase began does not stand for the density it began at |
| `HARVEST_TITER_WINDOW_HOURS` | 12 h | `calc/mass.py` | The last culture titer must be collected this close to the end of the phase |
| `VOLUME_MAX_AGE_SECONDS` | 900 s | `calc/mass.py` | The online volume used is the last value at or before the sample, no older than this |
| `RECOVERY_SUSPECT_ABOVE_PERCENT` | 105 % | `calc/mass.py` | A yield or recovery above this is shown, flagged `suspect` |
| `DIVERGENCE_TOLERANCE_FRACTION` | 0.15 | `calc/comparison.py` | A titer below the reference's by more than this fraction of the reference's counts as below |
| `PAIRING_WINDOW_HOURS` | 6 h | `calc/comparison.py` | A sample is compared with the reference sample nearest in culture age, at most this far away |
| `MERGE_TOLERANCE_PERCENT` | 3 % | `calc/mass.py` | A merged pool's mass may differ from the sum of its parts by this much before it is `suspect` |
| `INOCULATION_TOLERANCE_FRACTION` | 0.20 | `calc/comparison.py` | An inoculation density below the reference's by more than this fraction of the reference's is a shortfall |
| `TRANSFER_TOLERANCE_PERCENT` | 5 % | `calc/mass.py` | The volume a vessel's signal shows arriving may differ from the recorded volume of a transfer by this much before it is `suspect` |
| `MINIMUM_COMPARABLE` | 3 | `calc/comparison.py` | With fewer comparable batches than this that have a value, a metric is not placed among them |
| `RECOVERY_TOLERANCE_POINTS` | 5 points | `calc/comparison.py` | A step's yield or recovery lower than the reference's by more than this many percentage points is a shortfall |
| `TOLERANCE_POINTS_BY_METRIC` | harvest-to-load yield: 10 points | `calc/comparison.py` | A step whose tolerance is its own. The harvest-to-load yield rests on one culture titer and moves by several points with nothing wrong |

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

### 7. Titer divergence from the reference batch (`titer_divergence/1`), `days`

An observation about one batch against the reference batch, not a diagnosis.

1. Culture age of a sample = its collection time minus the start of its batch's production
   phase.
2. Each titer sample of the batch, in collection order, is paired with the reference batch's
   titer sample nearest in culture age, if one lies within `PAIRING_WINDOW_HOURS`. A sample
   without such a pair is left out and named. Nothing is interpolated between reference samples.
3. A pair is *below* when `reference - titer > tolerance * reference`.
4. The divergence is the first pair of the unbroken run of below pairs that reaches the last
   pair. Its value is that sample's culture age in days. A batch whose last pair is not below
   has not diverged, whatever happened earlier (`no_divergence`, no value).

Example (`tests/test_divergence.py`), reference 1.0, 2.0, 3.0, 4.0, 5.0 g/L at days 1 to 5, batch
0.98, 1.6, 2.9, 3.2, 4.0 g/L at days 1.1, 2.0, 3.1, 4.0, 5.1, tolerance 15 %: deficits 2 %, 20 %,
3.3 %, 20 %, 20 %. Day 2.0 is below but day 3.1 recovers, so the divergence is day 4.0.

- `insufficient`: fewer than two pairs. `invalid`: a wrong unit, a negative or non-finite titer,
  duplicate or out-of-order times, in either batch.
- `as_of` applies to both batches' results.
- Only a titer *below* the reference is looked for; a batch above it has not diverged.
- Assumption: **the first sample at which the gap is seen comes after whatever began it.** In
  the demo the productivity change starts at day 7 and is seen at day 7.9, the next sample.
- Assumption: the answer depends on the tolerance. For the demo's reduced-productivity batch a
  tolerance of 5, 10 or 15 % gives day 7.9 and 20 % gives day 11.9. Measured over 1,600
  comparisons ([verification-report.md](verification-report.md)): at the default 15 % there
  were no false alarms, 99 % of falls of qP to 55 % were found, 85 % of falls to 70 % and 17 %
  of falls to 85 %; at 5 % one normal comparison in seven raised a false alarm. In 3 of the
  604 detections at 15 % the sample named lies up to 0.1 day before the day the change truly
  began: assay noise at the sample just before it.
- Assumption: culture ages up to 6 h apart are compared as equal. Early in a culture, when
  titer is small and rising fast, that alone can exceed the tolerance for a sample or two; the
  requirement that every later sample stays below is what keeps such samples from counting.
- Assumption: one reference batch stands for "comparable batches". Its own assay noise and its
  own peculiarities are in every comparison.
- The comparison is plain floating-point arithmetic, with no margin added at the boundary.

### 8. Step recovery shortfall against the reference batch (`recovery_shortfall/2`), `percentage points`

For the harvest-to-load yield and for the Protein A recovery: `reference - value`, when that is
more than the step's tolerance; no value (`within_reference`) otherwise, also when the batch
is above the reference. The tolerance is `RECOVERY_TOLERANCE_POINTS` (5 points) for a step
measured pool to pool and 10 points for the harvest-to-load yield (version 2; version 1 used
10 points for every step).

Example: recovery 73.4 % against 93.6 % is 20.2 points below, a shortfall. A harvest-to-load
yield of 89.4 % against 97.0 % is 7.6 points below: within its 10 points. The same 7.6 points
on a UF/DF yield would be a shortfall.

- `insufficient`: either value is missing. `suspect`: a shortfall is found and either value is
  `suspect`. Without a shortfall there is no value to flag, so the result is `usable` and a
  reason says an input was suspect.
- Measured ([verification-report.md](verification-report.md)), which is where the two
  tolerances come from. Protein A at 5 points: no false alarm in 1,300 comparisons; a true
  recovery of 74 % or 80 % always found, 86 % in 78 % of comparisons (at 10 points: 100 %,
  91 %, never). A later step at 5 points: false alarms in 0.4 % of step comparisons, four of
  them naming a step other than the one that lost; a step at 92 % of its nominal yield found
  in 91 % of comparisons (at 10 points: 12 %). The harvest-to-load yield at 5 points raises a
  false alarm in 2.9 % of comparisons and at 10 points in none, so it keeps 10.
- The same calculation is applied to each step after capture (viral inactivation, cation and
  anion exchange, viral filtration, UF/DF), with the mass out of that step against the
  reference's as the consequence.
- Assumption: one tolerance for both steps. In the demo the computed yield already spreads
  from 89 to 97 % across batches whose true yield is about 93 %, because harvest mass rests
  on a single titer result; a tolerance much under 10 points would flag normal batches on yield.
- Assumption: points below one reference batch, not below a distribution of comparable batches.

### 9. The purification train (`ratio_percent/1`, `pool_mass/1`)

For each step after harvest (Protein A capture, viral inactivation, cation exchange, anion
exchange, viral filtration, UF/DF), from the pool that goes in and the pool that comes out:

- **Step yield** = `100 * mass out / mass in`.
- **Left of the harvest** = `100 * mass out / product mass at harvest`.
- **Harvest to drug substance** = `100 * drug substance mass / product mass at harvest`.

Each mass is a pool measurement's volume times concentration (calculation 4). Because a step's
mass in is the previous step's mass out, the step yields multiply to the recovery across the
steps; the product is not computed separately, so there is one number, not two that could
disagree. A step whose pool has no measurement has no yield, and every later "left of the
harvest" that needs it is `insufficient`. Without a harvest mass the step yields are still
answered and the recoveries from harvest are not.

- Assumption: one pool in and one pool out per step, measured once. Sampling losses, holds
  and side streams are inside the step's yield, not separated from it.
- Assumption: the same UV method reads every pool, with no correction for the changing
  impurity content along the train.

### 10. Merge balance (`merge_balance/1`), `%`

Where several pools were merged into one (here the eluates of two Protein A cycles):
`100 * (merged mass - sum of the parts) / sum of the parts`.

Example: parts of 4,600 g and 4,500 g, merged pool 9,150 g: `100 * 50 / 9100 = +0.55 %`.

- `suspect` beyond `MERGE_TOLERANCE_PERCENT` in either direction: mass does not appear, and
  what disappears should be accounted for. `insufficient` when a part or the whole has no
  value; a partial sum is never used.
- The genealogy is the list of links between pool measurements ("material of this pool went
  into that one"). Several links into one pool are a merge. Splits can be recorded the same
  way but the demo has none, and no balance is computed for a split.

### 11. Growth rate of a seed passage (`growth_rate/1`), `1/day`

`mu = ln(X_last / X_first) / (t_last - t_first)`, from the first and the last viable cell
count of one passage (`seed_n2_growth_rate`, `seed_n1_growth_rate`), `X` in `1e6 cells/mL`,
`t` in days. Only that passage's own samples are used.

Example, counts of 0.5 at day 0 and 3.5 at day 3: `ln(3.5 / 0.5) / 3 = 1.9459 / 3 = 0.6486`.

- It is the **average** rate of the passage; counts between the first and the last are not
  used, and a lag or a slowing near the end is not seen.
- `insufficient`: fewer than two counts (a batch with no record of the passage has none); a
  count of zero.
- `invalid`: a negative or non-finite count; a wrong unit; a last count not later than the
  first.

### 12. Inoculation density (`inoculation_density/1`), `1e6 cells/mL`

The first viable cell count of the production culture, when it was collected within
`INOCULATION_WINDOW_HOURS` of the start of the phase. It is a measured count, not the density
computed from what was transferred: transfers are not recorded yet.

- `insufficient`: no count; a first count collected later than the window (the culture has
  grown since, and no earlier density is guessed).
- `invalid`: a negative or non-finite count; a wrong unit.
- It rests on one count, so it carries that count's full assay error.

### 13. Inoculation shortfall against the reference batch (`inoculation_shortfall/1`), `%`

`deficit = 100 * (X_reference - X) / X_reference`, both the inoculation density of section 12.
A deficit above `INOCULATION_TOLERANCE_FRACTION` is a shortfall and is the value; otherwise
there is no value (`inoculation_within_reference`), also when the batch began above the
reference.

Example: 0.2 against 0.5 is `100 * 0.3 / 0.5 = 60 %`, a shortfall; 0.41 against 0.5 is 18 %,
within the tolerance.

- `insufficient`: either density has no value; the reference's is zero.
- Each density is one cell count with its assay error (3 % in the generator), so two normal
  batches differ by a few percent; the tolerance is set well above that and is illustrative.
- Consequence shown with it: the harvest mass against the reference's. Evidence shown with
  it: each batch's last sample of the N-1 seed passage. Neither is offered as the cause.

### 14. Transfer balance (`transfer_balance/2`), `%`

`balance = 100 * (arrived - recorded) / recorded`. `recorded` is the volume written on the
transfer. `arrived` is the destination vessel's volume signal just after the transfer minus
just before it: the last value at or before its start and the first at or after its end, each
no further away than `VOLUME_MAX_AGE_SECONDS`. `left` is the same on the source vessel, the
other way round, and is checked against the record in the same way (version 2). Where the
destination has no usable values the balance is computed from `left`.

Example: a feed recorded as 60.0 L; the bioreactor read 1400.5 L before and 1461.7 L after,
the feed tank 650.0 L and 589.0 L. `arrived = 61.2`, `left = 61.0`, `balance = 100 * 1.2 / 60
= 2.0 %`. Recorded as 6.0 L with 60 L arriving and leaving, the balance is 900 % and `suspect`.

- `suspect`: either vessel outside `TRANSFER_TOLERANCE_PERCENT` of the record. The record and
  a vessel disagree; the app does not decide which is wrong and changes neither. Two vessels
  that agree with each other and not with the record point at the record, and the app still
  does not say so.
- `insufficient`: no vessel at either end has a volume signal, or a value close enough on
  both sides of the transfer (a vessel that recorded nothing before its culture began, a hole
  in the historian); the transfer had not ended at `as_of`; a recorded volume of zero.
- `invalid`: a unit other than `L` anywhere; a negative or non-finite value.
- Assumption: nothing else entered or left either vessel during the transfer (no sampling, no
  evaporation, no base addition).

### 15. A metric among the comparable batches (`set_position/2`), the metric's unit

For one metric: the comparable batches' count, median, lowest and highest value, this batch's
difference from the median, and the range one more batch like them is expected in. The batch
itself is never in its own set, and every batch is computed as of the same moment.

The expected range is a 99 % prediction interval: `mean +/- t * s * sqrt(1 + 1/n)`, with the
sample standard deviation `s` over the `n` comparable batches and Student's `t` for `n - 1`
degrees of freedom (9.925 for three batches, 5.841 for four, 4.604 for five, 2.576 beyond
thirty-one). The reason says whether the value lies below, within or above it (version 2;
version 1 compared with the lowest and highest only).

Example, recoveries of 93.6, 91.1, 92.4 and 93.0 %: median 92.7, mean 92.525,
`s = sqrt(3.4275 / 3) = 1.069`, `92.525 +/- 5.841 * 1.069 * sqrt(1.25) = 85.5 to 99.5`. A
recovery of 73.4 % is below it; one of 89.0 %, lower than all four, is within it. With only
the first three batches the range is 78.0 to 106.7.

- `insufficient`: the batch's own metric has no value; fewer than `MINIMUM_COMPARABLE`
  comparable batches have one (those without are counted in the reason, never guessed).
- **Why not the lowest and highest.** With five batches a normal sixth falls outside their
  range about one time in three for each metric. The interval widens as the batches get
  fewer, so few batches say little, as they should.
- **What it assumes:** that the comparable batches are alike and their values roughly normal,
  and that this batch would be one of them. Nothing checks that. It is an observation beside
  the metric, not a limit, and no finding is raised from it.
- Which batches are comparable is a person's choice, like the reference.

### 16. Split balance (`split_balance/1`), `%`

One pool divided into several: `100 * (sum(parts) - whole) / whole`, each mass a pool
measurement's volume times concentration. Only links marked as a division (`portion`) are
checked; a step that worked on the material is not a split, however many pools came out of it.

Example: a drug substance of 8,000 g in containers of 2,500, 2,480 and 2,970 g:
`100 * (7,950 - 8,000) / 8,000 = -0.6 %`. With the third container missing from the records:
`100 * (4,980 - 8,000) / 8,000 = -37.8 %`, `suspect`.

- `suspect`: outside `MERGE_TOLERANCE_PERCENT` (the merge's 3 %), either way.
- `insufficient`: a portion on record had not been measured, or its result was not available,
  at `as_of`; the whole has no value or is zero. A partial sum is never used.
- It cannot see a portion that was never recorded: that shows as mass unaccounted for, and
  the app does not say why.

### Evidence beside a step recovery shortfall

For the Protein A step, cation exchange and UF/DF, a shortfall that was found carries the lot
of buffer the step drew, beside the reference batch's lot of the same solution: every result
of each lot's sample (pH, conductivity) with the difference, and each lot's age when its step
began to draw it. It is shown only with a shortfall. Nothing is computed from it, no tolerance
is applied to it, and the cause of the finding stays empty. `docs/verification-report.md`
measures what those differences are when the lot was the cause and when it was not.

Beside each result, the same result of the lots the comparable batches drew for that step,
as in section 15: their median and the range one more lot like them is expected in, with a
mark when this lot's value is outside it. Two good lots differ too; this says by how much.

### Evidence beside a divergence

When a divergence is found, the finding lists every other result of the two samples it names
(the diverging sample and the last compared one) beside the reference sample's result of the
same analyte, with the difference. Nothing is concluded from them, and one caution applies:
the two samples can be up to `PAIRING_WINDOW_HOURS` apart in culture age. For anything that
moves within a day, that alone can exceed the effect. In the demo, glucose follows a daily
feed sawtooth, and at the divergence the batch reads 1.63 g/L *below* the reference although
its generated glucose is 0.8 g/L *higher* at equal age.

A finding puts things side by side and keeps them apart: this **observation**; a
**consequence**, the product mass at harvest against the reference's (calculation 3, with its
own status); and a **cause**, which is always empty. BatchLens attributes nothing.

## Trends

The online trends are the mean of the values **recorded** in each step (about 300 steps over
the production phase), computed by the app from PlantCraft's recorded series. A step in which
nothing was recorded has no value and the line breaks there. PlantCraft's own stepped means
are not used for this: they hold the last value across a gap (in the test fake, for about
twelve hours), which would draw values that were never recorded.

## Display

Rounding happens only in the interface (`frontend/src/format.ts`); the API sends full values.

- A metric is shown at the significant digits its inputs carry: three (cell counts and pool
  concentrations are recorded to three), four for the harvest mass (titer and online volume
  carry four). The reference value uses the same digits.
- A difference is shown no finer than the coarser of the two values beside it.
- A recorded value (an assay result, a pool volume) is shown as recorded, without trailing zeros.
- Times are shown in the installation's time zone, which every page names.

## A batch that is running

The demo's live campaign (`demo_campaign(live_from)`) is the fixed campaign moved in time by
whole days, plus `BL-0007`: qP multiplied by 0.6 from day 7, seed 106, its culture begun nine
days before the day the demo first starts. Moving a batch changes none of its values
(`tests/test_live.py`).

- The live batch is generated whole, like the others, so its later records are dated ahead of
  the clock. Rule: for a batch any of whose records is later than now, every answer is cut at
  now, as if `as_of` were now; asking for a later instant gives no more.
- Its bioreactor values reach PlantCraft in a file written again every minute, holding nothing
  later than now. A value is recorded every 10 minutes.
- Assumption: this imitates a running batch for a demonstration. Real records arrive as they
  are made, late, corrected and out of order; none of that is modelled.

## The control loops

For the suite's loop monitoring the bioreactor has three control loops: temperature, pH and
dissolved oxygen (`generator.loop_series`). BatchLens computes nothing from them.

- Each has a fast value, a setpoint and an output every 30 seconds. The fast value follows the
  recorded 10-minute values of the same signal, with straight lines between and a little noise
  that is zero at the recorded instants. For temperature and pH it passes through every
  recorded value. For dissolved oxygen it keeps 15 % of the recorded value's distance from the
  setpoint, as a controller's filtered measurement would: the recorded signal scatters by
  1.5 % around 40 %, which a loop monitor reads as a loop that does not hold.
- Setpoints: 7.0 pH, 40 % air saturation, and 36.5 °C falling to 33.0 °C at the planned shift.
- The output is a load that moves over the culture (an S-curve between two hand-chosen
  values) plus a gain times the error, plus noise, clipped to 0 to 100 %.
- Assumption: this is the shape of a loop that is working, not a controller model. There are
  no dynamics, no integral action, no valve, no disturbance. A loop monitor's verdict on these
  signals describes the generator's noise, not a process. The three loops are made to look
  healthy (PlantCraft Analytics rates them between 90 and 98 %).
- Only the last 48 hours are written to the loops' file; nothing is made across a hole in the
  recorded values.

## The generator's model

`src/batchlens/demo/generator.py`, a deterministic function of (scenario parameters, seed) on
`random.Random(seed)`. Its ground truth (scenario label, parameters, true values) is a separate
object used by tests and described in [demo.md](demo.md); the app never stores, returns or reads
it.

Process: a 2,000 L CHO fed-batch production culture of 14.25 days on one bioreactor, a 6 h
harvest, a 4 h hold and one aggregated 10 h Protein A capture step. Before it, two seed
passages of three days each: N-2 in a 50 L seed bioreactor, then N-1 in a 250 L one.

| Part | Model | Parameters |
|---|---|---|
| Earlier campaign | Three normal batches, `BK-0007` to `BK-0009` (seeds 97 to 99), three weeks apart before the first batch of this campaign | The same model; marked comparable with `BL-0001` and `BL-0002` |
| Seed passages | Exponential growth from 0.5 for three days at `ln(7) / 3` = 0.649 /day (x 1 ± 2 %); four counts per passage (an hour after seeding, daily within ± 3 h, an hour before the transfer), each with a viability | Its own random stream, so earlier values did not change |
| Density a vessel starts at | The target 0.5, or, when the vessel before it held too few cells for that, all of them diluted into the new volume: `min(0.5, X_end * V_before / V_start)` | 50 L into 250 L into 1400 L |
| Transfers | One record for each seed passage moved on, the inoculation and each of the ten feeds, with the volume recorded: what reaches the target density in the next vessel (or all there is), 60 L per feed, each x 1 ± 0.5 %. Passages and the inoculation take 30 min, a feed 10 min and ends when the bioreactor's volume steps | Its own random stream. A feed may be recorded with a digit dropped (a tenth of its volume); the feed itself is unchanged |
| Solution lots | For each batch one lot of feed medium (pH 7.0 ± 0.02, 1150 ± 8 mOsm/kg) and one lot each of Protein A elution buffer (pH 3.5, 5.0 mS/cm), cation-exchange elution buffer (pH 5.5, 25 mS/cm) and diafiltration buffer (pH 6.0, 3.0 mS/cm), buffers ± 0.02 pH and 2 to 3 % conductivity. Prepared in a mix tank in 2 h, sampled once 15 min before the end, held in its own tank. The medium is made the day before the first feed and serves all ten; a buffer is begun 26 h before its step, which draws 300, 400 or 700 L (x 1 ± 1 %) | Its own random stream. Nominal values are illustrative, not a formulation |
| Viable cell density | Logistic growth from the density the culture started at (0.5 unless N-1 fell short) to a peak, times `exp(-0.03 * (day - 9))` after day 9 | Peak 20 (x 1 ± 3 %), rate 0.75 /day (x 1 ± 2 %), in `1e6 cells/mL` |
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
| Protein A recovery | 0.92 (x 1 ± 0.5 %) of the load mass, less 0.6 per pH unit of the elution buffer lot's true pH above 3.6 (a lot at 3.9 gives 0.74) | Eluate at about 18 g/L, as two cycle pools (48 to 52 % each) merged into one |
| Rest of the train | Viral inactivation 0.98, cation exchange 0.90, anion exchange 0.96, viral filtration 0.98, UF/DF 0.95 (each x 1 ± 0.5 %), two hours apart | Drug substance at 50 g/L; its own random stream, so earlier values did not change |
| Bulk containers | The drug substance less 0.5 % left in the lines, filled into containers of 50 L (the last takes the rest), each measured as filled, twenty minutes apart, with 1 % concentration noise | Its own random stream. The last container may be left out of the records; the fill itself is unchanged |
| Vessel volumes | The two seed reactors and the feed tank each have a volume signal on the same ten-minute grid, over the time the batch used them: a seed reactor from an hour before its passage (waiting with its medium, taking the passage before in half an hour, giving to the next vessel in its last half hour), the feed tank from the day before the first feed, falling by 60 L with each feed | Its own random stream; noise 0.2 % of a seed reactor's volume, 0.3 L on the tank |
| Online signals | One value every 10 minutes during the production phase | |
| Record-keeping problems | A sample's collection time keyed in as the previous sample's; a stretch of culture days in which the historian kept nothing. The culture itself is unchanged | Off except in the data-problem batch |

**A second outcome that depends on an input.** The Protein A recovery depends on the true pH
of the batch's elution buffer lot: nothing up to 3.6, then 0.6 less per pH unit. A shape (a knee
and a slope), not a binding model. `BL-0004` uses it: its lot was made at pH 3.9, measured
3.94. The benchmark also still lowers the recovery directly in some batches, which is a loss
whose cause is in no record.

**An outcome that depends on an input.** The density the production culture starts at depends
on the N-1 passage: with `n1_growth_factor` below about 0.8 the N-1 vessel holds too few cells,
the culture starts below the target, and it makes fewer cell-days and less product at the same
qP. This is the first such dependency in the generator, agreed with the owner so that the seed
records have something to show. It is a shape (a dilution and a minimum), not a model of a seed
train. One demo batch uses it, `BL-0006` (factor 0.4); the others are seeded at the target.

Because titer is generated from qP and the running IVCD, `tests/test_generator.py` checks that
the calculations recover the generator's own parameters within three standard deviations of the
assay noise. The scenarios are in [demo.md](demo.md).
