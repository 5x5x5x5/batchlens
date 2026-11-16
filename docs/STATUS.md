# STATUS: BatchLens (BatchlensCraft)

Where the app stands, for people and agents picking up work here. Updated 2026-11-15.

- **Branch:** `first-slice`, for the owner to merge into `main`.
- **Done:** Phases 0 to 3 of `docs/agent/kickoff.md` (bootstrap, calculations and generator,
  object and read API, the two pages). `make ci` and `make e2e` are green; the counts are in
  the last entries of `docs/devlog.md`.
- **Not started:** Phase 4, trying the app inside a live PlantCraft (`prompts/04`, best effort).
- **Next task, precisely:** run Phase 4 of the kickoff. Install `../PlantCraft` (tag `v0.6.0`)
  into `~/.venvs/batchlens` with `uv pip install`, run `make dev` with
  `BATCHLENS_DATA_DIR` pointing outside the repository, run `batchlens seed-demo` against the
  same data folder, open the app from the launcher as an editor and as a viewer, take
  screenshots. Expected: sign-in, launcher entry, list and app-owned data work; trends and
  harvest mass report the missing bioreactor. A failure caused by the SDK version difference
  (0.104.0 vendored, 0.105.0 in the PlantCraft checkout) goes to `docs/gaps.md` unchanged.
- **Blockers:** none for Phase 4. Known gaps: `docs/gaps.md`.
- **Careful:** `var/` at the root is the app's default data folder and also holds the owner's
  private file. Never write there; set `BATCHLENS_DATA_DIR`.

Keep the history in `docs/devlog.md`.
