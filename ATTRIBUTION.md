# Third-party assets and libraries

Every third-party asset (font, icon, image, dataset) and every direct dependency
has a row here (AGENTS.md, "Clean room"). The BatchlensCraft mark (`docs/images/logo.svg`,
`frontend/public/favicon.svg`), the suite frame `@plantcraft/ui` (vendored package: tokens,
fonts setup, sidebar, help browser, brand marks, chart colours) is original work of the
PlantCraft authors (Apache-2.0).

## Fonts and icons (bundled, served offline)

| Asset | Source | License |
|---|---|---|
| IBM Plex Sans, IBM Plex Mono | `@fontsource/ibm-plex-sans`, `@fontsource/ibm-plex-mono` (IBM) | SIL Open Font License 1.1 |
| Lucide icons | `lucide-react` | ISC |

## Frontend libraries

| Library | License |
|---|---|
| React, React DOM | MIT |
| Plotly.js (`plotly.js-cartesian-dist-min`), `react-plotly.js` (direct dependencies since the batch page draws charts; `react-plotly.js` also installs its peer `plotly.js`, which is not bundled) | MIT |
| `@types/plotly.js`, `@types/react-plotly.js` (type declarations, build only) | MIT |
| `@plantcraft/ui` (vendored package, PlantCraft authors) | Apache-2.0 |
| Vite, Vitest, TypeScript, jsdom (build and test only) | MIT |

## Python libraries

| Library | License |
|---|---|
| plantcraft-sdk (vendored wheel, PlantCraft authors) | Apache-2.0 |
| NumPy (suggested limits), pandas (through plantcraft-sdk) | BSD-3-Clause |
| pydantic | MIT |
| httpx | BSD-3-Clause |
| cryptography (through plantcraft-sdk) | Apache-2.0 or BSD-3-Clause |
| FastAPI, Starlette, Uvicorn | MIT / BSD-3-Clause |
| pytest, Ruff (development only) | MIT |
| Playwright for Python (e2e tests only, never in the image) | Apache-2.0 |

## Data

No third-party dataset is committed. The test plant (`plantcraft_sdk.testplant`, a port of
The Simulator's loop equations) is synthetic. The bioprocess batches, samples and signals are
made by this repository's own seeded generator (`src/batchlens/demo/generator.py`); every
parameter in it is illustrative and chosen by hand, none taken from a publication or a facility.

## Built on

BatchLens is an independent project built from the PlantCraft app template
(`PlantCraft/plantcraft-app-template` at `dc365ec`, Apache-2.0) and the vendored
`plantcraft-sdk` 0.104.0 and `@plantcraft/ui` 0.108.0 (Apache-2.0, PlantCraft authors). The
template's files keep their licence; the PlantCraft maintainers did not write, review or
endorse BatchLens.
