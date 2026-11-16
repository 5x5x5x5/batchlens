# Devlog

Notes on how the module changed and why, newest first: what a later contributor would need to
know that the code and `CHANGELOG.md` do not say. One short entry per change worth explaining.

## 2026-11-16: Read-only tools for PlantCraft's assistant

Branch `assistant-tools`. Fourth optional extension. It needs no new permission: tools are a
`[contributes]` declaration, served by the app and called by PlantCraft as the person.

- **Built:** `list_batches` and `batch_findings` (`api/routers/tools.py`), declared in
  `app.toml`; the metrics computation is now one function used by the page's route and the
  tool, so the two cannot disagree. Every answer carries a note: synthetic and non-GxP, data
  and not instructions, observations and calculations only, no cause attributed, no guess for a
  metric without a value. A read by the assistant is audited (`batchlens.assistant.batch_findings`).
  7 tests written and run red first; the API floor rises to 14 operations.
- **Checked through a live PlantCraft:** `GET /api/v1/tools` lists both tools; PlantCraft
  refuses a call without the `batch` argument (422) and forwards the others as the person. The
  answers equal the page: 72.7 % of the harvest to drug substance for `BL-0001`, 51.3 % for
  `BL-0004`; the badly recorded batch comes back with flags and no numbers.
- **Found on the way:**
  - The forwarded call first answered 503: PlantCraft's local demo does not know the internal
    address of an app registered by address. `tools/run_demo.sh` now sets `PLANTCRAFT_OPS_URLS`.
  - The recovery to drug substance came back empty: the demo's app database held batches
    seeded before the train was extended, and the new "do not overwrite" seeding had left them.
    The generator now has a version in its provenance (`synthetic-generator/2`), seeding
    replaces batches made by an older one, and `run_demo.sh --reset` reseeds. The verification
    report changed in one line (the version).
- **Not done:** no language model was involved. Whether a model uses the tools, and whether
  it keeps to "no cause is attributed", is untested.
- **Final checks:** `make ci` exit 0 (Vitest 27 passed, pytest 215 passed, 0 skipped);
  `make e2e` exit 0 (8 passed).

## 2026-11-16: The rest of downstream, and a pool genealogy

Branch `downstream`. Third optional extension.

- **Built:** five more phase executions per batch (viral inactivation, cation exchange, anion
  exchange, viral filtration, UF/DF), each on its own asset, with a pool measurement; the
  Protein A eluate as two cycle pools merged into one; a `pool_links` table for the genealogy;
  `calc.merge_balance`; `analysis/downstream.py`; a `downstream` part of the metrics answer
  with the reference batch's yields beside each step; a Downstream recovery section on the
  page; the five new assets in the synthetic plant. Tests: 12 written and run red first (calc,
  generator, analysis); the 2 API tests and the Vitest test were written with their code.
- **Rulings:**
  - The later steps draw from their own random stream, so every value generated before this
    change is unchanged (the verification report is byte-identical, which a test checks).
  - Step yields multiply to the recovery by construction: a step's mass in is the previous
    step's mass out, and no separate product is computed.
  - A merge beyond 3 % of the sum of its parts in either direction is `suspect`
    (`MERGE_TOLERANCE_PERCENT`).
  - Only merges get a balance; the links can describe a split but nothing is computed for one.
  - No findings for the later steps yet: their yields are shown beside the reference's.
- **Failed, and how it was resolved:** six older tests assumed three phases, two pools and
  four assets, and were updated; a browser check failed on a slash inside a locator pattern
  ("UF/DF"), the test's fault, not the page's.
- **What it shows on the demo:** `BL-0004` loses 20 points in the capture step and is within a
  point or two of the reference at every later step, ending at 51.3 % of its harvest against
  the reference's 72.7 %; its two capture cycles merge with a balance of -1.4 %.
- **Seen in the browser:** `docs/images/findings/downstream.png`.
- **Final checks:** `make ci` exit 0 (Vitest 27 passed, pytest 207 passed, 0 skipped);
  `make e2e` exit 0 (8 passed).

## 2026-11-16: Editing with audit

Branch `editing`. Second optional extension, and the answer to the fifth batch: a person can
now fix the record the app refused to guess about.

- **Built:** `PATCH /api/batches/{id}/samples/{sample_id}` (a sample's collection time, with a
  reason) and `PUT /api/batches/{id}/reference`, editors only, each audited in PlantCraft; a
  `corrections` table that keeps the value replaced, who, when and why; the Samples section on
  the batch page with the correction form and the list of corrections; a "make this the
  reference batch" button behind the suite's confirmation dialog. Tests first: 19 API tests,
  3 Vitest tests, 1 browser journey. The API floor rises from 5 to 12 operations.
- **Rules of a correction:** the new time must lie inside the phase execution the sample
  belongs to and before any of the sample's own results was reported (a sample cannot be taken
  after its result exists); a reason of 5 to 500 characters; nothing else may be sent.
- **Rulings:**
  - `seed-demo` now loads only the batches that are not there, so it never silently undoes a
    correction; `seed-demo --reset` loads all five again as generated. The corrections table
    is a history and survives a reset.
  - Setting the reference to the batch that already is the reference changes nothing and is
    not audited.
  - The editing controls are hidden while the page shows an as-of view.
  - A correction is not as-of aware (`docs/gaps.md`).
- **Failed, and how it was resolved:** the edit script stopped at a mismatch for the fourth
  time, after writing two of eight files. The scripts now go through a small helper that
  checks every match of a file before writing any of it and says which file it did not change.
- **Seen in the browser:** `docs/images/findings/correction.png`: sample 9 marked corrected at
  culture day 7.96, the original time beside the corrected one, the reason, and who.
- **Final checks:** `make ci` exit 0 (Vitest 26 passed, pytest 195 passed, 0 skipped);
  `make e2e` exit 0 (8 passed).

## 2026-11-16: The as-of slider

Branch `as-of-control`. First of the optional extensions.

- **Built:** a slider on the batch page over the span in which anything about the batch became
  known (the detail route now gives that span), in 6-hour steps; every read of the page takes
  the chosen instant as `as_of`. Tests first: 2 API, 2 Vitest, 1 browser journey.
- **Found by looking at the page, and fixed:** the as-of view knew the future in two ways. A
  metric named as "not yet available" the results of samples that had not been collected yet,
  and the phase table showed end times that had not happened. Now a sample collected after
  `as_of`, a pool measured after it and a phase not yet begun do not exist in that view, and a
  phase in progress has no end. The detail route takes `as_of` too.
- **Rulings:** the slider's last position means "everything recorded" (no `as_of`); the span
  itself, which the slider needs, is the one thing the as-of view is told about the future.
- **Final checks:** `make ci` exit 0 (Vitest 23 passed, pytest 175 passed, 0 skipped);
  `make e2e` exit 0 (7 passed).

## 2026-11-16: Packaging, a one-command demo, and the documents for publication

Branch `packaging`.

- **Packaging:** `make lock` exit 0 (only the comments changed: the template's lock named
  another app); `make image` exit 0, `batchlens:0.2.0`, 423 MB. The image runs with a
  read-only root as uid 20100, answers `/healthz`, answers 401 to a page request without a
  token, seeds the demo and runs the benchmark. **Not built:** the signed package, which needs
  a publisher key made inside the PlantCraft checkout.
- **`tools/run_demo.sh`:** PlantCraft's local demo, the app, the five batches and the plant map
  import in one command. Tried with a fresh workspace: source, 4 assets and 4 signals created,
  no issues. Read back live for `BL-0001`, `BL-0003` and `BL-0005`: every metric, finding and
  trend equals the fake's, including the 18 empty trend steps of the badly recorded batch
  with the new trend code. The script calls two of PlantCraft's interface routes that are not
  API v1; the app does not.
- **Documents:** removed the template's guides, recipes and prompts (they described the
  template's example and live in its repository) and the kickoff plan; rewrote `README.md`,
  `docs/README.md` and `docs/demo.md` (run instructions and a five-minute tour); added
  `docs/case-study-engineering.md` and `docs/case-study-ai-development.md`. Screenshots are
  now `docs/images/batches.png`, `batch.png` and `findings/`; image paths named in older
  entries below (`first-slice/`, `live-plantcraft/`) no longer exist.
- **Not done:** the repository is still private. Publishing exposes the commit author's email
  address, so the owner does it.
- **GitHub CI:** the runs for pull requests 5 and 6 were still queued when this was written;
  both were merged on local `make ci` and `make e2e`.
- **Final checks:** `make ci` exit 0 (Vitest 21 passed, pytest 172 passed, 0 skipped);
  `make e2e` exit 0 (6 passed).

## 2026-11-16: The benchmark and the verification report

Branch `benchmark`. Pull request 5 was merged on local `make ci` and `make e2e` alone: its
GitHub run failed at checkout ("Repository not found", GitHub's side) and the re-run sat in
the queue.

- **Built:** `src/batchlens/benchmark/` (layer 4, the one package outside the tests that reads
  the ground truth), `batchlens benchmark`, `docs/verification-report.md`, and 9 tests written
  first, one of which fails when the published report is not what the command gives.
- **What it runs:** 20 seeds of 16 variants (normal; qP falling to 55, 70 or 85 % from day 5, 7
  or 9; Protein A recovery of 74, 80 or 86 %; three kinds of bad records) = 320 batches, each
  against 5 reference batches = 1,600 comparisons, in under 3 seconds.
- **What it found:**
  - Bad records: 0 numbers where none should be (IVCD, qP, titer finding, harvest mass, yield
    finding), and Protein A recovery still answered for 60 of 60.
  - Titer divergence at the default 15 %: 0 false alarms in 400; falls of qP to 55 % found
    300 of 300 with a median delay of 1.9 days, to 70 % 84 %, to 85 % 20 %. At 5 %: 13.5 % false
    alarms and 129 findings dated before the change began. At 10 %: 0.5 % false alarms and
    better detection of the milder falls. The default stays at 15 %; the owner may prefer 10 %.
  - Recovery shortfall at the default 10 points: no false alarms on either step; 74 % always
    found, 80 % in 88 of 100, 86 % never.
  - Calculation error against the true values: IVCD 0.7 % mean, harvest mass 1.5 % mean and
    6.6 % at worst, which is the single final titer's assay noise.
- **Rulings:** bad-record batches are scored on their own and left out of the tolerance
  tables; a batch's true recovery is matched to the nearest level the benchmark set, since the
  generator adds 0.5 % variation; the report carries no date, so it is reproducible.
- **Honest limit, stated in the report:** the examiner and the examined share one generator.
  The false-alarm rates are a floor.
- **Final checks:** `make ci` exit 0 (Vitest 21 passed, pytest 172 passed, 0 skipped).

## 2026-11-16: The fifth batch: good process, bad records

Branch `data-problem-batch`. The original proposal's fourth scenario: a historian or sample-data
problem that the analysis must flag rather than answer.

- **Built:** two record-keeping options in the generator (`mis_keyed_sample`,
  `online_gap_days`) and batch `BL-0005` using both; the tests' fake PlantCraft now has its
  clock after the last batch; a fourth browser journey.
- **What the app does with it:** IVCD and qP `invalid` (duplicated sample time, naming the
  result), harvest mass `insufficient` (no volume within 15 minutes before the sample), yield
  `insufficient`; pool masses and Protein A recovery `usable`; the titer finding `invalid`, the
  yield finding `insufficient`, the recovery finding "within". No number anywhere it should
  not be.
- **Found on the way, and fixed:**
  - **The trends drew values that were never recorded.** PlantCraft's stepped means hold the
    last value across a gap: in the fake, twelve hours of a flat 2000 L after the historian
    stopped. The trends route now reads the recorded values and averages them per step in the
    app, and a step with no value breaks the line. Caught by the new test, not by eye.
  - `calc.specific_productivity` paired titers by time and silently kept one of two titers
    recorded at one instant (a deferred finding of the first review). Now `invalid`.
  - A finding that cannot be made now says which comparison failed, not only why.
- **Rulings:** the bad batch keeps a normal culture, so the only difference from a normal batch
  is in the records; the app refuses the whole culture calculation rather than dropping the
  suspect sample, because choosing which record is wrong is a person's call.
- **Tests:** 11 run red first (generator, API, calc). One edit script missed a text match
  again and wrote nothing; caught by the red tests staying red, then redone.
- **Seen in the browser:** `docs/images/findings/bad-records.png`: the flags, and the online
  trends ending where the data ends.
- **Final checks:** `make ci` exit 0 (Vitest 21 passed, pytest 163 passed, 0 skipped);
  `make e2e` exit 0 (6 passed).

## 2026-11-16: Recovery findings, evidence and the reference overlay

Branch `mvp-findings`. The owner asked for a finding on both steps, left the tolerance to the
agent, and asked for pull requests to be merged by the agent once CI passes.

- **Built:** `calc.recovery_shortfall` (4 tests run red first); `analysis.metrics.findings`
  now answers three findings for every compared batch, with `evidence` under a divergence;
  the samples route gives each sample its culture day and, with `align_to`, the instant of the
  same culture age on another batch's timeline (8 API tests run red first); the page shows
  the findings, evidence tables and the reference batch drawn over VCD and titer (3 Vitest
  tests run red first); a third browser journey reads the recovery finding of `BL-0004`.
- **Rulings:**
  - One tolerance for both steps, 10 percentage points (`RECOVERY_TOLERANCE_POINTS`). At that
    value the demo's yield spread (89 to 97 %, assay noise on one titer) flags nothing and the
    Protein A loss (20 points) is found.
  - The consequence of a step shortfall is the mass that comes out of that step against the
    reference's (load mass for the yield, eluate mass for the recovery).
  - Findings that found nothing are still listed ("within"), so a reader sees what was checked.
  - Evidence is the other results of the diverging sample and of the last compared sample,
    beside the reference sample's, with differences and no interpretation.
  - The overlay places the reference's samples on the batch's own time axis at equal culture
    age; the server computes those instants, so no arithmetic moved into the interface.
- **Learned from looking at the page:** at the divergence, the batch's glucose reads 1.63 g/L
  below the reference although the generator makes it 0.8 g/L higher at equal age: the two
  samples are hours apart on a daily feed sawtooth. Recorded as an assumption and a gap. It is
  a good example of why the app lists evidence and concludes nothing.
- **Seen in the browser:** `docs/images/findings/titer-divergence.png`, `recovery-shortfall.png`.
- **Final checks:** `make ci` exit 0 (translations 120/120 and 2/2, ruff 85 files, Vitest 21
  passed, pytest 157 passed, 0 skipped); `make e2e` exit 0 (5 passed).

## 2026-11-15: The first finding, titer divergence from the reference (roadmap item 2)

Branch `findings`, from `main` after pull requests 1 and 2 were merged. The owner chose the rule
before it was built: the first sample whose titer is below the reference batch's at the same
culture age by more than a tolerance and stays below for every later sample; nearest-sample
pairing, no interpolation; `insufficient` where nothing can be paired.

- **Built:** `calc/comparison.py` (`titer_divergence`, 13 oracle and failure tests run red
  first), `analysis.metrics.findings`, a `findings` list on the metrics route (6 API tests run
  red first), a Findings section on the batch page (2 Vitest tests run red first), ten new
  strings in both languages, and the journey now reads the finding in the browser.
- **Rulings** (left open by the rule as agreed):
  - "At the same culture age" pairs samples up to 6 h apart (`PAIRING_WINDOW_HOURS`); the
    demo samples each day within 3 h of the same clock time, so 6 h is the largest gap it makes.
  - The tolerance is relative to the reference's titer (`reference - titer > 0.15 * reference`),
    default 15 %, with no absolute floor: the stays-below rule is what filters early noise.
  - "No divergence" is a `usable` result with no value and the reason `no_divergence`, the
    one place a usable result has no number.
  - A finding has `observation`, `consequence` and `cause`; `cause` is always null and the
    page says no cause is attributed. The consequence is the harvest mass against the
    reference's, given only when a divergence is found, with its own status.
  - Only a titer below the reference is looked for.
  - The reference batch gets no findings.
- **Failed, and how it was resolved:**
  - The "exactly the tolerance" test first used 1.7 against 2.0, which floating point puts a
    hair above 15 %. The test now uses values a float holds exactly; no margin was added to
    the comparison.
  - The script that updated the documents stopped at a text match that did not exist, after
    the code and half the documents were already committed and the pull request opened. The
    rest (this entry, `ROADMAP.md`, `docs/STATUS.md`, `docs/gaps.md`, `docs/structure.md`)
    followed in a second commit.
- **What it finds on the demo:** `BL-0003` at culture day 7.9 (ground truth: productivity
  changes from day 7), 7,317 g against 10,170 g at harvest; `BL-0002` and `BL-0004` no
  divergence. With a 20 % tolerance `BL-0003` moves to day 11.9: recorded in `docs/gaps.md`.
- **Seen in the browser:** `docs/images/findings/titer-divergence.png`.
- **Final checks:** `make ci` exit 0 (standard and strict translations 110/110 and 2/2, ruff 85
  files, Vitest 18 passed, pytest 144 passed, 0 skipped); `make e2e` exit 0 (4 passed).

## 2026-11-15: The synthetic plant inside a live PlantCraft (roadmap item 1)

Branch `live-plant`, on top of `first-slice` (pull request 1, whose GitHub CI passed on
Python 3.11 and Node 22 after a manual dispatch; the pull request alone started no run).

- **Planned:** give a live PlantCraft the bioreactor and its four signals through its own
  import, without editing PlantCraft and without writing the signals as the app's own series.
  Acceptance: under `make dev`, BL-0001 shows a usable harvest mass and four online trends.
- **Built:** `src/batchlens/demo/plant.py` (the plant defined once; `write_plant_files`),
  `batchlens demo-plant --out DIR [--time-zone ZONE]`, `tests/test_demo_plant.py` (7 tests).
  `tests/plant.py` now builds its fake from the same definition, so the bioreactor is plain
  `equipment` there too and its signal ids are `batchlens-synthetic:BIO.BR-2001.<ROLE>`.
- **How the route was found:** a throwaway script against a local PlantCraft, first through
  its single routes (asset type, assets, source, bindings), then through the plant map import,
  which carries the source, the assets and each signal's unit and role in one file. Roles are
  free text in the map, so no asset type has to be made first.
- **Failed, and how it was resolved:**
  - CSV times with a `Z` made every read fail (`Cannot compare tz-naive and tz-aware`): the
    CSV source wants times without an offset.
  - **Times without an offset were read three hours off, silently.** The first live harvest
    mass was 10,177 g against the fake's 10,174 g, and the trends began with two empty steps.
    PlantCraft's local data layer reads every source's naive times in the scenario's source
    time zone (`America/Sao_Paulo` in the local demo). Setting the source's own time zone to
    UTC, at creation or afterwards, changed nothing, and a map import resets that setting
    anyway. The CSV is therefore written on the wall clock of a zone the caller names
    (`--time-zone`), and `docs/demo.md` says how to check the result. The fake could never
    have shown this; the 3 g difference in one metric did.
  - An intermediate design kept the source out of the map (a separate `source.json`) to
    protect its time zone setting. Dropped once that setting proved to have no effect.
- **Process note:** the first version of these tests was rewritten together with the code when
  the design changed; the time-zone tests were run red first (5 failing), then green.
- **Verified live** (fresh workspace): import creates 1 source, 4 assets, 4 signals, no
  issues; a second import changes nothing; all four batches show seven usable metrics equal
  to the fake's values; four online trends, no gaps; six charts on the page
  (`docs/images/live-plantcraft/3-batch-with-synthetic-plant.png`).
- **Not done:** the import through PlantCraft's pages by hand (it was driven through the
  routes those pages call); any PlantCraft other than `v0.6.0`; a packaged install.
- **Final checks:** `make ci` exit 0 (standard and strict translations, ruff 83 files, Vitest 16
  passed, pytest 125 passed, 0 skipped); `make e2e` exit 0 (4 passed).

## 2026-11-15: Phase 4 (best effort) and the branch review

**Inside a live PlantCraft.** PlantCraft `v0.6.0` and its Simulator were installed into the
same environment with `uv pip install -e sdk/python -e ".[server,opcua]"` and `-e simulator`,
then `make dev` (which reinstalls the vendored SDK 0.104.0 over the checkout's 0.105.0, so
PlantCraft 0.6.0 ran on SDK 0.104.0), `batchlens seed-demo` into the data folder `make dev`
gives the app (`../PlantCraft/var/batchlens`), and a Playwright script.

- **Worked:** PlantCraft on :8060 and the app on :9100 both answered after about 80 s; the
  local session signs in as the demo's default person; `GET /api/v1/apps` and the launcher
  list the app (as "batchlens": an app given by address takes its id as its name); the app's
  `/api/me` answers that person with editor access and a service key; the list shows the four
  batches; the batch page shows phases, pools, assay results, the VCD and titer charts, and
  IVCD, qP, pool masses and recovery as usable.
- **As expected, the bioreactor is not there:** harvest mass and the harvest-to-load yield are
  `Insufficient` ("Asset BR-2001 was not found in PlantCraft."), all four online trends say
  the same, and the phases show the asset ids marked "Not found in PlantCraft". HTTP 200
  throughout, no 5xx in the log.
- **Not checked:** a viewer. Every person of PlantCraft's local demo is an admin, and
  `POST /api/session/switch` to another one still gives editor access; making a viewer would
  mean changing PlantCraft's own data. Viewer access is covered only by the tests on the fake.
  The launcher entry was read and screenshotted, but the script's click on it did not change
  the page (it likely opens a new tab), so the app was then opened by its address.
- **Nothing failed** because of the SDK version difference. The PlantCraft checkout's tracked
  files are unchanged (`git status` clean; its `var/` and `frontend/dist` are ignored).
- **Screenshots:** `docs/images/live-plantcraft/1-launcher.png`,
  `2-batch-without-bioreactor.png` (the guided tour's first step overlays the top of it).

**Review.** A fresh reviewer (a subagent on a mid-tier model, read-only) reviewed
`13efc0b..HEAD` against the kickoff and the rules.

- **Important, fixed:** a valid ISO `as_of` whose offset pushes the UTC instant outside years
  1 to 9999 (`0001-01-01T00:00:00+05:00`) passed validation and then raised `OverflowError`,
  a 500. `as_of` is now converted to UTC inside the validation and answers 422.
  `test_an_as_of_whose_utc_instant_does_not_exist_is_a_422_not_a_crash`: 6 red, then green.
- **Minor, deferred** (`docs/gaps.md`): the first pool measurement of a name is taken whatever
  its availability (only one per name exists today); two titers at the same collection time
  collapse silently, the last one winning; a ratio whose input is `invalid` is reported
  `insufficient` (the reason carries the input's status); a 403 or 422 from PlantCraft on one
  asset fails the whole route.
- **Found correct by the reviewer:** every oracle in `tests/test_calc.py` re-derived; the
  status rules; the `as_of` filters; batch scoping; no ground truth in the store, the API,
  `calc` or `analysis`; the documents against the code.
- **Final checks:** `make ci` exit 0 (standard and strict translations, ruff 81 files, Vitest 16
  passed, pytest 118 passed, 0 skipped); `make e2e` exit 0 (4 passed).

## 2026-11-15: Phase 3, the pages

- **Planned:** the batch list and batch detail pages on `@plantcraft/ui`, the banner, both
  languages, a Vitest test per page and one browser journey.
- **Built:** `BatchesPage.tsx`, `BatchPage.tsx`, `DemoBanner.tsx`, `words.ts` (ids and reason
  codes into words), `format.ts` (display rounding only), `when.tsx` (times and the zone line);
  100 interface strings in Brazilian Portuguese; two browser journeys; the documents
  (`README.md`, `SPEC.md`, `ROADMAP.md`, `docs/demo.md`, the help pages, `docs/structure.md`).
- **Where the code disagreed with the kickoff:**
  - `Plot` is not exported from the package root. The chart (`TimeChart`) is on the subpath
    `@plantcraft/ui/plot` and needs the app to install `react-plotly.js` and
    `plotly.js-cartesian-dist-min`. The owner approved adding both (asked, as a new npm
    dependency). Their type packages `@types/plotly.js` and `@types/react-plotly.js` came with
    them as build-only dependencies, as in PlantCraft's own apps. `react-plotly.js` also makes
    npm install its peer `plotly.js` (about 220 packages in the lockfile); it is not bundled.
  - `PeriodPicker` is not used: a batch's chart always spans its production phase.
- **Rulings:**
  - The sidebar shows the short name "Batchlens": the frame clips "BatchlensCraft" at the
    "Larger text" display size and the template's display-size test fails on it. The manifest
    name is unchanged (`docs/gaps.md`).
  - Two journeys instead of one: none of the four batches has a flagged metric when the whole
    synthetic plant is served, so the second journey runs against a PlantCraft whose
    bioreactor has no volume signal and reads the reason on the page.
  - Metrics show three significant digits, harvest mass four; a difference is shown no finer
    than the coarser of the two values beside it.
  - Batch detail lists the pool measurements, and each metric row lists its input ids.
  - The Dockerfile's description label follows the new `app.toml` summary (a suite test
    requires them to agree).
- **Failed, and how it was resolved:** dates were first asserted in a form the suite's
  formatter does not use (it writes "Jul 1, 2026, 6:00 AM UTC" in this locale); a row locator
  matched two rows because another metric's reason quotes the metric's name (anchored).
- **Seen in the browser** (`docs/images/first-slice/`): `1-batches.png` the list with four
  batches and the reference mark; `2-batch.png` batch BL-0003 with phases, seven usable
  metrics beside the reference, six charts and the results table; `3-missing-signal.png`
  batch BL-0001 without a volume signal, harvest mass and yield `Insufficient` with the reason.
- **Final checks:** `make ci` exit 0: standard and strict translations pass (100/100 and 2/2),
  ruff clean (81 files), Vitest 16 passed, pytest 110 passed, 0 skipped (the 4 browser tests
  now run inside `make ci` too, since Playwright is installed). `make e2e` exit 0: 4 passed.
- **Not run:** Phase 4 (inside a live PlantCraft); `make image`, `make package`, `make lock`;
  the GitHub workflow (no remote yet).

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
