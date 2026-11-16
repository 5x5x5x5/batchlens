// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { BatchDetail, BatchList, Metrics, Samples, Trends } from "./types";

const answers = vi.hoisted(() => ({ list: null as unknown, detail: null as unknown, metrics: null as unknown, samples: null as unknown, trends: null as unknown }));
vi.mock("./api", () => ({
  UNAUTHORIZED_EVENT: "unauthorized",
  api: {
    batches: () => Promise.resolve(answers.list),
    batch: () => Promise.resolve(answers.detail),
    metrics: () => Promise.resolve(answers.metrics),
    samples: () => Promise.resolve(answers.samples),
    trends: () => Promise.resolve(answers.trends),
  },
}));
// The chart needs Plotly and a real layout: the page test only checks what it is given.
vi.mock("@plantcraft/ui/plot", () => ({
  TimeChart: ({ lines }: { lines: Array<{ name: string; t: string[] }> }) => <div data-chart={lines.map((line) => `${line.name}:${line.t.length}`).join("|")} />,
}));

import { BatchPage } from "./BatchPage";
import { BatchesPage } from "./BatchesPage";
import { DemoBanner } from "./DemoBanner";
import { NAV } from "./pages";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

async function render(node: React.ReactNode): Promise<HTMLElement> {
  const host = document.createElement("div");
  document.body.replaceChildren(host);
  await act(async () => { createRoot(host).render(node); });
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)); });
  return host;
}

const LIST: BatchList = {
  time_zone: "UTC",
  batches: [
    { batch_id: "BL-0001", product: "mAb-X (synthetic)", is_reference: true, created_at: "2026-07-01T06:00:00.000Z", provenance: "synthetic-generator/1 seed=101", start: "2026-07-01T06:00:00.000Z", end: "2026-07-16T08:00:00.000Z", asset_id: "BR-2001", asset_name: "Production bioreactor 2000 L" },
    { batch_id: "BL-0002", product: "mAb-X (synthetic)", is_reference: false, created_at: "2026-07-22T06:00:00.000Z", provenance: "synthetic-generator/1 seed=102", start: "2026-07-22T06:00:00.000Z", end: "2026-08-06T08:00:00.000Z", asset_id: "BR-2001", asset_name: null },
  ],
};
const DETAIL: BatchDetail = {
  time_zone: "UTC",
  batch: { batch_id: "BL-0002", product: "mAb-X (synthetic)", is_reference: false, created_at: "2026-07-22T06:00:00.000Z", provenance: "synthetic-generator/1 seed=102" },
  phases: [
    { phase_id: "BL-0002-P1", batch_id: "BL-0002", kind: "production_culture", asset_id: "BR-2001", start: "2026-07-22T06:00:00.000Z", end: "2026-08-05T12:00:00.000Z", provenance: "p", asset_name: null },
    { phase_id: "BL-0002-P3", batch_id: "BL-0002", kind: "protein_a_capture", asset_id: "CH-3001", start: "2026-08-05T22:00:00.000Z", end: "2026-08-06T08:00:00.000Z", provenance: "p", asset_name: "Protein A chromatography skid" },
  ],
  pools: [
    { measurement_id: "BL-0002-protein_a_load", batch_id: "BL-0002", phase_id: "BL-0002-P3", pool: "protein_a_load", volume: 1915.3, volume_unit: "L", concentration: 5.42, concentration_unit: "g/L", method: "UV absorbance at 280 nm", measured_at: "2026-08-05T21:00:00.000Z", result_available_at: "2026-08-06T00:10:00.000Z", provenance: "p" },
  ],
};
const metric = (name: string, more: Partial<Metrics["metrics"][number]>) => ({ metric: name, value: null, unit: "g", status: "usable", reasons: [], inputs: [], calculation_version: `${name}/1`, reference: null, difference: null, ...more });
const METRICS: Metrics = {
  batch_id: "BL-0002", as_of: null, reference_batch_id: "BL-0001",
  findings: [{
    finding: "titer_divergence",
    observation: {
      metric: "titer_divergence", value: 7.9047, unit: "days", status: "usable", inputs: ["BL-0002-S09-titer", "BL-0001-S09-titer"], calculation_version: "titer_divergence/1",
      reasons: [{ code: "diverged_from_reference", values: { result_id: "BL-0002-S09-titer", reference_result_id: "BL-0001-S09-titer", collected_at: "2026-07-30T03:42:44Z", titer: 1.68, reference_titer: 2.01, deficit_percent: 16.2786, tolerance_percent: 15, later_samples_below: 6 } }],
    },
    consequence: { metric: "harvest_mass", unit: "g", status: "usable", value: 7317.46, reference: 10174.47, difference: -2857.01 },
    cause: null,
  }],
  metrics: [
    metric("qp", { value: 31.2449, unit: "pg/cell/day", inputs: ["BL-0002-S01-vcd", "BL-0002-S15-titer"], reference: { value: 29.6213, status: "usable" }, difference: 1.6236 }),
    metric("harvest_mass", { status: "insufficient", reasons: [{ code: "asset_not_found", values: { asset_id: "BR-2001" } }], reference: { value: 10174.4736, status: "usable" } }),
    metric("protein_a_recovery", { value: 106.3596, unit: "%", status: "suspect", reasons: [{ code: "above_plausibility_bound", values: { bound_percent: 105 } }], reference: { value: 93.5512, status: "usable" }, difference: 12.8084 }),
  ],
};
const SAMPLES: Samples = {
  batch_id: "BL-0002", as_of: null,
  samples: [1, 2].map((day) => ({
    sample_id: `BL-0002-S0${day}`, batch_id: "BL-0002", phase_id: "BL-0002-P1", collected_at: `2026-07-2${day + 2}T07:00:00.000Z`, provenance: "p",
    results: [
      { result_id: `BL-0002-S0${day}-titer`, sample_id: `BL-0002-S0${day}`, analyte: "titer", value: 0.021 * day, unit: "g/L", method: "Protein A HPLC", result_available_at: `2026-07-2${day + 3}T05:00:00.000Z`, validity: "valid", provenance: "p" },
      { result_id: `BL-0002-S0${day}-vcd`, sample_id: `BL-0002-S0${day}`, analyte: "vcd", value: 0.51 * day, unit: "1e6 cells/mL", method: "Automated cell counter", result_available_at: `2026-07-2${day + 2}T08:30:00.000Z`, validity: "valid", provenance: "p" },
    ],
  })),
};
const TRENDS: Trends = {
  batch_id: "BL-0002", as_of: null, asset_id: "BR-2001", start: "2026-07-22T06:00:00.000Z", end: "2026-08-05T12:00:00.000Z", step_seconds: 4140,
  signals: [
    { role: "ph", signal_id: "plantcraft:BIO.BR-2001.PH", name: "BR-2001 pH", unit: "pH", t: ["2026-07-22T06:00:00Z", "2026-07-22T07:09:00Z"], v: [7.01, 7.02], status: "usable", reasons: [] },
    { role: "volume", signal_id: null, name: null, unit: null, t: [], v: [], status: "insufficient", reasons: [{ code: "signal_not_found", values: { asset_id: "BR-2001", role: "volume" } }] },
  ],
};

beforeEach(() => { Object.assign(answers, { list: LIST, detail: DETAIL, metrics: METRICS, samples: SAMPLES, trends: TRENDS }); });

describe("the frame's pages", () => {
  it("Batches holds the list and each batch's page", () => {
    const [batches] = NAV;
    expect(NAV.map((item) => item.to)).toEqual(["/"]);
    for (const path of ["/", "/batches/BL-0001"]) expect(batches.match?.(path)).toBe(true);
    expect(batches.match?.("/help")).toBe(false);
  });

  it("every page says the data is synthetic and non-GxP", async () => {
    const host = await render(<DemoBanner />);
    expect(host.textContent).toBe("SYNTHETIC DEMO · NON-GxP · NOT FOR PROCESS CONTROL, RELEASE OR BATCH DISPOSITION");
  });
});

describe("the batch list", () => {
  it("lists each batch with its product, bioreactor, window and reference mark, linked to its page", async () => {
    const host = await render(<BatchesPage />);
    const rows = [...host.querySelectorAll("tbody tr")];
    expect(rows).toHaveLength(2);
    expect(rows[0].querySelector("a")?.getAttribute("href")).toBe("/batchlens/batches/BL-0001");
    expect(rows[0].textContent).toContain("mAb-X (synthetic)");
    expect(rows[0].textContent).toContain("Production bioreactor 2000 L");
    expect(rows[0].textContent).toContain("Reference");
    expect(rows[0].textContent).toContain("Jul 1, 2026, 6:00 AM UTC");
    expect(rows[0].textContent).toContain("Jul 16, 2026, 8:00 AM UTC");
    expect(rows[1].textContent).not.toContain("Reference");
    // The asset is not in PlantCraft: the id is shown, and the page says so.
    expect(rows[1].textContent).toContain("BR-2001");
    expect(rows[1].textContent).toContain("Not found in PlantCraft");
    expect(host.textContent).toContain("Times are shown in UTC");
  });

  it("says so when there are no batches", async () => {
    answers.list = { time_zone: "UTC", batches: [] };
    const host = await render(<BatchesPage />);
    expect(host.textContent).toContain("No batches yet");
  });
});

describe("one batch", () => {
  it("shows the phase executions on their assets", async () => {
    const host = await render(<BatchPage batchId="BL-0002" />);
    const phases = host.querySelector('[data-section="phases"]')!;
    expect(phases.textContent).toContain("Production culture");
    expect(phases.textContent).toContain("Protein A capture");
    expect(phases.textContent).toContain("Protein A chromatography skid");
    expect(phases.textContent).toContain("Not found in PlantCraft");
  });

  it("shows each metric with value, unit, status and reasons, beside the reference and the difference", async () => {
    const host = await render(<BatchPage batchId="BL-0002" />);
    const rows = [...host.querySelectorAll('[data-section="metrics"] tbody tr')].map((row) => row.textContent ?? "");
    expect(rows).toHaveLength(3);
    // Rounded for display to three significant digits, like the reference and the difference.
    expect(rows[0]).toContain("Specific productivity (qP)");
    expect(rows[0]).toContain("31.2 pg/cell/day");
    expect(rows[0]).toContain("Usable");
    expect(rows[0]).toContain("29.6");
    expect(rows[0]).toContain("+1.6");
    expect(rows[0]).toContain("BL-0002-S15-titer");
    expect(rows[1]).toContain("Insufficient");
    expect(rows[1]).toContain("Asset BR-2001 was not found in PlantCraft.");
    expect(rows[1]).toContain("10,170");
    expect(rows[2]).toContain("106 %");
    expect(rows[2]).toContain("Suspect");
    expect(rows[2]).toContain("Above the plausibility bound of 105 %.");
    expect(host.textContent).toContain("Reference batch: BL-0001");
  });

  it("states a finding as an observation and a calculation, and attributes no cause", async () => {
    const host = await render(<BatchPage batchId="BL-0002" />);
    const findings = host.querySelector('[data-section="findings"]')!.textContent ?? "";
    // The observation: where, how far below, against which samples.
    expect(findings).toContain("Titer left the reference batch at culture day 7.9");
    expect(findings).toContain("1.68 g/L against 2.01 g/L (16 % below; the tolerance is 15 %)");
    expect(findings).toContain("all 6 later samples");
    expect(findings).toContain("BL-0002-S09-titer");
    expect(findings).toContain("BL-0001-S09-titer");
    expect(findings).toContain("Jul 30, 2026, 3:42 AM UTC");
    // The calculation, rounded like the metrics table.
    expect(findings).toContain("Calculated: Product mass at harvest: 7,317 g against 10,170 g for the reference (-2,860 g).");
    // No diagnosis.
    expect(findings).toContain("No cause is attributed");
  });

  it("says so when the titer followed the reference, or when it cannot be compared", async () => {
    const quiet = { ...METRICS.findings[0], consequence: null, observation: { ...METRICS.findings[0].observation, value: null, reasons: [{ code: "no_divergence", values: { pairs: 15, tolerance_percent: 15 } }] } };
    answers.metrics = { ...METRICS, findings: [quiet] };
    let host = await render(<BatchPage batchId="BL-0002" />);
    expect(host.querySelector('[data-section="findings"]')!.textContent).toContain("Titer stayed within 15 % of the reference batch at the end of 15 compared samples.");
    const short = { ...quiet, observation: { ...quiet.observation, status: "insufficient", reasons: [{ code: "fewer_than_two_reference_pairs", values: { pairs: 1 } }] } };
    answers.metrics = { ...METRICS, findings: [short] };
    host = await render(<BatchPage batchId="BL-0002" />);
    expect(host.querySelector('[data-section="findings"]')!.textContent).toContain("Fewer than two titer samples could be compared with the reference batch.");
    // The reference batch has nothing to be compared with: no section at all.
    answers.metrics = { ...METRICS, findings: [] };
    host = await render(<BatchPage batchId="BL-0002" />);
    expect(host.querySelector('[data-section="findings"]')).toBeNull();
  });

  it("lists every assay result with its collection and availability times", async () => {
    const host = await render(<BatchPage batchId="BL-0002" />);
    const rows = [...host.querySelectorAll('[data-section="results"] tbody tr')].map((row) => row.textContent ?? "");
    expect(rows).toHaveLength(4);
    expect(rows.join()).toContain("Viable cell density");
    expect(rows.join()).toContain("Protein A HPLC");
    const titer = rows.find((row) => row.includes("BL-0002-S01") && row.includes("Titer"))!;
    expect(titer).toContain("0.021 g/L");
    expect(titer).toContain("Jul 23, 2026, 7:00 AM UTC");
    expect(titer).toContain("Jul 24, 2026, 5:00 AM UTC");
    expect(host.querySelector('[data-section="pools"]')?.textContent).toContain("1,915.3 L");
  });

  it("draws the online signals and the VCD and titer trends, and says why one is missing", async () => {
    const host = await render(<BatchPage batchId="BL-0002" />);
    const charts = [...host.querySelectorAll("[data-chart]")].map((chart) => chart.getAttribute("data-chart"));
    expect(charts).toEqual(["pH:2", "Viable cell density:2", "Titer:2"]);
    const trends = host.querySelector('[data-section="trends"]')!;
    expect(trends.textContent).toContain("BR-2001 has no volume signal in PlantCraft.");
  });

  it("shows the server's words when the batch does not exist", async () => {
    answers.detail = Promise.reject(new Error("Batch not found."));
    const host = await render(<BatchPage batchId="BL-9999" />);
    expect(host.textContent).toContain("Batch not found.");
  });
});
