# SPEC: BatchLens (BatchlensCraft)

What the app does and the public sources it relies on (AGENTS.md, "Clean room").

## Purpose

A synthetic-data-only, non-GxP demonstration of mAb manufacturing analytics: for four
synthetic batches it shows the chain from viable cell density to Protein A recovery, with every
number traceable to its inputs. It makes no release, disposition or control decision.

## Who owns what

| Owner | Holds |
|---|---|
| PlantCraft | People, sign-in, roles, the asset tree, signals, time series, audit |
| BatchLens (its SQLite database) | Batches, phase executions, samples, assay results, pool measurements |
| Nobody (computed on request) | Metrics: derived from the two above each time, never stored |

## Object

One aggregate, the batch record (`src/batchlens/batches/models.py`), in five tables.

| Record | Fields |
|---|---|
| Batch | `batch_id`, `product`, `is_reference`, `created_at` |
| Phase execution | `phase_id`, `batch_id`, `kind` (`production_culture`, `harvest`, `protein_a_capture`), `asset_id` (PlantCraft's), `start`, `end` |
| Sample | `sample_id`, `batch_id`, `phase_id`, `collected_at` |
| Assay result | `result_id`, `sample_id`, `analyte`, `value`, `unit`, `method`, `result_available_at`, `validity` |
| Pool measurement | `measurement_id`, `batch_id`, `phase_id`, `pool` (`protein_a_load`, `protein_a_eluate`), `volume`, `volume_unit`, `concentration`, `concentration_unit`, `method`, `measured_at`, `result_available_at` |

Every record carries `provenance` (here always the synthetic generator and its seed). Stored
instants are UTC. Records are loaded only by `batchlens seed-demo`; there is no create, change
or delete route in this version.

## API

All read-only, all behind a PlantCraft token that grants this app; viewers and editors read alike.

| Route | Answers |
|---|---|
| `GET /api/batches` | The batches, with reference flag, window and bioreactor |
| `GET /api/batches/{id}` | One batch with its phase executions and pool measurements |
| `GET /api/batches/{id}/samples?as_of=&align_to=` | Samples and assay results, both timestamps on each, and each sample's culture day; with `align_to`, also the instant of the same culture age on another batch's timeline |
| `GET /api/batches/{id}/metrics?as_of=` | Every metric as a result object, the reference batch's value and the difference; and `findings` against the reference batch (titer divergence, and a shortfall of each step recovery), each with an `observation` (a result object), a `consequence`, `evidence` and a `cause` that is always null |
| `GET /api/batches/{id}/trends?as_of=` | The bioreactor's online signals over the production phase, read from PlantCraft as the person, downsampled |

`as_of` is an ISO 8601 instant (UTC without an offset): the answer holds only what was collected
and available by then. Unknown batch 404; malformed `as_of` 422; no token 401; no access 403. A
missing asset, signal or series in PlantCraft is HTTP 200 with the metric or trend
`insufficient` and a reason. Plus the standard `/healthz`, `/api/me`, `/api/meta`, `/api/help`.

Permissions (`app.toml`): read `assets`, `signals`, `series`; write `audit`; no plant write, no
outbound connection.

## Calculations

IVCD, specific productivity, product mass at harvest, Protein A load and eluate masses,
harvest-to-load yield, Protein A recovery, and where a batch's titer left the reference batch's: formulas, units, worked examples, statuses and
every assumption are in [docs/scientific-assumptions.md](docs/scientific-assumptions.md).

## Sources

Only public, textbook-level knowledge and the PlantCraft suite's own documents:

- PlantCraft's app standard, API v1 and SDK (`docs/app-standard.md`, `docs/api-v1.md` of the
  PlantCraft repository, Apache-2.0).
- The trapezoidal rule for the integral of viable cell density, and specific productivity as
  product formed per integral of viable cells: standard definitions in cell culture
  engineering textbooks and review articles. No specific publication's data, figures or
  parameter values are used.
- The mass balance (mass = concentration x volume; step yield = mass out / mass in).

Every number in the generator is illustrative and chosen by hand
([docs/scientific-assumptions.md](docs/scientific-assumptions.md)); none comes from a
publication, a facility, an employer or a client.
