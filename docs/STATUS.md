# STATUS: BatchLens (BatchlensCraft)

Where the app stands, for people and agents picking up work here. Updated 2026-11-15.

- **Branches:** `first-slice` (pull request 1, for the owner to merge into `main`), then
  `live-plant` on top of it.
- **Done:** Phases 0 to 4 of `docs/agent/kickoff.md`, and roadmap item 1: with the files of
  `batchlens demo-plant` imported, the demo runs end to end inside a live PlantCraft `v0.6.0`
  (`docs/demo.md`). `make ci` and `make e2e` are green; counts in `docs/devlog.md`.
- **Next task, precisely:** roadmap item 2, evidence-linked findings, starting with the
  smallest one: for a batch and the reference batch, the first sample at which the titer
  trajectory leaves the reference by more than a named, illustrative tolerance, as a `calc`
  function with a hand-calculated oracle, answered by the metrics route as a finding with the
  ids of the samples it rests on. Observation (where it diverged), calculation (what that is
  in grams at harvest) and hypothesis stay in separate fields; no cause is attributed. Present
  the design to the owner before building it: what counts as "left the reference" is a
  scientific choice.
- **Blockers:** none. Known gaps: `docs/gaps.md`.
- **Careful:** `var/` at the root is the app's default data folder and also holds the owner's
  private file. Never write there; set `BATCHLENS_DATA_DIR`.

Keep the history in `docs/devlog.md`.
