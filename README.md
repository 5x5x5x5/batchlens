<p align="center"><img src="docs/images/logo.svg" width="72" height="72" alt="BatchLens"></p>

# BatchLens

**Synthetic demo · non-GxP · not for process control, release or batch disposition.**

BatchLens is a demonstration of monoclonal antibody (mAb) manufacturing analytics, built as an
app of the [PlantCraft](https://github.com/PlantCraft/PlantCraft) suite. It joins batch phases,
plant signals, offline assay results and product mass balances, and shows every number with
its inputs, its status and the reasons for it.

The question it is being built to answer: *why did this batch yield less recoverable antibody
than comparable batches?* This first slice delivers the chain that question needs, for four
synthetic batches:

```
VCD samples -> IVCD -> specific productivity -> harvest titer x bioreactor volume
            -> product mass at harvest -> mass loaded on Protein A -> mass eluted -> recovery
```

## What it is, and is not

- **Independent.** BatchLens is a personal portfolio project. It is not written, reviewed or
  endorsed by the PlantCraft maintainers. It is built on PlantCraft's Apache-2.0 app template
  and SDK, and keeps their licence notices ([LICENSE](LICENSE), [ATTRIBUTION.md](ATTRIBUTION.md)).
- **Synthetic only.** Every batch, sample, signal and limit is made by a seeded generator
  ([docs/demo.md](docs/demo.md)). Nothing comes from a real facility, employer or client.
- **Not GxP.** It is not an MES, LIMS or QMS, it is not validated, and it makes no release,
  disposition or control decision. Its model of a cell culture is a shape generator, not a
  mechanistic or validated model ([docs/scientific-assumptions.md](docs/scientific-assumptions.md)).
- **Named** `BatchlensCraft` (id `batchlens`, prefix `/batchlens/`) in its manifest, the form
  PlantCraft's app standard prescribes for an app outside the suite.

## What works today

| Part | State |
|---|---|
| Pure calculations (`src/batchlens/calc/`), each with a hand-calculated oracle test | Implemented, tested |
| Seeded generator of four batches, with its ground truth kept out of the app | Implemented, tested |
| Batches, phase executions, samples, assay results and pool measurements in the app's database | Implemented, tested |
| Five read routes; online signals read from PlantCraft as the signed-in person | Implemented, tested against the SDK's fake PlantCraft |
| Batch list and batch detail pages | Implemented, tested (Vitest, two browser journeys) |
| Running inside a live PlantCraft | Verified once on PlantCraft 0.6.0 (local `make dev`): after an administrator imports the files of `batchlens demo-plant`, all metrics and trends are served from PlantCraft ([docs/demo.md](docs/demo.md)). Without that import the app reports the missing bioreactor |

Where the app stands in detail: [docs/STATUS.md](docs/STATUS.md). What comes next:
[ROADMAP.md](ROADMAP.md).

## Run it

You need `uv`, Python 3.12, Node.js, `make` and Git. The Python environment lives outside the
tree (a `.venv` inside it breaks a test that walks the folder, [docs/gaps.md](docs/gaps.md)).

```sh
uv venv --seed --python 3.12 ~/.venvs/batchlens
export PATH="$HOME/.venvs/batchlens/bin:$PATH"
make ci                    # app standard, translations, lint, interface build and tests, pytest
make e2e                   # browser journeys (see docs/testing.md for Playwright)
```

[docs/demo.md](docs/demo.md) reproduces the demo from a clean checkout and says which batch
carries which scenario.

## How it was built

With a coding agent, under written rules, and the trail is part of the project:
[AGENTS.md](AGENTS.md) (the rules), [docs/agent/kickoff.md](docs/agent/kickoff.md) (the plan
the agent was given), [docs/devlog.md](docs/devlog.md) (what was planned, what failed and how it
was resolved, the measured check results) and [docs/gaps.md](docs/gaps.md) (what is known to
be missing or wrong).

## Where things are

| Path | What it is |
|---|---|
| `src/batchlens/calc/` | The formulas and the result type. Standard library only |
| `src/batchlens/batches/` | The app's object: records, store, service |
| `src/batchlens/demo/` | The seeded generator and the seed loader |
| `src/batchlens/analysis/` | A batch's metrics, assembled from records and the volume signal |
| `src/batchlens/api/` | The routes, and what they read from PlantCraft (`plant.py`) |
| `frontend/src/` | The two pages, on `@plantcraft/ui` |
| `tests/` | pytest against the SDK's fake PlantCraft; `tests/e2e/` browser journeys |
| `docs/` | The template's guides, plus this app's own notes and assumptions |

The guides under `docs/` (quickstart, backend, data, frontend, testing, packaging, publishing,
recipes) and `prompts/` are the template's own and still describe its example app.

## License

Apache-2.0 ([LICENSE](LICENSE)). Third-party assets and libraries: [ATTRIBUTION.md](ATTRIBUTION.md).
