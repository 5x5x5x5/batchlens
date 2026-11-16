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

## Next, in the intended order (proposed)

1. Load the synthetic plant into a live PlantCraft, so the demo runs end to end there.
2. Evidence-linked findings: where a batch's trajectory left the reference, and what that cost
   in product mass, with observations, calculations and hypotheses kept apart.
3. A benchmark over many seeded normal and faulty batches, including missing windows and
   misaligned sample times, publishing false positives, misses and incomplete-data behaviour.
4. An as-of control in the interface, then editing (samples, reference designation) with audit.
5. Batch genealogy and cumulative recovery across the rest of downstream (polishing, viral
   filtration, UF/DF), where pools split and merge.
6. Possibly later: cross-batch process monitoring, and read-only assistant tools over the
   verified calculations.

Out of scope until decided otherwise: real PI, LIMS, MES or QMS links; drug product; anything
that claims GMP, validation or mechanistic model validity.
