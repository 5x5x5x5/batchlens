# Devlog

Notes on how the module changed and why, newest first: what a later contributor would need to
know that the code and `CHANGELOG.md` do not say. One short entry per change worth explaining.

## 2026-11-15: Phase 2, the object, the seed and the read API

- **Planned:** replace the example object with `batches`, a seed loader with a CLI command,
  five read routes, the synthetic plant served by the fake.
- **Built:** `batches/store.py` (five tables) and `service.py`; `demo/seed.py` and
  `batchlens seed-demo`; `api/plant.py` (reads as the person) and `api/routers/batches.py`;
  `tests/plant.py` adds a `bioreactor` asset type with the roles `ph`, `do`, `temperature`
  and `volume`, three assets and the four signals. `app.toml` reads `assets`, `signals`,
  `series`. The example object, its router and `tests/test_notes.py` are gone (the kickoff's
  "replace the example object"); the interface still shows the old page until Phase 3.
- **Where the code disagreed with the kickoff:** nothing. Roles are free text per asset type,
  so the asset's own `signals` map carries all four and no app-owned binding was needed.
- **Rulings:**
  - `as_of` is parsed strictly as ISO 8601 text. FastAPI's own `datetime` parameter read
    `as_of=12` as twelve seconds after 1970, a silent wrong answer; it is now a 422.
  - The samples route with `as_of` leaves out samples not yet collected, as well as results
    not yet available.
  - PlantCraft answering 404 or 502 becomes a reason on the metric or trend (`asset_not_found`,
    `signal_not_found`, `series_unreadable`) with HTTP 200; 401 and 403 stay errors.
  - The reference batch is compared under the same `as_of`, and not with itself.
  - Batch detail also returns the pool measurements, so a pool mass can be traced to its inputs.
  - List and detail answer the installation's time zone for the pages.
  - A batch's stored instants are whole seconds, so a stored record reads back equal to the
    generated one (the store keeps milliseconds).
- **Failed, and how it was resolved:** a POST to a read-only path answers 404, not 405 (the
  test accepts both); the translation check also reads docstrings, so the example in
  `i18n.py` now quotes a string the app has.
- **Final checks:** `make ci` exit 0: standard and strict translations pass, ruff clean (80 files),
  Vitest 3 passed, pytest 106 passed, 2 skipped (browser journeys: Playwright not installed yet).

## 2026-11-15: Phase 1, calculations and synthetic data

- **Planned:** the pure `calc` package with one result shape, the seeded generator with ground
  truth kept apart, oracle tests for both.
- **Built:** `calc` (IVCD, qP, harvest mass, pool mass, the yield and recovery ratio),
  `batches/models.py` (the record shapes), `demo/generator.py`, and `analysis/metrics.py`
  (pulled forward from Phase 2 because the generator tests need records turned into metrics).
- **Rulings** (decisions the kickoff left open):
  - qP's window runs from the first to the last sample that has both a cell count and a titer
    available, so an early `as_of` shortens the window instead of failing.
  - Harvest mass takes the last titer sample *collected* in the phase; if that one result is
    not yet available the metric is `insufficient` rather than falling back to an older sample.
  - "Volume at the sample's collection time" is the last online value at or before it, at most
    15 minutes old (`VOLUME_MAX_AGE_SECONDS`); never a later value, never interpolated.
  - The 105 % plausibility bound applies to the harvest-to-load yield too, not only recovery.
  - A negative qP is shown as `suspect`.
  - The two ratios take already computed results, so they have no `as_of` argument of their own.
  - Harvest mass does not cut the volume series itself: once the titer is available every
    value near the sample is older than `as_of`. The cut happens where the series is read.
- **Failed, and how it was resolved:**
  - The calc tests and the calc code were written in one step, so those tests were not seen
    red first. Checked afterwards by breaking the trapezoid factor (7 tests failed) and
    restoring it. The generator tests were run red before the generator existed.
  - A stale `.pyc` (two edits in the same second, same size) made restored code look broken;
    cleared `__pycache__`.
  - The first recovery tolerances were guesses and one failed by 0.1 %: the reference batch's
    final titer drew 5 % low. Tolerances are now three standard deviations of the generator's
    stated assay noise, and the seeds were left alone. Consequence worth knowing: the reference
    batch shows a 97 % harvest-to-load yield against a true 92.6 %, because harvest mass rests
    on one titer result.
- **Final checks:** `make ci` exit 0: standard and strict translations pass, ruff clean (80 files),
  Vitest 3 passed, pytest 71 passed, 2 skipped (browser journeys: Playwright not installed yet).

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
