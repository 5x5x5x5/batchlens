# The demo

Four synthetic batches of `mAb-X (synthetic)`, run one after another on the same 2,000 L
bioreactor, each followed by harvest and one aggregated Protein A capture step. Everything is
made by `src/batchlens/demo/generator.py` from fixed seeds: the same output on every run and
machine. **All of it is illustrative** ([scientific-assumptions.md](scientific-assumptions.md)).

## Reproduce it from a clean checkout

```sh
uv venv --seed --python 3.12 ~/.venvs/batchlens
export PATH="$HOME/.venvs/batchlens/bin:$PATH"
make ci                                         # installs the SDK from vendor/, builds, tests
BATCHLENS_E2E_SCREENSHOTS=shots make e2e        # the pages in a browser, screenshots in shots/
```

`make e2e` needs Playwright and Chromium once ([testing.md](testing.md), with `uv pip` in place
of `pip`): `uv pip install --python ~/.venvs/batchlens/bin/python --find-links vendor -e ".[e2e]"`
and `python -m playwright install chromium`. The journeys start the app with the four batches
seeded, against the SDK's fake PlantCraft serving the synthetic plant (`tests/plant.py`).

To load the batches into an app database yourself:

```sh
BATCHLENS_DATA_DIR=/some/folder batchlens seed-demo
```

It stores the four batches under stable ids and can be run again without changing anything.

## Inside a live PlantCraft

Without the synthetic plant, a live PlantCraft has no bioreactor: the app-owned data works,
and the trends and the product mass at harvest answer `insufficient` and name the missing
asset. To give PlantCraft the plant, the app writes two files and an administrator imports one
of them. BatchLens writes nothing to PlantCraft itself.

```sh
batchlens demo-plant --out /a/folder/plantcraft/can/read --time-zone America/Sao_Paulo
```

| File | What it is |
|---|---|
| `bioreactor.csv` | The bioreactor's recorded values: one row per instant, one column per tag |
| `plant-map.json` | PlantCraft's plant map: the CSV as a data source, the four assets, and each signal with its unit and its role on the bioreactor |

Then, in PlantCraft, an administrator imports `plant-map.json` with the plant map import
(preview first, then apply). Importing it again changes nothing.

**The time zone matters, and a wrong one is silent.** A CSV has no offsets. PlantCraft 0.6.0
reads a CSV source's times on the wall clock of its scenario's source time zone
(`scenario.source.timezone`), and the source's own time zone setting does not change that.
`--time-zone` must name that zone: `America/Sao_Paulo` for PlantCraft's local demo
(`scenarios/opcua_demo.json`), which is not the zone `GET /api/v1/installation` answers. With
the wrong zone every value lands hours off and the numbers still look plausible. Check after
importing: batch BL-0001's trends must start at 2026-07-01 06:00 UTC with no gap at either end
of the production phase, and its product mass at harvest must read 10,170 g.

Tried on 2026-11-15 with PlantCraft `v0.6.0` under `make dev` (a fresh workspace,
`DEV_FLAGS=--reset`): the import created 1 source, 4 assets and 4 signals with no issues, a
second import changed nothing, and all four batches then show seven usable metrics equal to
the values in the table below, four online trends and no gaps
(`images/live-plantcraft/3-batch-with-synthetic-plant.png`). The import was driven through
PlantCraft's own interface routes (`POST /api/map/preview` and `/api/map/apply`, as its
pages call them) by the local demo's administrator; those routes are PlantCraft's, not part
of API v1, and nothing in this repository calls them.

## The synthetic plant

| Asset id | What | Signals |
|---|---|---|
| `U-MAB` | Unit: mAb drug substance (synthetic) | |
| `BR-2001` | Production bioreactor 2000 L (equipment) | Roles `ph`, `do`, `temperature`, `volume`, from source `batchlens-synthetic` |
| `HV-2101` | Harvest clarification skid | None |
| `CH-3001` | Protein A chromatography skid | None |

The same four signals carry all four batches, so every read is scoped to a phase execution's
asset and time window. `src/batchlens/demo/plant.py` defines this plant once: the files
above and the tests' fake PlantCraft are both made from it.

## Which batch carries which scenario (ground truth)

This table is the generator's ground truth. It lives here, in the generator's separate output
and in the tests; the app's database, API and analysis code never see it, and batch ids say
nothing about it.

| Batch | Seed | Starts (UTC) | Scenario | What differs |
|---|---|---|---|---|
| `BL-0001` | 101 | 2026-07-01 06:00 | Normal, designated reference | Nothing |
| `BL-0002` | 102 | 2026-07-22 06:00 | Normal | Ordinary variability only |
| `BL-0003` | 103 | 2026-08-12 06:00 | Reduced culture productivity | qP is multiplied by 0.55 from day 7; glucose +0.8 g/L and lactate rising 0.25 g/L per day from then |
| `BL-0004` | 104 | 2026-09-02 06:00 | Reduced Protein A recovery | Normal culture; recovery 0.74 instead of 0.92 |

## What the app computes for them

Read from the API through the fake PlantCraft on 2026-11-15 (values as the page rounds them):

| Batch | IVCD | qP | Harvest mass | Harvest-to-load yield | Protein A recovery |
|---|---|---|---|---|---|
| `BL-0001` | 172 | 29.6 | 10,170 g | 97.0 % | 93.6 % |
| `BL-0002` | 181 | 31.2 | 11,290 g | 91.9 % | 91.5 % |
| `BL-0003` | 177 | 20.6 | 7,317 g | 91.0 % | 92.6 % |
| `BL-0004` | 184 | 30.7 | 11,290 g | 89.4 % | 73.4 % |

IVCD in `1e6 cell-days/mL`, qP in `pg/cell/day`. Worth noticing: the true harvest-to-load
yield is about 93 % in every batch, yet the computed one ranges from 89 to 97 %. Harvest mass
rests on a single titer result with 2 % assay noise, and the reference batch's final titer
happened to read 5 % low. The app shows that number as it is.

## What the app finds

Against the reference batch `BL-0001`, with the default tolerance of 15 %:

| Batch | Finding |
|---|---|
| `BL-0002` | Titer stayed within the tolerance over 15 compared samples |
| `BL-0003` | Titer left the reference at culture day 7.9 (sample `BL-0003-S09-titer`, 1.681 against 2.008 g/L) and stayed below in all 6 later samples; product mass at harvest 7,317 g against 10,170 g |
| `BL-0004` | Titer stayed within the tolerance. Its loss is in the Protein A step, which the metrics table shows (recovery 73.4 % against 93.6 %); no finding is raised for a step recovery yet |

The ground truth says `BL-0003`'s productivity changes from day 7. The app sees it at the next
sample, day 7.9, and says so: the first sample at which a gap is seen comes after whatever
began it. No cause is attributed (`images/findings/titer-divergence.png`).
