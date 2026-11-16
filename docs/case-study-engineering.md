# Engineering case study

What BatchLens had to get right, the decisions that followed, and what they cost. The numbers
quoted are measured; where something is not measured it says so.

## The problem

A process engineer who asks why a batch yielded less antibody than the last ones has to look
in several systems. The historian has the bioreactor's pH, oxygen, temperature and volume. The
laboratory system has cell counts and titers, each reported hours or a day after its sample
was drawn. The execution system knows which batch was on which vessel and when. Pool volumes
and concentrations sit in a batch record. Each system is correct on its own terms, and none
of them knows what a batch is in the sense the question needs.

BatchLens is a small, synthetic demonstration of the layer that is missing: one that knows a
batch as a set of phase executions on shared equipment, joins the continuous and the sampled
data correctly, computes a mass balance along the process, and is strict about what it can
and cannot say.

## Four distinctions the software keeps

These came from manufacturing experience, not from the software side, and most of the design
follows from them.

1. **A batch is not an asset.** The bioreactor is an asset; a batch is a window on it. The same
   four signals carry every batch, so every read of plant data is scoped to a phase
   execution's asset and time window (`api/plant.py`). A test puts two batches on one
   bioreactor and checks neither sees the other's samples or series.
2. **A phase execution is not a recipe.** The app records what happened on an asset between two
   instants. It has no notion of what should have happened.
3. **An assay result is not an online sample.** Online values are read from PlantCraft on
   request and never copied. Assay results are the app's own records, with a method, a unit
   and a validity.
4. **Collection time is not availability time.** Every result has both. Collection time places
   it on the process timeline; availability time decides whether an analysis may use it. Every
   route takes `as_of` and filters on availability, so a past analysis cannot use a result
   that did not exist yet.

## One result shape

Every calculation answers the same structure: value, unit, status, reasons, the ids of its
inputs, and a calculation version. The status is one of four.

| Status | Meaning |
|---|---|
| `usable` | Computed from valid inputs |
| `suspect` | Computed, but implausible; the value is shown, flagged |
| `insufficient` | Not computed: something required is missing or not yet available |
| `invalid` | Not computed: an input breaks a rule |

The rule behind it: prefer no number to a number that looks precise and is not supported. Units
are exact strings and anything else is `invalid`; nothing is converted, interpolated across a
disallowed gap, extrapolated or clipped; a zero denominator is `insufficient`, never 0 %. The
formulas are in a package that imports only the standard library, so each is tested against
arithmetic written out by hand in the test (`tests/test_calc.py`, `tests/test_divergence.py`).

The cost is a page with many flags. That is the intent: the fifth demo batch has a normal
process and bad records, and the right behaviour is a screen of refusals that each name a
record.

## Who owns what

| Owner | Holds |
|---|---|
| PlantCraft | People, sign-in, roles, assets, signals, time series, audit |
| BatchLens | Batches, phase executions, samples, assay results, pool measurements |
| Nobody | Metrics and findings: computed on request, never stored |

The app is built on PlantCraft's published app template and reaches the platform only through
its API v1 client, as the signed-in person. It stores asset ids, not assets. Computing on
request keeps `as_of` honest and removes a whole class of stale-result bugs; the price is that
the metrics route reads PlantCraft every time, which is fine for five batches and unmeasured
beyond that.

A missing asset or signal is an answer, not an error. A PlantCraft that has never heard of the
bioreactor gets HTTP 200 with the harvest mass `insufficient` and the reason "asset BR-2001
was not found", and the metrics that rest only on the app's own records are still computed.

## Findings without diagnosis

A finding has four parts that stay apart: an observation (a calculation with the ids it rests
on), a consequence (a product mass against the reference's), evidence (other results of the
same samples), and a cause, which is always empty.

- **Titer divergence**: the first sample that is below the reference batch's sample of the
  same culture age by more than a tolerance, and after which every later sample is below too.
  Samples are paired by nearest culture age within a window; nothing is interpolated.
- **Step recovery shortfall**: a yield or recovery more than a tolerance below the reference's.

The app does not say why. One screenshot shows the reason: at the divergence of the
reduced-productivity batch, glucose reads 1.63 g/L below the reference although the generator
makes it 0.8 g/L higher at equal age, because the two samples are hours apart on a daily
feed sawtooth. A tool that concluded "glucose depletion" from that table would be wrong.

## What the real platform taught

The tests run against the SDK's fake PlantCraft. Two things only appeared against a real one
or against a harder test, and both would have been silent wrong answers.

- **A three-hour shift.** PlantCraft reads a CSV source's times in its scenario's time zone
  and ignores the source's own setting. The synthetic bioreactor data landed three hours off
  with no error. The only symptom was a harvest mass of 10,177 g instead of 10,174 g and two
  empty steps at the start of a trend. The plant files are now written for a named zone, and
  the demo guide says how to check.
- **A line through a hole.** The platform's stepped means hold the last value across a gap.
  For the badly recorded batch the trend drew twelve hours of volume that were never
  recorded. The trends are now averaged from recorded values in the app, and an empty step
  breaks the line.

Neither is a defect of this app's formulas. Both are the kind of thing that makes people
distrust analytics, which is why they are written down here and not only fixed.

## Verification

- **Oracle tests** for every formula, with the arithmetic in the test, and a test for each
  failure status.
- **A generator whose ground truth the app cannot see.** The scenario label and fault
  parameters are a separate object; tests check that no stored record and no API response
  contains them.
- **A benchmark** ([verification-report.md](verification-report.md)): 320 seeded batches, each
  against five references. At the default tolerances: no false alarms in 400 comparisons; a
  fall of specific productivity to 55 % found 300 times out of 300, with a median delay of 1.9
  days; a fall to 85 % found 59 times out of 300; no number returned for any badly recorded
  batch. A test fails when the published report is not what the command gives.
- **A live run** inside PlantCraft 0.6.0, where every checked value equals the fake's.
- **An independent review** of the first slice, which found one path to a server error (an
  `as_of` at the edge of representable time) and four smaller issues, listed in
  [gaps.md](gaps.md).

At the time of writing: 172 Python tests, 21 interface tests and 6 browser journeys, all
passing locally; the exact counts of each step are in [devlog.md](devlog.md).

## Tradeoffs and limits

- **One reference batch stands for "comparable batches".** Its assay noise is in every
  comparison. A set of comparable batches with a distribution is the obvious next step.
- **Harvest mass rests on one titer result.** In the demo the true harvest-to-load yield is
  about 93 % in every batch and the computed one ranges from 89 to 97 %. No uncertainty is
  shown beside the number.
- **Tolerances are settings with illustrative defaults**, not limits. The benchmark shows what
  each choice costs; a mild fall in productivity is mostly missed at the default.
- **The examiner and the examined share one generator.** The benchmark's false-alarm rates are
  a floor, not an estimate for real data.
- **Two things can be changed, and only by an editor**: a sample's collection time and the
  reference designation. A correction needs a reason, keeps the value it replaces and is
  written to PlantCraft's audit log. Everything else is read-only.
- **A simple train.** Downstream is one pool in and one pool out per step, with one merge (two
  capture cycles into one eluate). Splits, side streams, repeated cycles of a polishing
  column and material carried between batches are not modelled.
- **Not validated, not GxP**, and the generator is not a mechanistic model.
