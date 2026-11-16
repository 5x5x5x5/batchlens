# AGENTS.md: BatchLens

The rules for anyone, person or coding agent, who changes this repository.

**BatchLens** (`batchlens`, prefix `/batchlens/`, port 9100, uid 20100) is an app of the
PlantCraft suite, made from the suite's app template: BatchLens, synthetic, non-GxP mAb batch
analytics (`README.md`). The first part of this file is the template's own rules, which all
still hold; the second part, "BatchLens rules", adds this project's.

## Where the rules come from

The suite's rules are in the PlantCraft repository
(https://github.com/PlantCraft/PlantCraft): its root `AGENTS.md`, `docs/app-standard.md` (the
app standard: manifest, layout, endpoints, image, suite table) and `docs/testing.md`. This file
repeats the ones an app must follow; when the two differ, PlantCraft's wins and this file is
fixed. The template's how-to guides (server, data, interface, translations, packaging, and
recipes for search, widgets, events and background work) are not copied here: read them in
https://github.com/PlantCraft/plantcraft-app-template.

## Start here

1. Read `README.md`, `docs/README.md` (what each document is) and `ROADMAP.md` (what is
   proposed next).
2. `make test-fast` while working, `make ci` before every commit, `make e2e` when you touched a
   page a person uses.
3. Commit messages start with the app id (`batchlens: ...`); add an entry to `docs/devlog.md`
   before you finish.

## Map and layers

```text
app.toml        the manifest: id, name, version, prefix, port, uid, permissions (single source)
src/batchlens/    the app, in layers (below)
tests/          pytest against FakePlantCraft (no real PlantCraft); tests/e2e: browser journeys
frontend/       Vite + React + TypeScript on @plantcraft/ui, served under /batchlens/
docs/           the project's documents (docs/README.md): assumptions, demo, reports, STATUS/devlog/gaps
docs/help/      help pages served at /api/help and shown under Help
vendor/         the plantcraft-sdk wheel and the @plantcraft/ui package (never edited here)
deploy/         requirements.in/.lock: the image's hashed dependencies (`make lock`)
tools/          run_demo.sh (the whole demo locally); rename.py (the template's, already used)
```

| Layer | Packages (`src/batchlens/`) | Role |
|---|---|---|
| -1 | `i18n` | `t()`; anything may use it |
| 0 | `config`, `meta` | settings from the environment; `app.toml` and the help pages |
| 1 | `suite` | what the app sends to PlantCraft with its app key (none yet) |
| 1 | `calc` | pure formulas and result types: standard library only, nothing from the app |
| 2 | `batches` | the app's object: records, store (`BatchStore`), rules (`BatchService`) |
| 3 | `demo`, `analysis` | the seeded generator and seed loader; metrics assembled from records |
| 4 | `benchmark` | the findings scored against the generator's ground truth |
| 5 | `api`, `cli` | FastAPI app under `/batchlens`, command line |

A new object goes in layer 2 beside `batches` (its own package: contract and store). Methods that
compute something (an analysis on plant signals) go in a layer between the objects and the API.
`tests/test_suite_rules.py` enforces the table: a package imports only from lower layers.

A store's `SCHEMA` is the table as a new installation makes it. A change to a table a release
shipped is a named step in the store's `MIGRATIONS` (`Migration`, `add_columns` from
`plantcraft_sdk.server.store`), never code that inspects the table at start; its test is
`apptest.upgrade_problems(Store, Store, tmp_path)`, which opens the store on the older tables.

## The rules an app follows

- **Read-only on the plant.** An app never writes to a DCS, PLC, historian or OPC UA server.
  `app.toml` says `plant_write = false` and `outbound = []`; the platform refuses any other
  package. Plant data comes only through PlantCraft's API v1 (`plantcraft_sdk.client`).
- **Refer, never copy.** An app names assets and signals by their PlantCraft id
  (`asset_id`, `signal_id`) and reads their names and data when it needs them; it keeps no copy
  of the asset tree or of plant samples.
- **Sign-in is PlantCraft's.** Every route needs a PlantCraft token that grants this app
  (`api/deps.py`, `Access`); `/healthz` is the only open one. Viewers read, editors change.
- **Every change a person makes is audited** with `Runtime.audit` (action `batchlens.<noun>.<verb>`).
- **Bad data never crashes.** Wrong input gets a 422 with words a person can act on, a missing
  object a 404, never a 500. `tests/test_suite_rules.py` sends junk to every route.
- **No silent wrong answers.** A result the app cannot compute says so, in words.
- **Offline.** No CDN, web font, telemetry or update check; the interface is built and served by
  the app. `tests/test_suite_rules.py` fails on runtime `http(s)://` fetches.
- **One language source.** Every user-facing string goes through `t()` (`src/batchlens/i18n.py`,
  `frontend/src/i18n.ts`), English first.
- **Clean room.** Use only public information: standards, public manuals, papers. Every outside
  source goes in `SPEC.md`; every third-party asset or library in `ATTRIBUTION.md`. No client or
  employer data, names or hostnames, even as examples.
- **One frame.** Pages use `@plantcraft/ui` (sidebar, page header, tables, forms, help); do not
  restyle them. The app's colour comes from its mark only.
- **Tests are the gate.** Every change comes with a test that fails without it; the numbers in
  `tests/floors.toml` only rise.

## What is the platform's, never the app's

Users, sign-in, roles and groups, assets and asset types, signals and data sources, the
historian, messages, licences, backups and the launcher are PlantCraft's. An app adds its own
object, the methods on it and its workflow. When two apps would need the same thing, it belongs
in PlantCraft (ask a maintainer) rather than in either app.

## Maintainer decisions (stop and ask)

A new permission in `app.toml` (`read`, `write`), any write path toward the plant, a new outside
dependency, the app's id, prefix, port and uid once it was installed somewhere, and anything that
changes what the platform must do for the app.

## BatchLens rules

These sections are appended to the template's `AGENTS.md` under `## BatchLens rules`. They add
to the platform's rules and never loosen one: where they differ, PlantCraft's rule wins.

### What BatchLens is

An independent, open-source, synthetic-data-only, non-GxP demonstration of mAb manufacturing
analytics for process engineers and manufacturing-informatics people. It joins batch phases,
plant signals, offline assay results and product mass balances. It is not an MES, LIMS or QMS,
and it makes no release, disposition or control decision. It is a portfolio project: clear
decisions, reproducible results and honest reporting matter more than breadth.

### Domain rules

- **Synthetic only.** No employer or client data, tags, names, recipes, limits, schedules or
  screenshots, even as examples. Every page says the data is synthetic and non-GxP.
- **Four things that are not each other.** A batch is not an asset. A phase execution (what
  happened on an asset, with start and end) is not a recipe. An assay result is not an online
  sample. The time a sample was collected is not the time its result became available.
- **A batch is a window on shared equipment.** The same signal carries many batches; every
  read of plant data is scoped to a phase execution's asset and time window.
- **No look-ahead.** A result is used in an analysis only from its availability time on.
  Collection time places it on the process timeline; it never grants earlier use.
- **Units are explicit** on every stored and returned quantity. Instants are stored in UTC
  and shown in the installation's zone, named.
- **Ground truth stays out.** Scenario labels and fault parameters of the synthetic data
  live in the generator's separate output, the tests, the benchmark and the documents. They
  are never stored in the app's database, returned by the API or read by analysis code. The
  `benchmark` package is the one reader outside the tests: it scores the analysis, it is not
  part of it.
- **Nothing universal is hard-coded.** No critical process parameter or quality attribute
  classification, acceptance limit or viral-clearance claim. Plausibility bounds and gap
  limits are named settings with illustrative defaults, listed in
  `docs/scientific-assumptions.md`.

### Calculation rules

- Formulas live in the pure `calc` package: standard library only, no imports from the rest
  of the app, no I/O. Never in the frontend, a router or a store.
- Every result carries value, unit, status (`usable`, `suspect`, `insufficient`, `invalid`),
  reasons, the ids of its inputs and a calculation version. Change a formula, bump its version.
- Prefer `insufficient` or `invalid` to a number that looks precise and is not supported.
  Never interpolate across a disallowed gap, extrapolate, coerce units, substitute a
  denominator or clip a surprising result. A surprising result is shown, flagged `suspect`.
- A mass derived from concentration times volume says so, and names the assay method.
- A new or changed formula comes with a hand-calculated oracle test, a test for each failure
  status, and its entry (units, worked example, assumptions) in
  `docs/scientific-assumptions.md`.
- Rounding is for display only and never shows more precision than the inputs have.

### Data ownership

- PlantCraft owns assets, signals, series, people and audit. BatchLens owns batches, phase
  executions, samples, assay results and pool measurements. Metrics are computed on request
  and not stored.
- Online data is read through the SDK client. Never copy it into the app's database, and never
  publish synthetic sensor data as the app's own derived series.
- A missing asset, signal or result is an answer (`insufficient`, with what was not found),
  not an error.

### Working here

- Run make targets as `PATH="$HOME/.venvs/batchlens/bin:$PATH" make <target>`. The environment
  is made with `uv venv --seed --python 3.12 ~/.venvs/batchlens`, outside the tree (a `.venv`
  inside it gets swept up by tests that walk the folder; `docs/gaps.md`); install by hand with
  `uv pip`, never bare `pip`.
- Start of a session: `git status`, then `ROADMAP.md`, `docs/gaps.md` and the last devlog
  entries. Take one small task with a stated acceptance test.
- `var/` at the root is the app's default data folder and is not tracked. Never write there
  while developing; set `BATCHLENS_DATA_DIR`.
- Type hints on public functions, the `logging` module rather than `print`, `ruff` clean.
- Done means: tests written first and passing, bad and missing data handled, `make ci` green,
  `make e2e` green when a page changed, and the documents say what is now true.
- Ask the owner before: a new dependency or permission, any edit to `vendor/`, the Makefile's
  targets or the CI workflow, lowering a floor or weakening a test, pushing or publishing,
  using credentials, changing the licence, or touching anything real (plant systems or data).
- Keep implemented, verified, simulated and proposed clearly apart in every report and
  document. Never claim GxP compliance, validation or mechanistic model validity.
