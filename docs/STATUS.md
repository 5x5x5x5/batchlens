# STATUS: BatchLens (BatchlensCraft)

Where the app stands, for people and agents picking up work here. Updated 2026-11-15.

- **How work lands:** one branch and pull request per item from `main`; the agent merges it
  itself once GitHub CI passes (owner's instruction of 2026-11-16).
- **Done:** the first slice (calculations, generator, store, read API, two pages); the demo
  inside a live PlantCraft (`tools/run_demo.sh`); three findings per compared batch with
  evidence and a reference overlay; a fifth, badly recorded batch that is flagged, not
  answered; the benchmark and `docs/verification-report.md`; `make lock` and `make image`; the
  documents cleaned up for publication, with a tour and two case studies; an as-of slider on the batch page; editing with audit (a sample's
  collection time, the reference batch); the rest of the purification train with a pool
  genealogy; two read-only tools for PlantCraft's assistant. Counts in
  `docs/devlog.md`.
- **Waiting for the owner:** making the repository public. It exposes the commit author's
  email address in the history, so that step is the owner's.
- **Next tasks, in order:** (1) findings for the later purification steps (a yield more than a
  tolerance below the reference's, as for the capture step), with benchmark variants that
  vary those steps; (2) a fuller genealogy (splits, repeated cycles); (3) an evaluation of the
  assistant with the tools, which needs a language model set up in PlantCraft.
- **Blockers:** none. Known gaps: `docs/gaps.md`.
- **Careful:** `var/` at the root is the app's default data folder and also holds the owner's
  private file. Never write there; set `BATCHLENS_DATA_DIR`.

Keep the history in `docs/devlog.md`.
