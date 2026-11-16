# STATUS: BatchLens (BatchlensCraft)

Where the app stands, for people and agents picking up work here. Updated 2026-11-15.

- **Branch:** `first-slice`, for the owner to merge into `main`.
- **Done:** Phases 0 to 3 of `docs/agent/kickoff.md` (bootstrap, calculations and generator,
  object and read API, the two pages), and Phase 4 once, best effort: the app runs inside a
  live PlantCraft `v0.6.0`, where it reports the missing bioreactor as designed. `make ci` and
  `make e2e` are green; the counts are in the first entries of `docs/devlog.md`.
- **Next task, precisely:** load the synthetic plant into a live PlantCraft (ROADMAP item 1).
  Start by reading PlantCraft's `docs/installation-file.md` and the configuration-file import
  with a CSV source; write the bioreactor asset type (roles `ph`, `do`, `temperature`,
  `volume`), the four assets of `docs/demo.md` and the four series as an import PlantCraft
  accepts, without editing PlantCraft and without writing the signals as the app's own derived
  series. Acceptance: under `make dev`, batch BL-0001 shows a usable harvest mass and four
  online trends.
- **Blockers:** none. Known gaps: `docs/gaps.md`.
- **Careful:** `var/` at the root is the app's default data folder and also holds the owner's
  private file. Never write there; set `BATCHLENS_DATA_DIR`.

Keep the history in `docs/devlog.md`.
