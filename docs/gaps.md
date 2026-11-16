# Gaps

Known gaps, with the date they were found.

| Found | Gap | State |
|---|---|---|
| 2026-11-15 | Template: a virtual environment inside the tree (`.venv`, as its quickstart suggests) makes the template's rename test fail, because the test's copy does not ignore `.venv`. Worked around by keeping the environment at `~/.venvs/batchlens`. Belongs upstream (PlantCraft repository). | Open upstream, worked around here |
| 2026-11-15 | Template: its rename test cannot pass in a renamed app (the tool refuses to run twice), although the quickstart says `make ci` is green right after `make rename`. `tests/test_rename.py` was deleted here with the owner's approval. Belongs upstream. | Open upstream, resolved here |
| 2026-11-15 | Toolchain: built and tested on Python 3.12 and Node 24, while the template's CI workflow uses Python 3.11 and Node 22. The workflow passed on the `first-slice` branch (manual dispatch). A pull request did not start it by itself; not looked into. | Mostly closed |
| 2026-11-15 | A live PlantCraft has no bioreactor until an administrator imports the files of `batchlens demo-plant` (`docs/demo.md`). Verified on `v0.6.0` under `make dev` only. | Closed for the local demo |
| 2026-11-15 | PlantCraft 0.6.0 reads a CSV source's times in its scenario's source time zone and ignores the source's own time zone setting; the plant map has no column for it either. A CSV written for another zone is shifted by hours with no error. Worked around with `--time-zone` and a check in `docs/demo.md`. Belongs upstream. The app itself cannot detect the shift. | Open upstream, worked around |
| 2026-11-15 | Viewer access was not checked in a live PlantCraft: its local demo has only admins. Covered by tests on the fake only. | Open |
| 2026-11-15 | In `make dev` the launcher names the app "batchlens" (its id): an app registered by address has no display name. A packaged install reads the name from `app.toml`; not tried. | Open |
| 2026-11-15 | The frame clips the full name "BatchlensCraft" in the sidebar at the "Larger text" display size (the template's display-size test fails on it). The sidebar shows the short name "Batchlens"; the manifest name is unchanged. Belongs upstream. | Worked around |
| 2026-11-15 | The template's guides and `prompts/` described the template's notes example, which this app no longer has. | Closed 2026-11-16: removed; they live in the template's repository |
| 2026-11-15 | Recorded values are shown without trailing zeros (a titer of 0.300 g/L reads 0.3): the API sends numbers and the page does not know how many decimals an assay reports. | Open |
| 2026-11-15 | No `as_of` control in the interface (out of scope for this slice); `as_of` works on the API only. | Open, planned |
| 2026-11-15 | The metrics route reads the reference batch's volume from PlantCraft on every request, and `series`/`signal` one call each: fine for four batches, not measured at scale. | Open |
| 2026-11-15 | The image and `make lock` had not been run. | Closed 2026-11-16: `make lock` (comments only changed) and `make image` pass; the image runs read-only as uid 20100, answers `/healthz`, seeds the demo and runs the benchmark |
| 2026-11-16 | The signed package (`make dev-package`, `make package`) is not built: it needs a publisher key, and the development key is made inside the PlantCraft checkout, which this project does not modify. Installing from a package is untried. | Open |
| 2026-11-16 | `tools/run_demo.sh` imports the plant map through PlantCraft's interface routes (`/api/session`, `/api/map/apply`), which are not API v1 and were tried on PlantCraft 0.6.0 only. | Open, stated in the script |
| 2026-11-15 | The harvest-to-load yield inherits the full assay error of one titer result (see `docs/demo.md`: 89 to 97 % computed against about 93 % true). No uncertainty is shown beside the value. | Open |
| 2026-11-15 | Review, minor: `analysis/metrics.py` takes the first pool measurement of a name whatever its availability. With a re-measurement it could answer `insufficient` or use a superseded value. One measurement per pool exists today. | Open |
| 2026-11-15 | Review, minor: `calc.specific_productivity` paired titers by collection time, so two titers of one instant collapsed silently. | Closed 2026-11-16: `invalid` |
| 2026-11-15 | Review, minor: a yield or recovery whose input is `invalid` is reported `insufficient` (its reason names the input's status) rather than `invalid`. | Open, owner to decide |
| 2026-11-15 | Review, minor: a 403 or 422 from PlantCraft on one asset fails the whole list, metrics or trends route instead of becoming a reason. | Open, owner to decide |
| 2026-11-15 | Titer divergence (`titer_divergence`): the answer depends on the tolerance, and it reports when a gap is first seen, not when it began. Measured in `docs/verification-report.md` (false alarms, detections and delay by tolerance); still not shown on the page. | Partly closed |
| 2026-11-15 | Titer divergence compares with one reference batch, not a set of comparable batches, and only looks for a titer below it. The benchmark averages over five references but the app still uses one. | Open |
| 2026-11-15 | The Protein A recovery loss of the demo raised no finding. | Closed: `recovery_shortfall` |
| 2026-11-15 | A finding was not shown with its supporting evidence. | Closed: evidence tables under a divergence |
| 2026-11-16 | Evidence compares samples up to 6 h apart in culture age. For analytes that move within a day (glucose between feeds) the timing difference can exceed and even reverse the real difference; the page says nothing is concluded but does not warn about this. | Open |
| 2026-11-16 | Shown values and their shown difference do not always subtract exactly (7,410 g and 9,230 g with a difference of -1,830 g): each is rounded from the full value on its own. | Open, by design |
| 2026-11-16 | The trends route reads every recorded value of the production phase (about 2,000 per signal) to average them itself, because PlantCraft's stepped means hold the last value across a gap. Fine for a 10-minute signal over two weeks; a faster signal would need PlantCraft's `quality` or `extremes` options or a server-side gap rule. Not measured against a live PlantCraft since this change. | Open |
| 2026-11-16 | A mis-keyed sample time makes every culture metric of the batch `invalid`; the app does not offer the metric "without the suspect sample". A person can only fix the record, and there is no editing yet. | Open, planned (editing) |
| 2026-11-16 | The benchmark examines the analysis with the same generator that makes the demo: normal batches vary by 2 to 3 % and faults come in three shapes. Its false-alarm rates are a floor, not an estimate for real data. | Open, stated in the report |
| 2026-11-16 | A mild fall in productivity (qP to 85 %) is found in only 20 % of comparisons at the default tolerance, with a median delay of 7 days. | Open, by the choice of tolerance |
