# Devlog

Notes on how the module changed and why, newest first: what a later contributor would need to
know that the code and `CHANGELOG.md` do not say. One short entry per change worth explaining.

## 2026-11-15: Phase 0, bootstrap (BatchLens first slice)

Plan: `docs/agent/kickoff.md`. Template `PlantCraft/plantcraft-app-template` @ `dc365ec`,
PlantCraft `v0.6.0` (`129b05a`, SDK 0.105.0 in its tree) cloned read-only at `../PlantCraft`.
Used: vendored SDK 0.104.0, `@plantcraft/ui` 0.108.0, Python 3.12.13 (uv-managed), Node 24.22.3,
uv 0.10.8.

- **Planned:** baseline `make ci`, `make rename NAME=Batchlens`, `make ci`, commit.
- **Failed, and how it was resolved:**
  - The kickoff put the environment in `.venv` inside the tree. The template's rename test
    copies the tree (it ignores `.git` and `node_modules`, not `.venv`) and then finds the
    template's old name inside the environment. The environment now lives outside the tree,
    `~/.venvs/batchlens`; the untouched template is then green (22 passed, 2 skipped).
  - After the rename, `ruff format --check` failed on one line of `docs/recipes/refs.md` that
    the longer name pushed past 100 columns: fixed with `make format`.
  - After the rename, the template's rename test can never pass: it runs the rename tool on a
    copy, and the tool refuses an app that was already renamed. The owner approved deleting
    `tests/test_rename.py` (asked, as the kickoff requires for a template test).
- **Where the code disagreed with the kickoff:** both points above (the kickoff expected
  `.venv` in the tree to work and `make ci` to be green right after the rename).
- **Final checks:** `make ci` exit 0: app standard and strict translations pass, ruff clean
  (68 files), Vitest 3 passed, pytest 21 passed, 2 skipped (browser journeys: Playwright not
  installed yet).

## 0.5.1

- The repository's public history starts here; earlier releases are summarized in `CHANGELOG.md`.
