# BatchLens

**Synthetic demo · non-GxP · not for process control, release or batch disposition.**

BatchLens follows antibody batches from the production culture to the Protein A capture step
and shows, for each batch, how much product there was at each point and where each number
comes from. Every batch here is synthetic: made by a generator, not measured in any plant.

## Batches

**Batches** lists every batch with its product, its bioreactor, its start and end, and a mark
on the reference batch, the one the others are compared with. Open a batch from its id.

## One batch

- **Phase executions**: what happened on which asset, and when. A batch is a window on shared
  equipment: the same bioreactor carries one batch after another.
- **Findings** (not on the reference batch): where this batch's titer left the reference
  batch's, if it did. An observation (the first sample that was below the reference by more
  than the tolerance and after which every later sample stayed below), a calculation (the
  product mass at harvest against the reference's), and no cause: the app does not diagnose.
  The same for each step: a yield or recovery more than the tolerance below the reference's.
  Under a divergence, the other results of the same samples are listed beside the
  reference's, for you to read; the app concludes nothing from them.
- **Metrics**: each with its value and unit, its status, the reasons for it and the ids of its
  inputs, beside the reference batch's value and the difference.
- **Pool measurements**: the volume and concentration behind each pool mass.
- **Trends**: the bioreactor's online signals over the production phase, read from PlantCraft,
  and the offline viable cell density and titer at their collection times.
- **Assay results**: every result with two times, when its sample was collected and when the
  result became available. They are never the same thing.

## Reading a status

| Status | Meaning |
|---|---|
| Usable | Computed from valid inputs |
| Suspect | Computed, but an input or the result is implausible. The value is shown, flagged |
| Insufficient | Not computed: something required is missing or not yet available |
| Invalid | Not computed: an input breaks a rule (a wrong unit, a negative value) |

A metric with no value always says why. When PlantCraft has no such asset or signal, the app
says which one it did not find instead of drawing a trend it does not have.

## Good to know

- Masses are estimates from a concentration times a volume; the assay method is named.
- Units are never converted. A value in another unit is invalid.
- Times are shown in the installation's time zone, named on every page.
- The formulas, their assumptions and the settings behind them are in the project's
  `docs/scientific-assumptions.md`.
