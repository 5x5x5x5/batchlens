# ROADMAP: BatchLens

Done is what the tests and `docs/devlog.md` show. Everything under "Next" is a proposal.

## Done (first slice, 2026-11-15)

| Item | State |
|---|---|
| Pure calculations with one result shape, statuses and reasons | Done, oracle-tested |
| Seeded generator: four batches on one bioreactor, ground truth kept apart | Done, tested |
| Batches in the app's store, `batchlens seed-demo` | Done, tested |
| Read API with `as_of` (no look-ahead) | Done, tested against the fake PlantCraft |
| Batch list and batch detail pages, English and Brazilian Portuguese | Done, Vitest and browser journeys |
| The synthetic plant as files a live PlantCraft imports (`batchlens demo-plant`) | Done, verified on PlantCraft 0.6.0 under `make dev` |
| First evidence-linked finding: where the titer left the reference, and the harvest mass difference | Done, oracle-tested, on the batch page |

## Next, in the intended order (proposed)

1. More evidence-linked findings: a step recovery below the reference (the Protein A loss of
   the demo is visible in the metrics but raises no finding yet), and the supporting evidence
   around a divergence (cell growth, glucose, lactate at the same samples), still without
   attributing a cause.
2. A benchmark over many seeded normal and faulty batches, including missing windows and
   misaligned sample times (the fourth scenario of the original proposal: a data problem
   the analysis must flag rather than answer), publishing false positives, misses and incomplete-data behaviour.
3. An as-of control in the interface, then editing (samples, reference designation) with audit.
4. Batch genealogy and cumulative recovery across the rest of downstream (polishing, viral
   filtration, UF/DF), where pools split and merge.
5. Possibly later: cross-batch process monitoring, and read-only assistant tools over the
   verified calculations.

Out of scope until decided otherwise: real PI, LIMS, MES or QMS links; drug product; anything
that claims GMP, validation or mechanistic model validity.
