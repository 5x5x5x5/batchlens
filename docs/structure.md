# Structure

```text
app.toml              the manifest: id, name, version, prefix, port, permissions (single source)
pyproject.toml        the Python package and its dependencies
Makefile              every command: ci, dev, serve, rename, image, package
Dockerfile            the image: three stages, hashed dependencies, non-root, read-only root
src/batchlens/          the server (Python, FastAPI on plantcraft-sdk)
frontend/             the interface (Vite, React, TypeScript on @plantcraft/ui)
tests/                pytest against a fake PlantCraft; tests/e2e: browser journeys
docs/                 this documentation, the help pages (docs/help) and the app's own notes
vendor/               the plantcraft-sdk wheel and the @plantcraft/ui package, with their hashes
deploy/               requirements.in and requirements.lock: the image's pinned dependencies
prompts/              prompts for a coding agent: new app, add an object, add a page, try, package
tools/rename.py       make rename
.github/workflows/    ci.yml: make ci on every push and pull request
AGENTS.md, CLAUDE.md  the rules, for people and for coding agents
SPEC.md, ROADMAP.md   what the app does and its public sources; what comes next
CHANGELOG.md          what changed in each version
SECURITY.md, LICENSE, ATTRIBUTION.md   how to report a flaw, the licence, third-party credits
```

## The server: `src/batchlens/`

| File | What it does |
|---|---|
| `__init__.py` | `APP_ID` and `__version__` |
| `i18n.py`, `locales/` | `t()` and the server's translations ([translations.md](translations.md)) |
| `config.py` | `Settings`: every setting from the environment, each with a safe default |
| `meta.py` | Reads `app.toml` and the help pages for `/api/meta` and `/api/help` |
| `calc/results.py` | The result type, its statuses and reasons, and the input types |
| `calc/culture.py`, `calc/mass.py` | The formulas: IVCD, qP; harvest mass, pool mass, the ratios |
| `calc/comparison.py` | A batch against the reference: where its titer left the reference's; a step recovery below it |
| `batches/models.py` | The records: batch, phase execution, sample, assay result, pool measurement |
| `batches/store.py` | `BatchStore`: five tables in the app's SQLite database |
| `batches/service.py` | `BatchService`: the object's rules, without HTTP |
| `demo/generator.py` | The seeded generator; observations and ground truth as separate objects |
| `demo/seed.py` | `seed_demo`: loads the four demo batches into the store |
| `demo/plant.py` | The synthetic plant, defined once: the CSV and plant map a live PlantCraft imports |
| `analysis/metrics.py` | A batch's metrics from its records and the volume signal; the comparison with the reference |
| `benchmark/run.py`, `benchmark/report.py` | The findings scored against ground truth over many seeded batches; the verification report |
| `api/runtime.py` | `Runtime`: one server's settings, database, services and PlantCraft clients |
| `api/deps.py` | Who may do what (`CurrentUser`) and shared checks (`batch_or_404`) |
| `api/plant.py` | What the pages read from PlantCraft as the person: asset names, volume, trends |
| `api/routers/batches.py` | The five read routes |
| `api/app.py` | `create_app()`: the suite's standard endpoints plus the routers and the built interface |
| `cli.py` | `batchlens serve`, `check`, `seed-demo`, `demo-plant` and `benchmark` |

### Layers

A package imports only from layers below it. `tests/test_suite_rules.py` holds the table and
fails on an import that points up.

| Layer | Packages | Role |
|---|---|---|
| -1 | `i18n` | `t()`; anything may use it |
| 0 | `config`, `meta` | settings, the manifest, the help pages |
| 1 | `suite` | what the app sends to PlantCraft on its own (nothing yet) |
| 1 | `calc` | pure functions and result types: standard library only, nothing from the app |
| 2 | `batches` | the app's object: records, store, service |
| 3 | `demo`, `analysis` | the generator and seed loader; metrics assembled from records |
| 4 | `benchmark` | scores the analysis against the generator's ground truth |
| 5 | `api`, `cli` | the entry points |

Routers stay thin and only the service touches the store. Formulas live in `calc` only: never
in the interface, a router or a store.

## The interface: `frontend/src/`

| File | What it does |
|---|---|
| `main.tsx` | Starts the app: theme, language, the frame |
| `App.tsx` | The frame (`SuiteShell`), the banner and the routes |
| `pages.tsx` | `NAV` (the sidebar) and the guided tour |
| `DemoBanner.tsx` | The synthetic, non-GxP banner shown on every page |
| `BatchesPage.tsx` | The batch list |
| `BatchPage.tsx` | One batch: phases, metrics, pools, trends, assay results |
| `words.ts` | Words for metric, phase and analyte ids, statuses and reason codes |
| `format.ts` | Rounding for display only |
| `when.tsx` | Times in the installation's zone, and the line that names it |
| `SuitePages.tsx` | The help page, the same in every app |
| `api.ts`, `types.ts` | Every call to the server, and the shapes it sends |
| `nav.ts` | Paths under the app's prefix, `Link`, `navigate` |
| `i18n.ts`, `locales/` | `t()` and the interface's translations |
| `ui.tsx` | The shared blocks the pages use, in one import |
| `*.test.ts(x)` | Vitest tests |

## Tests: `tests/`

| File | What it checks |
|---|---|
| `plant.py`, `conftest.py` | A fake PlantCraft with the suite's test plant plus the synthetic bioprocess plant, and four people; a runtime and a client wired to it |
| `test_calc.py` | Each formula against a hand-calculated oracle; each failure status |
| `test_divergence.py` | The titer divergence rule against hand-worked cases |
| `test_benchmark.py` | The benchmark's counts and invariants; the published report is what it gives today |
| `test_generator.py` | Determinism, internal consistency, the scenarios, no ground truth in what the app sees |
| `test_demo_plant.py` | The plant files: every value at its time, the time zone, the map, agreement with the fake |
| `test_batches.py` | The store, the seed, each route, `as_of`, what PlantCraft lacks, scope between batches |
| `test_app_standard.py` | `app.toml` agrees with the code; the standard endpoints answer |
| `test_suite_rules.py` | Offline, layers, thin routers, junk never answers 500, no route without a token, the image |
| `floors.toml` | Numbers that only rise (API operations under test) |
| `e2e/` | Browser journeys with Playwright (`make e2e`) |
