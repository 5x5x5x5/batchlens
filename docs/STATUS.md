# STATUS: BatchLens (BatchlensCraft)

Where the app stands, for people and agents picking up work here. Updated 2026-11-15.

- **How work lands:** one branch and pull request per item from `main`; the agent merges it
  itself once GitHub CI passes (owner's instruction of 2026-11-16).
- **Done:** Phases 0 to 4 of `docs/agent/kickoff.md`; the demo inside a live PlantCraft; three
  findings per compared batch (titer divergence, yield shortfall, recovery shortfall) with
  evidence and a reference overlay; a fifth, badly recorded demo batch that is flagged, not
  answered; the benchmark and `docs/verification-report.md`. Counts in `docs/devlog.md`.
- **Next tasks, in order:** (1) packaging (`make image`, `make lock`); (2) documentation cleanup and the two case studies
  ahead of making the repository public (the owner confirms that last step: it exposes commit
  emails); then the optional extensions of `ROADMAP.md`.
- **Blockers:** none. Known gaps: `docs/gaps.md`.
- **Careful:** `var/` at the root is the app's default data folder and also holds the owner's
  private file. Never write there; set `BATCHLENS_DATA_DIR`.

Keep the history in `docs/devlog.md`.
