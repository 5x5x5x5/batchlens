# ROADMAP: BatchLens

Done is what the tests and `docs/devlog.md` show. Everything under "Next" is a proposal.

## Done (first slice, 2026-11-15)

| Item | State |
|---|---|
| Pure calculations with one result shape, statuses and reasons | Done, oracle-tested |
| Seeded generator: five batches on one bioreactor (one of them badly recorded), ground truth kept apart | Done, tested |
| Batches in the app's store, `batchlens seed-demo` | Done, tested |
| Read API with `as_of` (no look-ahead) | Done, tested against the fake PlantCraft |
| Batch list and batch detail pages, English and Brazilian Portuguese | Done, Vitest and browser journeys |
| The synthetic plant as files a live PlantCraft imports (`batchlens demo-plant`) | Done, verified on PlantCraft 0.6.0 under `make dev` |
| First evidence-linked finding: where the titer left the reference, and the harvest mass difference | Done, oracle-tested, on the batch page |
| Findings for both step recoveries, evidence beside a divergence, reference overlay on VCD and titer | Done, tested, on the batch page |
| A fifth, badly recorded demo batch that is flagged rather than answered | Done, tested |
| Benchmark over 320 seeded batches and the verification report | Done; a test keeps the report current |
| One-command demo, image and lock built, documents for publication | Done |
| An as-of slider on the batch page | Done, Vitest and a browser journey |
| Editing with audit: a sample's collection time, the reference batch | Done, tested, a browser journey |
| The rest of downstream: step yields to drug substance, pool genealogy with a merge balance | Done, oracle-tested, on the batch page |

## Next, in the intended order (proposed)

1. A fuller genealogy: splits, repeated cycles and material carried between batches, with a
   mass balance at each; findings for the later purification steps.
2. Possibly later: cross-batch process monitoring, and read-only assistant tools over the
   verified calculations.

Out of scope until decided otherwise: real PI, LIMS, MES or QMS links; drug product; anything
that claims GMP, validation or mechanistic model validity.
