/** `batches/<id>`: one batch. Its phase executions, its metrics beside the reference batch, its
 * pool measurements, the trends of the bioreactor's signals and of VCD and titer, and every
 * assay result with both of its times. The page shows what the server computed; no formula
 * lives here. */
import { lazy, Suspense, useEffect, useState } from "react";
import { DataTable, Pill } from "@plantcraft/ui";
import { api } from "./api";
import { recorded, signedBetween, significant } from "./format";
import { t } from "./i18n";
import type { BatchDetail, Finding, Metric, Metrics, Samples, Trends } from "./types";
import { ErrorBox, Heading, Loading, message } from "./ui";
import { NotInPlantCraft, useInstallationZone, when, ZoneNote } from "./when";
import { analyteName, metricDigits, metricName, phaseName, poolName, reasonText, roleName, statusTone, statusWord } from "./words";

// Plotly is loaded only when a chart is drawn (@plantcraft/ui/plot).
const TimeChart = lazy(() => import("@plantcraft/ui/plot").then((module) => ({ default: module.TimeChart })));

interface Loaded { detail: BatchDetail; metrics: Metrics; samples: Samples; trends: Trends }

function Section({ id, title, detail, children }: { id: string; title: string; detail?: string; children: React.ReactNode }) {
  return <section data-section={id}>
    <div className="panel-header"><div><h2>{title}</h2>{detail && <p>{detail}</p>}</div></div>
    {children}
  </section>;
}

function Phases({ detail }: { detail: BatchDetail }) {
  return <DataTable rows={detail.phases} rowKey={(phase) => phase.phase_id} label={t("Phase executions")}
    columns={[
      { key: "phase", label: t("Phase"), render: (phase) => phaseName(phase.kind) },
      { key: "asset", label: t("Asset"), render: (phase) => phase.asset_name ?? <>{phase.asset_id}<NotInPlantCraft /></> },
      { key: "start", label: t("Start"), render: (phase) => when(phase.start) },
      { key: "end", label: t("End"), render: (phase) => when(phase.end) },
    ]} />;
}

function MetricValue({ metric }: { metric: Metric }) {
  if (metric.value === null) return <span className="muted">{t("No value")}</span>;
  return <>{significant(metric.value, metricDigits(metric.metric))} {metric.unit}</>;
}

function MetricsTable({ metrics }: { metrics: Metrics }) {
  return <DataTable rows={metrics.metrics} rowKey={(metric) => metric.metric} label={t("Metrics")}
    columns={[
      { key: "metric", label: t("Metric"), render: (metric) => <>{metricName(metric.metric)}<small>{metric.calculation_version}</small></> },
      { key: "value", label: t("Value"), numeric: true, render: (metric) => <MetricValue metric={metric} /> },
      { key: "status", label: t("Status"), render: (metric) => <Pill status={statusTone(metric.status)} label={statusWord(metric.status)} /> },
      { key: "why", label: t("Reasons and inputs"), render: (metric) => <>
        {metric.reasons.map((reason, index) => <div key={index}>{reasonText(reason)}</div>)}
        {metric.inputs.length > 0 && <small title={metric.inputs.join(", ")}>{t("Inputs: {inputs}", { inputs: metric.inputs.join(", ") })}</small>}
      </> },
      { key: "reference", label: t("Reference"), numeric: true, phone: "hide",
        render: (metric) => (metric.reference ? significant(metric.reference.value, metricDigits(metric.metric)) || statusWord(metric.reference.status) : "") },
      { key: "difference", label: t("Difference"), numeric: true, phone: "hide",
        render: (metric) => signedBetween(metric.difference, metric.value, metric.reference?.value, metricDigits(metric.metric)) },
    ]} />;
}

/** One finding: the observation, then the calculation, then the line that no cause is given. */
function FindingPanel({ finding }: { finding: Finding }) {
  const { observation, consequence } = finding;
  const seen = observation.reasons.find((reason) => reason.code === "diverged_from_reference");
  const others = observation.reasons.filter((reason) => reason !== seen);
  const v = seen?.values ?? {};
  const digits = metricDigits("harvest_mass");
  return <div className="panel">
    {seen && <>
      <h3>{t("Titer left the reference batch at culture day {day}", { day: Number(observation.value).toFixed(1) })}</h3>
      <p>{t("Observed: sample {sample}, collected {when}, read {titer} g/L against {reference} g/L ({deficit} % below; the tolerance is {tolerance} %) for the reference sample {referenceSample} of the same culture age, and all {later} later samples stayed below.", {
        sample: String(v.result_id), when: when(String(v.collected_at)), titer: recorded(Number(v.titer)), reference: recorded(Number(v.reference_titer)),
        deficit: Number(v.deficit_percent).toFixed(0), tolerance: String(v.tolerance_percent), referenceSample: String(v.reference_result_id), later: String(v.later_samples_below),
      })}</p>
      {consequence && (consequence.difference !== null
        ? <p>{t("Calculated: {metric}: {value} {unit} against {reference} {unit} for the reference ({difference} {unit}).", {
            metric: metricName(consequence.metric), unit: consequence.unit, value: significant(consequence.value, digits), reference: significant(consequence.reference, digits),
            difference: signedBetween(consequence.difference, consequence.value, consequence.reference, digits),
          })}</p>
        : <p>{t("Calculated: {metric} cannot be compared with the reference ({status}).", { metric: metricName(consequence.metric), status: statusWord(consequence.status) })}</p>)}
      <p className="muted">{t("No cause is attributed: this is an observation and a calculation, not a diagnosis. The first sample at which a gap is seen comes after whatever began it.")}</p>
    </>}
    {others.map((reason, index) => <p key={index}>{reasonText(reason)}</p>)}
  </div>;
}

function Pools({ detail }: { detail: BatchDetail }) {
  return <DataTable rows={detail.pools} rowKey={(pool) => pool.measurement_id} label={t("Pool measurements")}
    empty={t("No pool measurement recorded.")}
    columns={[
      { key: "pool", label: t("Pool"), render: (pool) => <>{poolName(pool.pool)}<small>{pool.measurement_id}</small></> },
      { key: "volume", label: t("Volume"), numeric: true, render: (pool) => `${recorded(pool.volume)} ${pool.volume_unit}` },
      { key: "concentration", label: t("Concentration"), numeric: true, render: (pool) => `${recorded(pool.concentration)} ${pool.concentration_unit}` },
      { key: "method", label: t("Method"), phone: "hide", render: (pool) => pool.method },
      { key: "measured", label: t("Measured"), render: (pool) => when(pool.measured_at) },
      { key: "available", label: t("Result available"), render: (pool) => when(pool.result_available_at) },
    ]} />;
}

function TrendCharts({ trends, samples }: { trends: Trends; samples: Samples }) {
  const range = { start: trends.start ?? undefined, end: trends.end ?? undefined };
  const offline = ["vcd", "titer"].map((analyte) => {
    const results = samples.samples.flatMap((sample) => sample.results.filter((result) => result.analyte === analyte).map((result) => ({ at: sample.collected_at, result })));
    return { analyte, unit: results[0]?.result.unit, t: results.map((item) => item.at), v: results.map((item) => item.result.value) };
  });
  return <Suspense fallback={<Loading />}>
    {trends.signals.map((signal) => <div className="panel" key={signal.role}>
      <h3>{roleName(signal.role)}{signal.name && <small className="muted"> {signal.name}</small>}</h3>
      {signal.status === "usable" && signal.t.length > 0
        ? <TimeChart lines={[{ name: roleName(signal.role), t: signal.t, v: signal.v, unit: signal.unit ?? undefined }]} height={200} filename={`${trends.batch_id}-${signal.role}`} {...range} />
        : <p className="notice">{signal.reasons.map(reasonText).join(" ") || t("No values in the production phase.")}</p>}
    </div>)}
    {offline.map((line) => <div className="panel" key={line.analyte}>
      <h3>{analyteName(line.analyte)}<small className="muted"> {t("offline samples, at their collection times")}</small></h3>
      {line.t.length > 0
        ? <TimeChart lines={[{ name: analyteName(line.analyte), t: line.t, v: line.v, unit: line.unit }]} height={200} filename={`${trends.batch_id}-${line.analyte}`} {...range} />
        : <p className="notice">{t("No results yet.")}</p>}
    </div>)}
  </Suspense>;
}

function Results({ samples }: { samples: Samples }) {
  const rows = samples.samples.flatMap((sample) => sample.results.map((result) => ({ ...result, collected_at: sample.collected_at })));
  return <DataTable rows={rows} rowKey={(row) => row.result_id} label={t("Assay results")}
    empty={t("No results yet.")} initialSort={{ key: "collected", descending: false }}
    columns={[
      { key: "sample", label: t("Sample"), sort: (row) => row.sample_id, render: (row) => row.sample_id },
      { key: "analyte", label: t("Analyte"), sort: (row) => analyteName(row.analyte), filter: { value: (row) => analyteName(row.analyte) }, render: (row) => analyteName(row.analyte) },
      { key: "value", label: t("Value"), numeric: true, render: (row) => `${recorded(row.value)} ${row.unit}` },
      { key: "method", label: t("Method"), phone: "hide", render: (row) => row.method },
      { key: "collected", label: t("Collected"), sort: (row) => row.collected_at, render: (row) => when(row.collected_at) },
      { key: "available", label: t("Result available"), sort: (row) => row.result_available_at, render: (row) => when(row.result_available_at) },
    ]} />;
}

export function BatchPage({ batchId }: { batchId: string }) {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api.batch(batchId), api.metrics(batchId), api.samples(batchId), api.trends(batchId)])
      .then(([detail, metrics, samples, trends]) => setLoaded({ detail, metrics, samples, trends }))
      .catch((err) => setError(message(err)));
  }, [batchId]);
  useInstallationZone(loaded?.detail.time_zone);
  if (error) return <ErrorBox text={error} />;
  if (!loaded) return <Loading />;
  const { detail, metrics, samples, trends } = loaded;
  const reference = detail.batch.is_reference
    ? t("This is the reference batch.")
    : metrics.reference_batch_id ? t("Reference batch: {batch}", { batch: metrics.reference_batch_id }) : t("No reference batch is set.");
  return <>
    <Heading title={t("Batch {batch}", { batch: detail.batch.batch_id })} />
    <p className="muted">{detail.batch.product} · {reference} · {detail.batch.provenance}</p>
    <ZoneNote />
    <Section id="phases" title={t("Phase executions")} detail={t("What happened on which asset, and when.")}><Phases detail={detail} /></Section>
    {metrics.findings.length > 0 && <Section id="findings" title={t("Findings")} detail={t("This batch against the reference batch. Tolerances are illustrative settings, not limits.")}>
      {metrics.findings.map((finding) => <FindingPanel key={finding.finding} finding={finding} />)}
    </Section>}
    <Section id="metrics" title={t("Metrics")} detail={t("Computed on request from the records below and PlantCraft's signals. Masses are estimates from concentration × volume.")}><MetricsTable metrics={metrics} /></Section>
    <Section id="pools" title={t("Pool measurements")}><Pools detail={detail} /></Section>
    <Section id="trends" title={t("Trends")} detail={t("The bioreactor's online signals over the production phase, read from PlantCraft, and the offline VCD and titer.")}><TrendCharts trends={trends} samples={samples} /></Section>
    <Section id="results" title={t("Assay results")} detail={t("Each result has two times: when its sample was collected, and when the result became available.")}><Results samples={samples} /></Section>
  </>;
}
