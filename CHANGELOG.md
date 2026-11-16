# Changelog

All notable changes to this app are recorded here ([Keep a Changelog](https://keepachangelog.com)).

## [Unreleased]

BatchLens, first vertical slice (2026-11-15), built from the PlantCraft app template 0.2.0
(`dc365ec`); the entries below this one are the template's own history.

- The template's example object is replaced by batches: batch, phase executions, samples,
  assay results and pool measurements in the app's database, loaded by `batchlens seed-demo`.
- Pure calculations with one result shape (value, unit, status, reasons, inputs, version):
  IVCD, specific productivity, product mass at harvest, Protein A load and eluate masses,
  harvest-to-load yield, Protein A recovery; all honour `as_of` (no look-ahead).
- A seeded generator of four synthetic batches on one bioreactor, its ground truth kept apart.
- Five read routes under `/api/batches`; online signals are read from PlantCraft as the person,
  and a missing asset or signal is an `insufficient` result with its reason.
- Batch list and batch detail pages with the synthetic-demo banner, in English and Brazilian
  Portuguese. Trend charts use the suite's `TimeChart`, which needs `react-plotly.js` and
  `plotly.js-cartesian-dist-min` (added with the owner's approval).
- `app.toml` reads `assets`, `signals` and `series`.
- Removed: the notes object, its routes, page and tests; the template's rename test.
- Findings against the reference batch on the metrics route and the batch page: where the
  titer left the reference's (`calc.titer_divergence`), what that is in product mass at
  harvest, and no cause. Nearest-sample pairing by culture age, never interpolated.
- Findings for each step recovery (harvest-to-load yield, Protein A recovery) more than a
  tolerance below the reference's; the other results of a divergence's samples as evidence
  beside the reference's; the reference batch drawn over the VCD and titer charts at the
  same culture age (`align_to` on the samples route).
- A fifth demo batch with a normal culture and bad records (a mis-keyed sample time, a hole in
  the historian): the app flags it and answers only what rests on good records.
- Trends are means of recorded values per step, computed in the app, so a gap in the history
  stays a gap. Two titers recorded at one instant make qP `invalid`.
- `batchlens demo-plant --out DIR [--time-zone ZONE]` writes the synthetic plant as a CSV and a
  PlantCraft plant map, so an administrator can import it into a live PlantCraft and the
  demo runs end to end there (`docs/demo.md`).

## [0.2.0] - 2026-11-01

- Only the basics: the template keeps the notes (list, create, change, delete, audit),
  one page, a help page in English and Brazilian Portuguese, the tests, the image and the
  package. Search, widgets, the `note.written` event, Desk's follow-ups, the summary from a
  model and `#batchlens_note` references left the code and became recipes in `docs/recipes/`.
- Full documentation in `docs/`: quickstart, concepts, structure, server, data, interface,
  translations, testing, packaging (every `app.toml` key, and the keys PlantCraft PR #179 will
  add) and publishing.

- Earlier in this version, then moved to the recipes above: processcraft-sdk 0.35: the standard inside of an app. `suite/` is the only code that talks to
  PlantCraft (events, Desk, a model); `notes/` has `models.py`, `store.py` and `service.py`;
  routers stay thin. A note may ask for a follow-up (a day and a person): it shows on Desk's
  calendar and in that person's to-do. **Summarise** asks the model Setup gives the use
  `summary` (off until chosen). `#batchlens_note:<id>` references open the note.
- processcraft-sdk 0.28 (an app without an app key reports its conditions); nothing else changes.
- An example event, `note.written`, declared in `app.toml` and written by name
  (processcraft-sdk 0.26).

## [0.1.0] - 2026-10-23

- First version: notes on assets (list, filter, create, change, delete), audited; Ctrl+K search;
  help page; the suite's app standard and rules as tests; the image and the signed package.
