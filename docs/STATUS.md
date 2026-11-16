# STATUS: BatchLens (BatchlensCraft)

Where the app stands, for people and agents picking up work here. Updated 2026-11-15.

- **Branches:** `main` holds the first slice and the live-plant work (pull requests 1 and 2,
  merged). `findings` is pull request 3, for the owner to merge.
- **Done:** Phases 0 to 4 of `docs/agent/kickoff.md`; the demo inside a live PlantCraft; the
  first finding (titer divergence from the reference). Counts in `docs/devlog.md`.
- **Next task, precisely:** a second finding, "step recovery below the reference": Protein A
  recovery (and the harvest-to-load yield) lower than the reference batch's by more than a
  named, illustrative number of percentage points, as an observation with the pool
  measurements it rests on and the eluate mass difference as its consequence. Acceptance:
  `BL-0004` gets the finding, `BL-0002` and `BL-0003` do not, a hand-calculated oracle test,
  and `insufficient` when either recovery has no value. The tolerance needs the owner's view:
  the yield's own spread in the demo (89 to 97 %) is already 8 points.
- **Blockers:** none. Known gaps: `docs/gaps.md`.
- **Careful:** `var/` at the root is the app's default data folder and also holds the owner's
  private file. Never write there; set `BATCHLENS_DATA_DIR`.

Keep the history in `docs/devlog.md`.
