# Gaps

Known gaps, with the date they were found.

| Found | Gap | State |
|---|---|---|
| 2026-11-15 | Template: a virtual environment inside the tree (`.venv`, as its quickstart suggests) makes the template's rename test fail, because the test's copy does not ignore `.venv`. Worked around by keeping the environment at `~/.venvs/batchlens`. Belongs upstream (PlantCraft repository). | Open upstream, worked around here |
| 2026-11-15 | Template: its rename test cannot pass in a renamed app (the tool refuses to run twice), although the quickstart says `make ci` is green right after `make rename`. `tests/test_rename.py` was deleted here with the owner's approval. Belongs upstream. | Open upstream, resolved here |
| 2026-11-15 | Toolchain: built and tested on Python 3.12 and Node 24, while the template's CI workflow uses Python 3.11 and Node 22. Nothing failed because of the difference so far; the workflow itself has not run (no remote). | Open |
