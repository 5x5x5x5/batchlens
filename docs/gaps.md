# Gaps

Known gaps, with the date they were found.

| Found | Gap | State |
|---|---|---|
| 2026-11-15 | Template: a virtual environment inside the tree (`.venv`, as its quickstart suggests) makes the template's rename test fail, because the test's copy does not ignore `.venv`. Worked around by keeping the environment at `~/.venvs/batchlens`. Belongs upstream (PlantCraft repository). | Open upstream, worked around here |
| 2026-11-15 | Template: its rename test cannot pass in a renamed app (the tool refuses to run twice), although the quickstart says `make ci` is green right after `make rename`. `tests/test_rename.py` was deleted here with the owner's approval. Belongs upstream. | Open upstream, resolved here |
| 2026-11-15 | Toolchain: built and tested on Python 3.12 and Node 24, while the template's CI workflow uses Python 3.11 and Node 22. Nothing failed because of the difference so far; the workflow itself has not run (no remote). | Open |
| 2026-11-15 | Inside a live PlantCraft (tried once, `docs/devlog.md`) the bioreactor asset does not exist, so trends and harvest mass are `insufficient` by design; loading the synthetic plant into PlantCraft is the next slice. | Open, planned |
| 2026-11-15 | Viewer access was not checked in a live PlantCraft: its local demo has only admins. Covered by tests on the fake only. | Open |
| 2026-11-15 | In `make dev` the launcher names the app "batchlens" (its id): an app registered by address has no display name. A packaged install reads the name from `app.toml`; not tried. | Open |
| 2026-11-15 | The frame clips the full name "BatchlensCraft" in the sidebar at the "Larger text" display size (the template's display-size test fails on it). The sidebar shows the short name "Batchlens"; the manifest name is unchanged. Belongs upstream. | Worked around |
| 2026-11-15 | The template's guides (`docs/quickstart.md`, `backend.md`, `data.md`, `frontend.md`, `testing.md`, the recipes) and `prompts/` still describe the template's notes example, which this app no longer has. | Open |
| 2026-11-15 | Recorded values are shown without trailing zeros (a titer of 0.300 g/L reads 0.3): the API sends numbers and the page does not know how many decimals an assay reports. | Open |
| 2026-11-15 | No `as_of` control in the interface (out of scope for this slice); `as_of` works on the API only. | Open, planned |
| 2026-11-15 | The metrics route reads the reference batch's volume from PlantCraft on every request, and `series`/`signal` one call each: fine for four batches, not measured at scale. | Open |
| 2026-11-15 | The image (`make image`), the signed package and `make lock` were not run after the dependency and code changes; `deploy/requirements.lock` is the template's. | Open |
| 2026-11-15 | The harvest-to-load yield inherits the full assay error of one titer result (see `docs/demo.md`: 89 to 97 % computed against about 93 % true). No uncertainty is shown beside the value. | Open |
| 2026-11-15 | Review, minor: `analysis/metrics.py` takes the first pool measurement of a name whatever its availability. With a re-measurement it could answer `insufficient` or use a superseded value. One measurement per pool exists today. | Open |
| 2026-11-15 | Review, minor: `calc.specific_productivity` pairs titers by collection time, so two titers of one instant collapse silently (the last wins). Duplicate cell counts are `invalid`; duplicate titers should be too. | Open |
| 2026-11-15 | Review, minor: a yield or recovery whose input is `invalid` is reported `insufficient` (its reason names the input's status) rather than `invalid`. | Open, owner to decide |
| 2026-11-15 | Review, minor: a 403 or 422 from PlantCraft on one asset fails the whole list, metrics or trends route instead of becoming a reason. | Open, owner to decide |
