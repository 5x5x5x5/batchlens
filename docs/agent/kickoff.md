# BatchLens: first vertical slice

You are the implementation engineer for BatchLens. This document is the plan, and the project
owner approved it by handing it to you: carry out Phases 0 to 3 without asking for plan
approval again. Anything outside it, or any listed stop condition, goes back to the owner.

Facts below marked **(verified)** were checked on 2026-11-15 against
`PlantCraft/plantcraft-app-template` at `dc365ec` and `PlantCraft/PlantCraft` at `527e7c4`.
Both projects move fast. When the code you find disagrees with this document, the code wins:
say so in `docs/devlog.md` and continue on what the code actually does.

## 1. What BatchLens is

An independent, open-source, synthetic-data-only, non-GxP demonstration app for monoclonal
antibody (mAb) manufacturing analytics, built as an app of the PlantCraft suite from its
published template and SDK. It is a portfolio project of an engineer with biopharmaceutical
manufacturing and software experience. Its value is domain-correct batch context, transparent
calculations and honest verification, not dashboards or chat.

The question the finished product answers: *why did this batch yield less recoverable
antibody than comparable batches?* This first slice delivers the chain that question needs:

```
VCD samples -> IVCD -> specific productivity -> harvest titer x bioreactor volume
            -> product mass at harvest -> mass loaded on Protein A -> mass eluted -> recovery
```

for four synthetic batches, shown on a batch list and a batch detail page, with every number
traceable to its inputs.

## 2. Ground rules

- The template's `AGENTS.md` and PlantCraft's `AGENTS.md`, `docs/app-standard.md`,
  `docs/api-v1.md` and `docs/testing.md` are authoritative for everything about the platform.
  This document adds the BatchLens-specific work; it never loosens a platform rule.
- Never invent an SDK call, endpoint or UI component. Read the vendored SDK and
  `@plantcraft/ui` before using them.
- Report what happened. A check you did not run is "not run", with the reason. Never describe
  a skipped or failing check as passing.
- Tests first: each behaviour gets a test that fails before the code exists.
- Smallest thing that fully works. No abstraction, option or scaffolding for later slices.

### Approved in advance

- Cloning the template and PlantCraft over SSH, read-only.
- `app.toml` permissions `read = ["assets", "signals", "series"]`. Nothing else: `write` stays
  `["audit"]`, `plant_write = false`, `outbound = []`.
- Installing the template's existing `e2e` extra (Playwright) and downloading Chromium for it.
- Local commits on a work branch (section 3.5).

### Stop and ask the owner

- Any other permission, any new Python or npm dependency, any edit under `vendor/`, to the
  Makefile's targets or to `.github/workflows/`.
- Lowering a number in `tests/floors.toml`, deleting or weakening a template test, or
  bypassing manifest validation.
- Pushing, creating a remote repository, publishing, deploying, using credentials.
- Changing anything in the PlantCraft checkout.
- The untouched template failing `make ci` (stop condition of Phase 0).

### Out of scope for this slice

Create, edit and delete routes; automated fault detection or root-cause attribution; alarms,
results, events or search contributions to PlantCraft; an as-of control in the interface;
predictive models; chat, RAG or MCP tools; drug product; real PI, LIMS, MES or QMS links;
anything that claims GMP, validation or mechanistic model validity.

## 3. Phase 0: bootstrap

Done when the renamed app passes `make ci` unchanged and that state is committed.

### 3.1 The repository

The working directory holds this file, `AGENTS.batchlens.md` and
`var/original-chat.markdown`, and is not a git repository. That last file is the owner's
private background: you do not need to read it, and you must not move, rename, edit, commit
or delete it (its folder and suffix keep it clear of the rename tool, the rename test and
git). A one-line `.gitignore` here ignores `/var/`; the template's own `.gitignore` replaces
it when you copy the template in and ignores `/var/` too (verified). Before the first commit,
confirm with `git check-ignore var/original-chat.markdown`; if it is not ignored, add `/var/`
to `.gitignore` and check again. Make it one from the template with a fresh history (what GitHub's "Use this
template" produces), with no remote:

1. Shallow-clone `git@github.com:PlantCraft/plantcraft-app-template.git` into your scratch
   folder, note its commit hash, delete its `.git`, and copy its contents here.
2. `git init -b main`, commit the untouched template as
   `batchlens: start from plantcraft-app-template @<hash>`.

If the directory is already a repository with history, do not reinitialise it: inspect it and
continue from its state.

**Naming trap (verified).** The rename tool rewrites every text file in the tree, and a
template test fails if the template app's old name is left in any file. This document and
`AGENTS.batchlens.md` deliberately never spell that name. Keep it out of everything you write.

### 3.2 Toolchain

On this machine (verified): `uv` 0.10.8, Node 24, system Python 3.14, a uv-managed Python
3.12, GNU make, Docker.

- The template's CI uses Python 3.11 and Node 22. Use Python 3.12 and the local Node 24.
  If something fails only because of those versions, record it in `docs/gaps.md` and report;
  do not change pins to get past it.
- The owner's rule is `uv`, never bare `pip` or `venv`. The template's Makefile calls
  `python -m pip` (verified) and must not be edited. Reconcile them this way: create the
  environment with `uv venv --seed --python 3.12 .venv` (seeded, so the Makefile's pip calls
  work inside it), and use `uv pip install` for anything you install by hand.
- Shell state does not persist between your commands, and the Makefile calls `ruff` and the
  app's command by bare name. Run every make target as
  `PATH="$PWD/.venv/bin:$PATH" make <target>`.

### 3.3 Read before changing anything

In the template: `AGENTS.md`, `README.md`, `docs/README.md`, `docs/quickstart.md`,
`docs/structure.md`, `docs/backend.md`, `docs/data.md`, `docs/frontend.md`, `docs/testing.md`,
`docs/translations.md`, `docs/recipes/signals.md`, `prompts/01` to `04`, and the example
object's package, router, page and tests end to end.

In PlantCraft (clone it beside this folder as `../PlantCraft`, at tag `v0.6.0`): `AGENTS.md`,
`docs/app-standard.md`, `docs/api-v1.md` (identity, assets, signal ids, series),
`docs/testing.md`. In the installed SDK: `plantcraft_sdk.testing` (`FakePlantCraft`),
`plantcraft_sdk.testplant`, `plantcraft_sdk.apptest`, `plantcraft_sdk.server.store`.

Version note (verified): the template vendors SDK 0.104.0; PlantCraft `v0.6.0` carries SDK
0.105.0 and its head 0.107.0. Record the versions you actually used in `docs/devlog.md`.

### 3.4 Baseline, rename, baseline

1. `make ci` on the untouched template. Record the result. **If it is not green, stop and
   report**: do not build on a red baseline and do not repair the template.
2. `make rename NAME=Batchlens` (verified: the name must match `[A-Z][a-z][a-z0-9]{1,24}`, so
   not `BatchLens`). It yields `BatchlensCraft`, id `batchlens`, prefix `/batchlens/`. Keep
   the default port and uid. The manifest name stays `BatchlensCraft`, the form the app
   standard prescribes for an app outside the suite; "BatchLens" is the project's name in the
   README and documents only.
3. `make ci` again, green, then commit.

### 3.5 Branch, rules, commits

- After the rename commit, work on a branch `first-slice`. The owner merges.
- Append the sections of `AGENTS.batchlens.md` to `AGENTS.md` under a heading
  `## BatchLens rules`, keeping every template rule, then delete `AGENTS.batchlens.md` and
  move this file to `docs/agent/kickoff.md`.
- One commit per finished phase at least, `make ci` green at each, message
  `batchlens: <imperative summary, the why>`, with your harness's `Co-Authored-By` line
  (PlantCraft's convention: a commit an agent wrote says so).

## 4. Architecture decisions (already made)

### 4.1 Who owns what

| Owner | Holds |
|---|---|
| PlantCraft | People, sign-in, roles, the asset tree, signals, time series, audit |
| BatchLens (its SQLite database) | Batches, phase executions, samples, assay results, pool measurements |
| Nobody (computed on request) | Metrics. They are derived from the two above each time, never stored |

BatchLens stores asset ids and reads signals and series through the SDK client as the
signed-in person, exactly as `docs/recipes/signals.md` shows. It keeps no copy of the asset
tree and no online samples.

### 4.2 Where the bioreactor's online data comes from

PlantCraft's simulator and the SDK's test plant contain only control loops (verified): there
is no bioreactor. `FakePlantCraft` accepts `assets=`, `signals=` and `series=` (verified), so:

- **In tests and browser journeys** (this slice): extend `tests/plant.py` so the fake serves
  the test plant *plus* the synthetic bioprocess assets, signals and series produced by the
  generator of Phase 1. The app then reads them through the real client calls. No fixture
  adapter inside the app, no invented endpoint, no app-owned sensor table.
- **In a live PlantCraft** those assets do not exist yet. The app must answer that honestly:
  a metric that needs a missing asset or signal is `insufficient` with a reason naming what
  was not found, and the page shows it. Never a 5xx, never a fabricated trend.
- Loading the synthetic plant into a live PlantCraft (its configuration-file import with a
  CSV source is the likely route) is the next slice. Do not attempt it, and do not write the
  online signals as the app's own derived series to work around it.

Prefer resolving a signal from the asset's own `signals` map (role to signal id) that
PlantCraft returns. Only if asset types constrain roles so that `ph`, `do`, `temperature` and
`volume` cannot be expressed, add a small app-owned binding (asset id, role, signal id) and
say why in the devlog.

### 4.3 Packages and layers

Keep the template's layering and update `LAYERS` in `tests/test_suite_rules.py`:

| Package | Role | May import |
|---|---|---|
| `calc` | Pure functions and result types. Standard library only | nothing from the app |
| `batches` | The object, replacing the example object: contract, store, service | lower layers |
| `demo` | Seeded generator and the seed loader | `batches`, lower layers |
| `analysis` | Assembles a batch's metrics from records and series, calling `calc` | `calc`, `batches` |
| `api`, `cli` | Routers, runtime, commands | everything below |

Routers stay thin and only services touch stores (the suite tests enforce both). No formulas
in the frontend: it displays what the server computed. `calc` and the generator use the
standard library only; `pandas` appears only in `tests/` where the fake requires it.

## 5. Phase 1: calculations and synthetic data (pure Python)

Done when `calc` and the generator are covered by oracle tests and `make ci` is green.

### 5.1 Result type

Every calculation returns one shape: `metric`, `value` (or none), `unit`, `status`,
`reasons` (machine-readable code plus the values involved; translation happens at the edge),
`inputs` (the ids of the samples, measurements and signals used) and `calculation_version`.

| Status | Meaning |
|---|---|
| `usable` | Computed from valid inputs |
| `suspect` | Computed, but an input or the result is implausible; the value is shown with its flag |
| `insufficient` | Not computed: something required is missing or not yet available |
| `invalid` | Not computed: an input breaks a rule |

No clipping, no unit coercion, no interpolation across a disallowed gap, no extrapolation, no
substituted denominators. Units are exact strings (`1e6 cells/mL`, `g/L`, `L`, `g`); any other
unit is `invalid` in this slice rather than converted.

### 5.2 The calculations

All times are sample **collection** times as UTC instants; elapsed days are seconds / 86400.

1. **IVCD**, `1e6 cell-days/mL`: trapezoid over consecutive VCD samples,
   `sum(0.5 * (X[i] + X[i+1]) * (t[i+1] - t[i]))`. Needs at least two samples. `invalid` for a
   negative or non-finite VCD, duplicate or non-increasing times, or a wrong unit.
   `insufficient` when a gap exceeds the configured maximum (default 3 days, a documented
   illustrative setting).
2. **Specific productivity qP**, `pg/cell/day`, culture average:
   `1000 * (titer_last - titer_first) / IVCD` over the same window, titer in `g/L`. Unit
   check: 1 pg/cell/day x 1e6 cell-days/mL = 1e6 pg/mL = 1 mg/L. It is a concentration-basis
   estimate that ignores fed-batch volume change; state that as an assumption.
3. **Product mass at harvest**, `g`: last culture titer x bioreactor volume **at that
   sample's collection time**, the volume read from the online signal. The titer sample must
   fall inside the production phase and within a configured window before its end (default
   12 h), else `insufficient`. Assumption to document: titer is per litre of supernatant and
   the volume is whole broth, so no packed-cell-volume correction is applied.
4. **Pool masses**, `g`: Protein A load and eluate, each `volume_L * concentration_g_per_L`
   from a pool measurement. Always labelled as estimated from concentration x volume, with
   the assay method named.
5. **Harvest-to-load yield**, `%`: load mass / harvest mass. It covers clarification, hold
   and transfer together; never assume it is 100.
6. **Protein A recovery**, `%`: eluate mass / load mass. Missing or zero denominator is
   `insufficient`, never 0 %. Above a configured plausibility bound (default 105, illustrative)
   it is `suspect`, value unchanged.

**As-of rule.** Every calculation takes an optional `as_of`. An assay result or pool
measurement is used only when its `result_available_at <= as_of`; online series are cut at
`as_of`. Collection time places a value on the process timeline; availability time decides
whether it may be used. The two are never merged.

### 5.3 The generator

A deterministic function of `(scenario parameters, seed)`: the same inputs give identical
output on every run and machine. Use `random.Random(seed)`, never global or time-based state.

Process, illustrative throughout: a 2,000 L CHO fed-batch production culture of about 14
days on one bioreactor, harvest, and one aggregated Protein A capture step on one skid.

- **Online signals** at a regular interval on the bioreactor: pH, dissolved oxygen (% air
  saturation), temperature (°C, with one planned shift) and volume (L, rising with feeds).
- **Offline samples**, roughly daily at irregular times, each with assay results for VCD,
  viability, glucose, lactate and titer. Each result has its own availability time: cell
  counts and metabolites within hours, titer many hours later.
- **Internal consistency**: generate titer from qP and the running IVCD, so the calculation
  library can be checked against the generator's own parameters.
- **Pool measurements** for Protein A load and eluate (volume, concentration, method, times).

Four batches, run **one after another on the same bioreactor** in separate time windows, so
the same signal id carries different batches and the code has to scope by phase window:

| Batch | Scenario | What differs |
|---|---|---|
| A | Normal, designated reference | Nothing |
| B | Normal, different seed | Ordinary variability only |
| C | Reduced culture productivity | qP falls from a set day, with shifted glucose and lactate |
| D | Reduced Protein A recovery | Normal culture; less product in the eluate |

Batch ids are neutral (no scenario in the id or name). The generator returns observations and
ground truth as **separate** objects. Ground truth (scenario label, fault parameters) is used
by tests and described in `docs/demo.md`; it is never stored in the app's database, never
returned by the API and never read by `calc` or `analysis`. "Reference" is ordinary batch
context a person assigns, so it is a field of the batch.

Do not present the model as mechanistic or validated. Do not use numbers, tags, names or
limits from any real facility.

### 5.4 Tests

- Each formula against a hand-calculated oracle with irregular spacing, the arithmetic
  written out in the test.
- Each `invalid`, `insufficient` and `suspect` case named above.
- A result that exists but is not yet available at `as_of` is not used, and the metric says
  why.
- Generator: same seed gives identical output; different seeds differ; IVCD and qP computed
  from generated samples recover the generator's parameters within the assay noise; batch C
  has lower qP than A and B; batch D has lower recovery with a normal harvest mass.

## 6. Phase 2: the object, the seed and the API

Done when the API serves the four seeded batches with metrics read through the fake, and
`make ci` is green.

### 6.1 The object

Replace the example object with `batches`: one package, several tables, one aggregate.

| Record | Fields this slice needs |
|---|---|
| Batch | id, product, reference flag, created time |
| Phase execution | id, batch id, kind (`production_culture`, `harvest`, `protein_a_capture`), asset id, start, end |
| Sample | id, batch id, phase id, `collected_at` |
| Assay result | id, sample id, analyte, value, unit, method, `result_available_at`, validity |
| Pool measurement | id, batch id, phase id, pool (`protein_a_load`, `protein_a_eluate`), volume, concentration, units, method, `measured_at`, `result_available_at` |

Every record carries a provenance field (here always the synthetic generator and its seed).
Stored instants are UTC. Follow the store, schema and migration rules of `docs/data.md`. A
phase execution is what happened on an asset, not a recipe; a batch is not an asset.

### 6.2 Seed loader

One service function loads the four generated batches into the store, idempotently by stable
id, exposed as a CLI command beside the existing ones (`batchlens seed-demo`). Tests and the
browser journey call the same function. There are no write routes in this slice.

### 6.3 Read API

Follow the example router's guards, error handling and naming. These five operations keep the
API-operations floor from falling (verified: `tests/floors.toml` says 5, and it may only rise):

| Route | Answers |
|---|---|
| `GET /api/batches` | The batches, with reference flag and phase window |
| `GET /api/batches/{id}` | One batch with its phase executions |
| `GET /api/batches/{id}/samples?as_of=` | Samples and assay results, both timestamps on each |
| `GET /api/batches/{id}/metrics?as_of=` | Every metric of 5.2 as a result object, plus the reference batch's value and the difference |
| `GET /api/batches/{id}/trends?as_of=` | The online signals over the production phase, read from PlantCraft as the person, downsampled |

If the count would still fall below the floor, stop and report rather than lower it or pad it.

### 6.4 Tests

- The test plant: bioprocess assets, signals and series added to the fake in `tests/plant.py`.
- Each route: the happy path; 404 for an unknown id; 422 for a malformed `as_of`; 401 without
  a token; 403 for the person with no access; a viewer can read.
- `as_of` before a titer result became available: samples omit it, harvest mass is
  `insufficient`.
- The asset or a signal missing from PlantCraft: `insufficient` with a reason, HTTP 200.
- Two batches on the same bioreactor do not see each other's samples or series.
- No response contains the scenario label or fault parameters.
- The suite's own rule tests, adapted to the new object (the junk test builds a real batch
  id), all still pass; permissions used match `app.toml`.

## 7. Phase 3: the pages

Done when `make ci` and `make e2e` are green and you have looked at screenshots of both pages.

- **Batch list**: a table of batches with product, bioreactor, start, end and the reference
  mark, each linking to its detail page.
- **Batch detail**: the phase executions; the metrics, each with value, unit, status and
  reasons, beside the reference batch's value and the difference; the assay results with
  collection and availability times; trends of the online signals and of VCD and titer.
- Use `@plantcraft/ui` only. It exports `Plot`, `PeriodPicker` and `timeFigure` for charts
  and times (verified in `docs/frontend.md`); do not add a chart library.
- A banner on every page, through the translation function like every other string:
  **SYNTHETIC DEMO · NON-GxP · NOT FOR PROCESS CONTROL, RELEASE OR BATCH DISPOSITION**.
- Times are shown in the installation's zone with the zone named.
- Rounding happens only in display, and never shows more precision than the inputs carry.
- `make ci` runs a strict translation check and the template ships a second language
  (verified). Supply every string in it; do not drop the language to pass.
- Tests: a Vitest test per page, and one browser journey: open the app, open a batch, see its
  phases and metrics, and see a flagged metric's reason. Install the browser tooling as
  `docs/testing.md` says, using `uv pip`.

## 8. Phase 4: inside a live PlantCraft (best effort)

Only after Phase 3. Follow `prompts/04`: install `../PlantCraft` into the same environment
with `uv pip install`, `make dev`, seed the demo, open the app from the launcher as an editor
and as a viewer, and take screenshots. Expected: sign-in, the launcher entry, the list and
the app-owned data work; trends and harvest mass report the missing bioreactor.

A failure caused by the SDK version difference or the environment is not yours to fix: record
the exact command and error in `docs/gaps.md` and move on. Never edit PlantCraft or `vendor/`.

## 9. Documents

Keep them short and true. Update the template's own: `README.md`, `SPEC.md` (purpose, object,
API, every public source used), `ROADMAP.md`, `CHANGELOG.md`, `ATTRIBUTION.md`,
`docs/STATUS.md`, `docs/gaps.md`, `docs/devlog.md`, `docs/structure.md`, and the help page
under `docs/help/`. Add two:

- `docs/scientific-assumptions.md`: each formula with units and a worked example, every
  assumption and configurable default named above, the generator's model and parameters, and
  a plain statement that all values are illustrative.
- `docs/demo.md`: reproducing the demo from a clean checkout, and which batch carries which
  scenario.

The README states that BatchLens is an independent project, not written or endorsed by the
PlantCraft maintainers, built on PlantCraft's Apache-2.0 template and SDK, and keeps the
upstream licence notices. The devlog records, per phase: what was planned, what failed and
how it was resolved, and the final check results. Do not claim productivity or accuracy
figures that were not measured.

### Where the project goes after this slice

Context for `ROADMAP.md` and for design choices, not work for now. In the intended order:

1. Load the synthetic plant into a live PlantCraft, so the demo runs end to end there.
2. Evidence-linked findings: where a batch's trajectory left the reference, and what that
   cost in product mass, with observations, calculations and hypotheses kept apart.
3. A benchmark over many seeded normal and faulty batches, including missing windows and
   misaligned sample times, publishing false positives, misses and incomplete-data behaviour.
4. An as-of control in the interface, then editing (samples, reference designation) with
   audit.
5. Batch genealogy and cumulative recovery across the rest of downstream (polishing, viral
   filtration, UF/DF), where pools split and merge.
6. Possibly later: cross-batch process monitoring, and read-only assistant tools over the
   verified calculations.

The owner also wants the way this was built to be visible: agent rules, the devlog trail and
measured test results are portfolio evidence, so keep them accurate.

## 10. Working through the phases

Finish and commit each phase green before starting the next. If you cannot finish them all in
one session, stop at a phase boundary with `docs/STATUS.md` naming the next task precisely.
Do not stop after only planning or only documenting.

## 11. Final report

1. Per phase: done, partly done or not started, with the paths that matter.
2. Every check run, with its command and its pass, fail and skip counts. Checks not run, and why.
3. Template commit, PlantCraft tag, SDK, Python and Node versions used.
4. Where the code disagreed with this document, and what you did.
5. What you saw in the browser, with screenshot paths.
6. Entries added to `docs/gaps.md`, and the scientific assumptions the owner should review
   first.
7. The next three tasks, narrowly scoped. Keep finished work and proposals clearly apart.
