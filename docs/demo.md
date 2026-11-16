# The demo

Five synthetic batches of `mAb-X (synthetic)`, run one after another on the same 2,000 L
bioreactor, each followed by harvest and one aggregated Protein A capture step. Everything is
made by `src/batchlens/demo/generator.py` from fixed seeds: the same output on every run and
machine. **All of it is illustrative** ([scientific-assumptions.md](scientific-assumptions.md)).

## Run it

Once:

```sh
uv venv --seed --python 3.12 ~/.venvs/batchlens
export PATH="$HOME/.venvs/batchlens/bin:$PATH"
make ci                                         # installs the SDK from vendor/, builds, tests
git clone --branch v0.6.0 https://github.com/PlantCraft/PlantCraft.git ../PlantCraft
(cd ../PlantCraft && uv pip install --python ~/.venvs/batchlens/bin/python -e sdk/python -e ".[server,opcua]" -e simulator)
```

Then, each time:

```sh
tools/run_demo.sh             # add --reset for a fresh PlantCraft workspace
```

It starts PlantCraft's local demo with BatchLens inside it, loads the five batches, writes the
synthetic plant and imports it into PlantCraft. Open http://127.0.0.1:8060 (no password in
the local demo), then BatchLens from the app switcher at the top left, or
http://127.0.0.1:9100/batchlens/ directly. Ctrl+C stops everything. The environment lives
outside the repository on purpose ([gaps.md](gaps.md)).

Tried with PlantCraft `v0.6.0` on Linux. The script uses two of PlantCraft's own interface
routes to import the plant map; they are not part of its API v1 and may change.

### Without PlantCraft

```sh
make ci                                         # everything against the SDK's fake PlantCraft
uv pip install --python ~/.venvs/batchlens/bin/python --find-links vendor -e ".[e2e]"
python -m playwright install chromium           # once
BATCHLENS_E2E_SCREENSHOTS=shots make e2e        # the pages in a browser, screenshots in shots/
batchlens benchmark --out docs/verification-report.md
```

## A five-minute tour

1. **The list.** Five batches, one bioreactor, one after another. `BL-0001` carries the
   reference mark: the batch the others are compared with. The banner on every page says what
   this data is.
2. **`BL-0003`, a culture that fell behind.** Findings: the titer left the reference at
   culture day 7.9, with the sample that showed it, how far below, and that all six later
   samples stayed below. Then what that amounts to: 7,317 g at harvest against 10,170 g. Then
   the other results of the same samples beside the reference's, and the sentence that no
   cause is attributed. Scroll to the titer chart: this batch and the reference, at equal
   culture age.
3. **Every number has a pedigree.** In the metrics table each row has a status, its reasons
   and the ids of its inputs. The masses say they are estimates from concentration x volume
   and name the assay. The assay results table at the bottom shows two times for each result:
   collected, and available.
4. **`BL-0004`, a good culture and a poor capture step.** No titer finding. Protein A recovery
   is 20 points below the reference, 7,410 g against 9,230 g in the eluate. The loss is located
   in a step, not blamed on a cause. In Downstream recovery, the same loss is one row out of
   six: every later step is within a point or two of the reference, and the batch ends at
   51 % of its harvest against the reference's 73 %. Below, the genealogy shows the two capture
   cycles merged into one eluate, with the mass balance of the merge.
5. **`BL-0005`, a good process and bad records.** One sample's time was keyed in as the
   previous one's, and the historian has a hole over the harvest sample. The app refuses the
   culture metrics and the harvest mass, names the record each tripped on, stops the trends
   where the data stops, and still answers the Protein A recovery. This is the batch to show
   someone who asks whether it can be trusted.
6. **What was known when.** Back on `BL-0003`, drag the slider to the middle of the culture.
   The finding disappears, the harvest mass says the production phase had not ended, later
   phases and samples are gone, and a titer whose sample was already taken but not yet
   reported is named as pending. This is the view an engineer had on that day.
7. **Fixing a record.** On `BL-0005`, in Samples, correct the time of `BL-0005-S09` to a day
   after sample 8, with a reason. IVCD and qP become usable, the sample is marked corrected,
   the original time stays in the list of corrections, and PlantCraft's audit log has the
   change. The hole in the historian is still a hole. (`batchlens seed-demo --reset` puts
   the demo back.)
8. **How often is it wrong?** [verification-report.md](verification-report.md): the same
   findings over 380 seeded batches with known faults.

## Inside a live PlantCraft, by hand

`tools/run_demo.sh` does the following; this is what it does and why.

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

Tried with PlantCraft `v0.6.0` under its local demo with a fresh workspace: the import creates
1 source, 4 assets and 4 signals with no issues, a second import changes nothing, and every
metric, finding and trend then equals what the tests' fake PlantCraft gives (last checked
2026-11-16 for `BL-0001`, `BL-0003` and `BL-0005`). The import goes through PlantCraft's own
interface routes (`/api/map/preview`, `/api/map/apply`), as its pages call them. Those are not
API v1; only `tools/run_demo.sh` calls them, never the app.

## The synthetic plant

| Asset id | What | Signals |
|---|---|---|
| `U-MAB` | Unit: mAb drug substance (synthetic) | |
| `BR-2001` | Production bioreactor 2000 L (equipment) | Roles `ph`, `do`, `temperature`, `volume`, from source `batchlens-synthetic` |
| `HV-2101` | Harvest clarification skid | None |
| `CH-3001` | Protein A chromatography skid | None |
| `VI-3101`, `CH-3201`, `CH-3301`, `VF-3401`, `UF-3501` | Viral inactivation vessel, cation- and anion-exchange skids, viral filtration skid, UF/DF skid | None |

The same four signals carry all five batches, so every read is scoped to a phase execution's
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
| `BL-0005` | 105 | 2026-09-23 06:00 | Data problem | A normal culture, recorded badly: sample 9's collection time was keyed in as sample 8's, and the historian kept nothing from culture day 13.4 to the end of the phase |

## What the app computes for them

Read from the API through the fake PlantCraft on 2026-11-15 (values as the page rounds them):

| Batch | IVCD | qP | Harvest mass | Harvest-to-load yield | Protein A recovery |
|---|---|---|---|---|---|
| `BL-0001` | 172 | 29.6 | 10,170 g | 97.0 % | 93.6 % |
| `BL-0002` | 181 | 31.2 | 11,290 g | 91.9 % | 91.5 % |
| `BL-0003` | 177 | 20.6 | 7,317 g | 91.0 % | 92.6 % |
| `BL-0004` | 184 | 30.7 | 11,290 g | 89.4 % | 73.4 % |
| `BL-0005` | invalid | invalid | insufficient | insufficient | 91.5 % |

IVCD in `1e6 cell-days/mL`, qP in `pg/cell/day`. Worth noticing: the true harvest-to-load
yield is about 93 % in every batch, yet the computed one ranges from 89 to 97 %. Harvest mass
rests on a single titer result with 2 % assay noise, and the reference batch's final titer
happened to read 5 % low. The app shows that number as it is.

## What the app finds

Against the reference batch `BL-0001`, with the default tolerances (15 % of titer, 10 points of
a step recovery). Every compared batch gets the same eight findings: the titer, the
harvest-to-load yield, the Protein A recovery, and the yield of each of the five later steps.
In the demo every later step of every batch is within the tolerance; the page lists what was
found first and what was checked and within tolerance together below it.

| Batch | Titer | Harvest-to-load yield | Protein A recovery |
|---|---|---|---|
| `BL-0002` | Within the tolerance over 15 compared samples | Within (91.9 % against 97.0 %) | Within (91.5 % against 93.6 %) |
| `BL-0003` | Left the reference at culture day 7.9 (sample `BL-0003-S09-titer`, 1.681 against 2.008 g/L), below in all 6 later samples; 7,317 g against 10,170 g at harvest | Within (91.0 %) | Within (92.6 %) |
| `BL-0004` | Within the tolerance | Within (89.4 %) | 20 points below (73.4 % against 93.6 %); 7,410 g against 9,230 g in the eluate |
| `BL-0005` | Could not be compared (invalid: duplicated sample time at `BL-0005-S09-titer`) | Could not be compared (no harvest mass) | Within (91.5 %) |

The ground truth says `BL-0003`'s productivity changes from day 7. The app sees it at the next
sample, day 7.9, and says so: the first sample at which a gap is seen comes after whatever
began it. Under the divergence the page lists the other results of the same samples beside the
reference's (lactate is 1.72 g/L higher at the last sample), and concludes nothing from them.
No cause is attributed anywhere (`images/findings/`). The VCD and titer charts draw the
reference batch over each batch at the same culture age.

`BL-0005` is the batch whose process was fine and whose records were not. The app does not
guess which of the two samples with one timestamp is right, and it does not reach across the
hole in the historian for a volume: IVCD and qP are `invalid`, the product mass at harvest is
`insufficient`, each with the record it tripped on, and the trends stop where the data stops
(`images/findings/bad-records.png`). What rests on good records, the pool masses and the
Protein A recovery, is still answered.
