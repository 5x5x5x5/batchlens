# Gaps

Known gaps, with the date they were found.

| Found | Gap | State |
|---|---|---|
| 2026-11-15 | Template: a virtual environment inside the tree (`.venv`, as its quickstart suggests) makes the template's rename test fail, because the test's copy does not ignore `.venv`. Worked around by keeping the environment at `~/.venvs/batchlens`. Belongs upstream (PlantCraft repository). | Open upstream, worked around here |
| 2026-11-15 | Template: its rename test cannot pass in a renamed app (the tool refuses to run twice), although the quickstart says `make ci` is green right after `make rename`. `tests/test_rename.py` was deleted here with the owner's approval. Belongs upstream. | Open upstream, resolved here |
| 2026-11-15 | Toolchain: built and tested on Python 3.12 and Node 24, while the template's CI workflow uses Python 3.11 and Node 22. Nothing failed because of the difference so far; the workflow itself has not run (no remote). | Open |
| 2026-11-15 | Not run inside a live PlantCraft (kickoff Phase 4). There the bioreactor asset does not exist, so trends and harvest mass are `insufficient` by design; loading the synthetic plant into PlantCraft is the next slice. | Open |
| 2026-11-15 | The frame clips the full name "BatchlensCraft" in the sidebar at the "Larger text" display size (the template's display-size test fails on it). The sidebar shows the short name "Batchlens"; the manifest name is unchanged. Belongs upstream. | Worked around |
| 2026-11-15 | The template's guides (`docs/quickstart.md`, `backend.md`, `data.md`, `frontend.md`, `testing.md`, the recipes) and `prompts/` still describe the template's notes example, which this app no longer has. | Open |
| 2026-11-15 | Recorded values are shown without trailing zeros (a titer of 0.300 g/L reads 0.3): the API sends numbers and the page does not know how many decimals an assay reports. | Open |
| 2026-11-15 | No `as_of` control in the interface (out of scope for this slice); `as_of` works on the API only. | Open, planned |
| 2026-11-15 | The metrics route reads the reference batch's volume from PlantCraft on every request, and `series`/`signal` one call each: fine for four batches, not measured at scale. | Open |
| 2026-11-15 | The image (`make image`), the signed package and `make lock` were not run after the dependency and code changes; `deploy/requirements.lock` is the template's. | Open |
| 2026-11-15 | The harvest-to-load yield inherits the full assay error of one titer result (see `docs/demo.md`: 89 to 97 % computed against about 93 % true). No uncertainty is shown beside the value. | Open |
