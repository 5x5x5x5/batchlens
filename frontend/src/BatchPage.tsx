/** `batches/<id>`: one batch. Its phase executions, its metrics beside the reference batch, its
 * pool measurements, the trends of the bioreactor's signals and of VCD and titer, and every
 * assay result with both of its times. The page shows what the server computed; no formula
 * lives here. */
import { lazy, Suspense, useEffect, useState } from "react";
import { confirmAction, DataTable, isoOf, localOf, Pill } from "@plantcraft/ui";
import { api } from "./api";
import { ProcessTrain } from "./ProcessTrain";
import { recorded, signedBetween, signedRecorded, significant } from "./format";
import { t } from "./i18n";
import type { BatchDetail, Downstream, Evidence, Finding, Me, Metric, Metrics, Result, Sample, Samples, Transfer, Trends } from "./types";
import { ErrorBox, Heading, Link, Loading, message } from "./ui";
import { NotInPlantCraft, useInstallationZone, when, ZoneNote } from "./when";
import { analyteName, metricDigits, metricName, batchKindName, phaseName, poolName, reasonText, roleName, statusTone, statusWord, transferName } from "./words";

// Plotly is loaded only when a chart is drawn (@plantcraft/ui/plot).
const TimeChart = lazy(() => import("@plantcraft/ui/plot").then((module) => ({ default: module.TimeChart })));

/** A solution lot has no metrics or trends: only its phases, samples and results are read. */
interface Loaded { detail: BatchDetail; metrics: Metrics | null; samples: Samples; trends: Trends | null; reference: Samples | null }

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
      { key: "end", label: t("End"), render: (phase) => (phase.end ? when(phase.end) : <span className="muted">{t("In progress")}</span>) },
    ]} />;
}

function MetricValue({ metric }: { metric: Metric }) {
  if (metric.value === null) return <span className="muted">{t("No value")}</span>;
  return <>{significant(metric.value, metricDigits(metric.metric))} {metric.unit}</>;
}

/** The comparable batches' median of a metric and the range one more batch like them is
 * expected in (a prediction interval, wider the fewer they are), with a word when the value
 * lies outside it. An observation: the interval is not a limit. */
function Among({ result, digits }: { result?: Result | null; digits: number }) {
  if (!result) return null;
  const reason = result.reasons.find((item) => item.code.endsWith("_expected_range"));
  if (!reason) return <span className="muted">{result.reasons.map(reasonText).join(" ")}</span>;
  const seen = reason.values;
  const outside = reason.code.startsWith("below") ? t("Below") : reason.code.startsWith("above") ? t("Above") : "";
  return <>{significant(Number(seen.median), digits)}{outside && <> <Pill status="suspect" label={outside} /></>}
    <small>{t("expected {low} to {high} ({level} %, {count} batches)", { low: significant(Number(seen.expected_low), digits), high: significant(Number(seen.expected_high), digits), level: String(seen.level_percent), count: String(seen.count) })}</small></>;
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
      { key: "comparable", label: t("Comparable batches"), numeric: true, phone: "hide", render: (metric) => <Among result={metric.comparable} digits={metricDigits(metric.metric)} /> },
    ]} />;
}

const NO_CAUSE = () => t("No cause is attributed: this is an observation and a calculation, not a diagnosis.");

/** The product mass a finding amounts to, against the reference batch's. */
function Consequence({ consequence }: { consequence: Finding["consequence"] }) {
  if (!consequence) return null;
  const digits = metricDigits(consequence.metric);
  if (consequence.difference === null) return <p>{t("Calculated: {metric} cannot be compared with the reference ({status}).", { metric: metricName(consequence.metric), status: statusWord(consequence.status) })}</p>;
  return <p>{t("Calculated: {metric}: {value} {unit} against {reference} {unit} for the reference ({difference} {unit}).", {
    metric: metricName(consequence.metric), unit: consequence.unit, value: significant(consequence.value, digits), reference: significant(consequence.reference, digits),
    difference: signedBetween(consequence.difference, consequence.value, consequence.reference, digits),
  })}</p>;
}

/** The other results of the samples a divergence rests on, beside the reference batch's. */
function EvidenceTables({ evidence }: { evidence: Evidence[] }) {
  if (evidence.length === 0) return null;
  return <>
    <p className="muted">{t("Other results of the same samples, beside the reference batch's. Nothing is concluded from them.")}</p>
    {evidence.map((group) => <div key={group.at}>
      <h4>{group.at === "buffer_lot"
        ? t("{solution}: lot {lot} against the reference batch's lot {reference} ({days} and {referenceDays} days old when drawn)", { solution: group.solution ?? "", lot: group.lot_id ?? "", reference: group.reference_lot_id ?? "", days: (group.age_days ?? 0).toFixed(1), referenceDays: (group.reference_age_days ?? 0).toFixed(1) })
        : group.at === "seed_n1_end"
        ? t("At the end of the N-1 seed passage: {sample} against {reference} (day {day} of the passage)", { sample: group.sample_id, reference: group.reference_sample_id, day: group.culture_day.toFixed(1) })
        : group.at === "divergence"
        ? t("At the divergence: {sample} against {reference} (culture day {day})", { sample: group.sample_id, reference: group.reference_sample_id, day: group.culture_day.toFixed(1) })
        : t("At the last compared sample: {sample} against {reference} (culture day {day})", { sample: group.sample_id, reference: group.reference_sample_id, day: group.culture_day.toFixed(1) })}</h4>
      {group.hours_since_feed != null && group.reference_hours_since_feed != null && <p className="muted">{t("Collected {hours} h after a feed; the reference sample {reference} h after one. Glucose and lactate move with every feed.", { hours: group.hours_since_feed.toFixed(0), reference: group.reference_hours_since_feed.toFixed(0) })}</p>}
      <DataTable rows={group.results} rowKey={(row) => row.result_id} label={t("Evidence")}
        columns={[
          { key: "analyte", label: t("Analyte"), render: (row) => analyteName(row.analyte) },
          { key: "value", label: t("This batch"), numeric: true, render: (row) => `${recorded(row.value)} ${row.unit}` },
          { key: "reference", label: t("Reference"), numeric: true, render: (row) => (row.reference_value === null ? <span className="muted">{t("No value")}</span> : `${recorded(row.reference_value)} ${row.unit}`) },
          { key: "difference", label: t("Difference"), numeric: true, render: (row) => signedRecorded(row.difference) },
          ...(group.results.some((row) => row.comparable) ? [{ key: "comparable", label: t("Comparable batches' lots"), numeric: true, phone: "hide" as const, render: (row: Evidence["results"][number]) => <Among result={row.comparable} digits={3} /> }] : []),
        ]} />
    </div>)}
  </>;
}

/** Compared, and nothing beyond the tolerance: listed together, after what was found. */
const isQuiet = (finding: Finding) => finding.observation.status === "usable" && finding.observation.value === null;

/** One finding: the observation, then the calculation, then the line that no cause is given. */
function FindingPanel({ finding }: { finding: Finding }) {
  const { observation, consequence } = finding;
  const diverged = observation.reasons.find((reason) => reason.code === "diverged_from_reference");
  const short = observation.reasons.find((reason) => reason.code === "below_reference");
  const low = observation.reasons.find((reason) => reason.code === "inoculated_below_reference");
  const others = observation.reasons.filter((reason) => reason !== diverged && reason !== short && reason !== low);
  const v = (diverged ?? short ?? low)?.values ?? {};
  return <div className="panel">
    {diverged && <>
      <h3>{t("Titer left the reference batch at culture day {day}", { day: Number(observation.value).toFixed(1) })}</h3>
      {(() => {
        const values = {
          sample: String(v.result_id), when: when(String(v.collected_at)), titer: recorded(Number(v.titer)), reference: recorded(Number(v.reference_titer)),
          deficit: Number(v.deficit_percent).toFixed(0), tolerance: String(v.tolerance_percent), referenceSample: String(v.reference_result_id), later: String(v.later_samples_below),
        };
        return <p>{Number(v.later_samples_below) > 0
          ? t("Observed: sample {sample}, collected {when}, read {titer} g/L against {reference} g/L ({deficit} % below; the tolerance is {tolerance} %) for the reference sample {referenceSample} of the same culture age, and all {later} later samples stayed below.", values)
          : t("Observed: sample {sample}, collected {when}, read {titer} g/L against {reference} g/L ({deficit} % below; the tolerance is {tolerance} %) for the reference sample {referenceSample} of the same culture age, and no later sample has a result yet.", values)}</p>;
      })()}
      <Consequence consequence={consequence} />
      <p className="muted">{NO_CAUSE()} {t("The first sample at which a gap is seen comes after whatever began it.")}</p>
    </>}
    {short && <>
      <h3>{t("{metric} is {points} points below the reference batch", { metric: metricName(String(v.metric)), points: Number(observation.value).toFixed(0) })}</h3>
      <p>{t("Observed: {value} % against {reference} % for the reference (the tolerance is {tolerance} points).", { value: Number(v.value).toFixed(1), reference: Number(v.reference_value).toFixed(1), tolerance: String(v.tolerance_points) })}</p>
      <Consequence consequence={consequence} />
      <p className="muted">{NO_CAUSE()}</p>
    </>}
    {low && <>
      <h3>{t("The culture began {deficit} % below the reference batch's density", { deficit: Number(observation.value).toFixed(0) })}</h3>
      <p>{t("Observed: the first cell count read {value} against {reference} 1e6 cells/mL for the reference (the tolerance is {tolerance} %).", { value: recorded(Number(v.value)), reference: recorded(Number(v.reference_value)), tolerance: String(v.tolerance_percent) })}</p>
      <Consequence consequence={consequence} />
      <p className="muted">{NO_CAUSE()}</p>
    </>}
    {observation.status !== "usable" && observation.value === null && <h3>{finding.finding === "titer_divergence"
      ? t("The titer could not be compared with the reference batch ({status})", { status: statusWord(observation.status) })
      : t("{metric} could not be compared with the reference batch ({status})", { metric: metricName(observation.metric.replace(/_shortfall$/, "")), status: statusWord(observation.status) })}</h3>}
    {others.map((reason, index) => <p key={index}>{reasonText(reason)}</p>)}
    <EvidenceTables evidence={finding.evidence} />
  </div>;
}

/** A mass or a percentage of the train, or why there is none. */
function Amount({ result, digits = 3 }: { result: Result; digits?: number }) {
  if (result.value === null) return <span className="muted">{result.reasons.map(reasonText).join(" ") || t("No value")}</span>;
  return <>{significant(result.value, digits)} {result.unit}{result.status === "suspect" && <small>{result.reasons.map(reasonText).join(" ")}</small>}</>;
}

/** A mass balance in percent (a merge's or a split's), flagged with its reason when suspect. */
function Balance({ result }: { result?: Result | null }) {
  if (!result) return null;
  if (result.value === null) return <Amount result={result} />;
  return <>{result.value.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: "exceptZero" })} %{result.status === "suspect" && <small>{result.reasons.map(reasonText).join(" ")}</small>}</>;
}

/** The purification train, step by step, and what each pool was made from. */
function DownstreamSection({ train }: { train: Downstream }) {
  return <>
    <DataTable rows={train.steps} rowKey={(row) => row.step} label={t("Downstream recovery")}
      columns={[
        { key: "step", label: t("Step"), render: (row) => phaseName(row.step) },
        { key: "in", label: t("Mass in"), numeric: true, render: (row) => <Amount result={row.mass_in} /> },
        { key: "out", label: t("Mass out"), numeric: true, render: (row) => <Amount result={row.mass_out} /> },
        { key: "yield", label: t("Step yield"), numeric: true, render: (row) => <Amount result={row.step_yield} /> },
        { key: "reference", label: t("Reference"), numeric: true, phone: "hide", render: (row) => significant(row.reference_yield, 3) },
        { key: "difference", label: t("Difference"), numeric: true, phone: "hide", render: (row) => signedBetween(row.yield_difference, row.step_yield.value, row.reference_yield, 3) },
        { key: "harvest", label: t("Left of the harvest"), numeric: true, render: (row) => <Amount result={row.from_harvest} /> },
      ]} />
    <p>{train.overall.value === null
      ? t("From harvest to drug substance: no value. {why}", { why: train.overall.reasons.map(reasonText).join(" ") })
      : train.overall_reference === null
        ? t("From harvest to drug substance: {value} %.", { value: significant(train.overall.value, 3) })
        : t("From harvest to drug substance: {value} % (reference batch: {reference} %).", { value: significant(train.overall.value, 3), reference: significant(train.overall_reference, 3) })}</p>
    <DataTable rows={train.genealogy} rowKey={(node) => node.measurement_id} label={t("Pool genealogy")}
      empty={t("No pool measurement recorded.")}
      columns={[
        { key: "pool", label: t("Pool"), render: (node) => <>{poolName(node.pool)}<small>{node.measurement_id}</small></> },
        { key: "mass", label: t("Mass"), numeric: true, render: (node) => <Amount result={node.mass} /> },
        { key: "sources", label: t("Made from"), render: (node) => node.sources.join(", ") },
        { key: "balance", label: t("Merge balance"), numeric: true, render: (node) => <Balance result={node.merge_balance} /> },
        { key: "split", label: t("Split balance"), numeric: true, render: (node) => <Balance result={node.split_balance} /> },
      ]} />
  </>;
}

/** What was moved into which vessel, and whether the vessel's volume signal agrees. */
function Transfers({ transfers }: { transfers: Transfer[] }) {
  return <DataTable rows={transfers} rowKey={(transfer) => transfer.transfer_id} label={t("Transfers")}
    empty={t("No transfer recorded.")}
    columns={[
      { key: "transfer", label: t("Transfer"), render: (transfer) => <>{transferName(transfer.kind)}<small>{transfer.transfer_id}</small></> },
      { key: "from", label: t("From"), render: (transfer) => transfer.from_asset_id },
      { key: "to", label: t("To"), render: (transfer) => transfer.to_asset_id },
      { key: "lot", label: t("Lot"), phone: "hide", render: (transfer) => (transfer.from_lot_id
        ? <><Link to={`/batches/${encodeURIComponent(transfer.from_lot_id)}`}>{transfer.from_lot_id}</Link><small>{transfer.lot_solution ?? ""}{transfer.lot_age_days != null && ` · ${t("{days} days old", { days: transfer.lot_age_days.toFixed(1) })}`}</small></>
        : "") },
      { key: "end", label: t("Ended"), render: (transfer) => (transfer.end ? when(transfer.end) : <span className="muted">{t("In progress")}</span>) },
      { key: "volume", label: t("Recorded volume"), numeric: true, render: (transfer) => (transfer.volume === null ? "" : `${recorded(transfer.volume)} ${transfer.volume_unit}`) },
      { key: "balance", label: t("Vessels, against the record"), numeric: true, render: (transfer) => (transfer.balance.value === null ? <span className="muted">{t("Not checked")}</span>
        : `${transfer.balance.value.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: "exceptZero" })} %`) },
      { key: "status", label: t("Status"), render: (transfer) => <Pill status={statusTone(transfer.balance.status)} label={statusWord(transfer.balance.status)} /> },
      { key: "why", label: t("Reasons"), phone: "hide", render: (transfer) => transfer.balance.reasons.filter((reason) => reason.code !== "transfer_balanced").map((reason, index) => <div key={index}>{reasonText(reason)}</div>) },
    ]} />;
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

function TrendCharts({ trends, samples, reference }: { trends: Trends; samples: Samples; reference: Samples | null }) {
  const range = { start: trends.start ?? undefined, end: trends.end ?? undefined };
  const offline = ["vcd", "titer"].map((analyte) => {
    // The production culture's samples only: the seed passages are not on the bioreactor's timeline.
    const results = samples.samples.filter((sample) => sample.phase_kind === "production_culture").flatMap((sample) => sample.results.filter((result) => result.analyte === analyte).map((result) => ({ at: sample.collected_at, result })));
    // The reference batch at the same culture age: the server placed its samples on this batch's timeline.
    const beside = (reference?.samples ?? []).filter((sample) => sample.phase_kind === "production_culture").flatMap((sample) => sample.results.filter((result) => result.analyte === analyte && sample.aligned_at).map((result) => ({ at: sample.aligned_at as string, result })));
    const lines = [{ name: analyteName(analyte), t: results.map((item) => item.at), v: results.map((item) => item.result.value), unit: results[0]?.result.unit }];
    if (reference && beside.length > 0) lines.push({ name: t("Reference batch {batch}, same culture age", { batch: reference.batch_id }), t: beside.map((item) => item.at), v: beside.map((item) => item.result.value), unit: beside[0].result.unit });
    return { analyte, lines };
  });
  return <Suspense fallback={<Loading />}>
    {trends.signals.map((signal) => <div className="panel" key={signal.role}>
      <h3>{roleName(signal.role)}{signal.name && <small className="muted"> {signal.name}</small>}</h3>
      {signal.status === "usable" && signal.t.length > 0
        ? <TimeChart lines={[{ name: roleName(signal.role), t: signal.t, v: signal.v, unit: signal.unit ?? undefined }]} height={200} filename={`${trends.batch_id}-${signal.role}`} {...range} />
        : <p className="notice">{signal.reasons.map(reasonText).join(" ") || t("No values in the production phase.")}</p>}
    </div>)}
    {offline.map((chart) => <div className="panel" key={chart.analyte}>
      <h3>{analyteName(chart.analyte)}<small className="muted"> {t("offline samples, at their collection times")}</small></h3>
      {chart.lines[0].t.length > 0
        ? <TimeChart lines={chart.lines} height={220} filename={`${trends.batch_id}-${chart.analyte}`} {...range} />
        : <p className="notice">{t("No results yet.")}</p>}
    </div>)}
  </Suspense>;
}

const AS_OF_STEP_MS = 6 * 3600 * 1000;

/** Move through the batch's history: everything below shows only what had been collected and
 * reported by the chosen instant. The server does the filtering (`as_of` on every route). */
function AsOfControl({ timeline, asOf, onChange }: { timeline: BatchDetail["timeline"]; asOf: string | null; onChange: (asOf: string | null) => void }) {
  if (!timeline.start || !timeline.end) return null;
  const start = Date.parse(timeline.start);
  const last = Math.ceil((Date.parse(timeline.end) - start) / AS_OF_STEP_MS);
  const position = asOf ? Math.round((Date.parse(asOf) - start) / AS_OF_STEP_MS) : last;
  const choose = (value: number) => onChange(value >= last ? null : new Date(start + value * AS_OF_STEP_MS).toISOString());
  return <div className="panel as-of">
    <label>{t("What was known when")}
      <input type="range" min={0} max={last} step={1} value={position} onChange={(event) => choose(Number(event.target.value))} />
    </label>
    <p className={asOf ? "notice" : "muted"}>
      {asOf ? t("Showing only what had been collected and reported by {when}. A result reported later is not used, even if its sample was taken before.", { when: when(asOf) }) : t("Showing everything recorded.")}
      {asOf && <> <button type="button" className="button button-small" data-action="show-everything" onClick={() => onChange(null)}>{t("Show everything")}</button></>}
    </p>
  </div>;
}

/** The samples with their collection times. An editor may correct a time that was recorded
 * wrongly: the value it replaces is kept and listed, and PlantCraft's audit log has the change. */
function SamplesSection({ batchId, samples, detail, canEdit, onChanged }: { batchId: string; samples: Samples; detail: BatchDetail; canEdit: boolean; onChanged: () => void }) {
  const [editing, setEditing] = useState<Sample | null>(null);
  const [time, setTime] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const open = (sample: Sample) => { setEditing(sample); setTime(localOf(sample.collected_at)); setReason(""); setError(""); };
  const save = () => editing && api.correctSample(batchId, editing.sample_id, { collected_at: isoOf(time), reason: reason.trim() })
    .then(() => { setEditing(null); onChanged(); })
    .catch((err) => setError(message(err)));
  return <>
    <DataTable rows={samples.samples} rowKey={(sample) => sample.sample_id} label={t("Samples")}
      empty={t("No samples yet.")}
      columns={[
        { key: "sample", label: t("Sample"), render: (sample) => sample.sample_id },
        { key: "collected", label: t("Collected"), render: (sample) => <>{when(sample.collected_at)}{sample.corrected && <small>{t("Corrected")}</small>}</> },
        { key: "phase", label: t("Phase"), render: (sample) => (sample.phase_kind ? phaseName(sample.phase_kind) : "") },
        { key: "day", label: t("Culture day"), numeric: true, render: (sample) => (sample.culture_day === null ? "" : sample.culture_day.toFixed(2)) },
        { key: "change", label: "", render: (sample) => (canEdit ? <button type="button" className="button button-small" data-action="correct-time" onClick={() => open(sample)}>{t("Correct the time")}</button> : "") },
      ]} />
    {editing && <form className="panel" onSubmit={(event) => { event.preventDefault(); void save(); }}>
      <h3>{t("Correct the collection time of {sample}", { sample: editing.sample_id })}</h3>
      <p className="muted">{t("The recorded value is kept beside the correction, and the change is written to PlantCraft's audit log with your name and reason.")}</p>
      <div className="form-grid">
        <label>{t("Collected")}<input type="datetime-local" value={time} onChange={(event) => setTime(event.target.value)} required /></label>
        <label className="form-wide">{t("Reason")}<textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={2} minLength={5} maxLength={500} required /></label>
      </div>
      {error && <ErrorBox text={error} />}
      <div className="form-actions">
        <button className="button button-primary" type="submit">{t("Save the correction")}</button>{" "}
        <button className="button" type="button" onClick={() => setEditing(null)}>{t("Cancel")}</button>
      </div>
    </form>}
    {detail.corrections.length > 0 && <DataTable rows={detail.corrections} rowKey={(item) => item.correction_id} label={t("Corrections")}
      columns={[
        { key: "record", label: t("Corrected record"), render: (item) => item.record_id },
        { key: "old", label: t("Recorded as"), render: (item) => when(item.old_value) },
        { key: "new", label: t("Corrected to"), render: (item) => when(item.new_value) },
        { key: "reason", label: t("Reason"), render: (item) => item.reason },
        { key: "by", label: t("By"), render: (item) => <>{item.corrected_by}<small>{when(item.corrected_at)}</small></> },
      ]} />}
  </>;
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

export function BatchPage({ batchId, me }: { batchId: string; me: Me }) {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [asOf, setAsOf] = useState<string | null>(null);
  const [version, setVersion] = useState(0); // bumped after a change, to read everything again
  const [error, setError] = useState("");
  useEffect(() => {
    const at = asOf ?? undefined;
    api.batch(batchId, at)
      .then(async (detail) => {
        if ((detail.batch.kind ?? "product") !== "product") {
          setLoaded({ detail, metrics: null, samples: await api.samples(batchId, at), trends: null, reference: null });
          return;
        }
        const [metrics, samples, trends] = await Promise.all([api.metrics(batchId, at), api.samples(batchId, at), api.trends(batchId, at)]);
        // The reference batch's samples, laid over this batch at the same culture age.
        const reference = metrics.reference_batch_id ? await api.samples(metrics.reference_batch_id, at, batchId) : null;
        setLoaded({ detail, metrics, samples, trends, reference });
      })
      .catch((err) => setError(message(err)));
  }, [batchId, asOf, version]);
  useInstallationZone(loaded?.detail.time_zone);
  if (error) return <ErrorBox text={error} />;
  if (!loaded) return <Loading />;
  const { detail, metrics, samples, trends, reference: beside } = loaded;
  if (!metrics || !trends) return <>
    <Heading title={t("Lot {lot}", { lot: detail.batch.batch_id })} />
    <p className="muted" data-lot>{detail.batch.product} · {batchKindName(detail.batch.kind ?? "")} · {detail.batch.provenance}</p>
    <ZoneNote />
    <AsOfControl timeline={detail.timeline} asOf={asOf} onChange={setAsOf} />
    <Section id="phases" title={t("Phase executions")} detail={t("Where the lot was prepared and held, and when. The batch that drew from it lists the draws under Transfers.")}><Phases detail={detail} /></Section>
    <Section id="samples" title={t("Samples")} detail={t("When each sample was collected. A time recorded wrongly can be corrected by an editor; the original is kept.")}>
      <SamplesSection batchId={batchId} samples={samples} detail={detail} canEdit={me.can_edit && !asOf} onChanged={() => setVersion((value) => value + 1)} />
    </Section>
    <Section id="results" title={t("Assay results")} detail={t("Each result has two times: when its sample was collected, and when the result became available.")}><Results samples={samples} /></Section>
  </>;
  const makeReference = async () => {
    if (!(await confirmAction(t("Compare every other batch with {batch} from now on? The change is written to PlantCraft's audit log.", { batch: batchId })))) return;
    api.setReference(batchId).then(() => setVersion((value) => value + 1)).catch((err) => setError(message(err)));
  };
  const toggleComparable = async () => {
    const question = detail.is_comparable
      ? t("Take {batch} out of the comparable batches? The change is written to PlantCraft's audit log.", { batch: batchId })
      : t("Add {batch} to the comparable batches the others are read against? The change is written to PlantCraft's audit log.", { batch: batchId });
    if (!(await confirmAction(question))) return;
    api.setComparable(batchId, !detail.is_comparable).then(() => setVersion((value) => value + 1)).catch((err) => setError(message(err)));
  };
  const comparable = metrics.comparable_batch_ids ?? [];
  const reference = detail.batch.is_reference
    ? t("This is the reference batch.")
    : metrics.reference_batch_id ? t("Reference batch: {batch}", { batch: metrics.reference_batch_id }) : t("No reference batch is set.");
  return <>
    <Heading title={t("Batch {batch}", { batch: detail.batch.batch_id })}
      actions={me.can_edit && !asOf
        ? <>
          {!detail.batch.is_reference && <button type="button" className="button" data-action="make-reference" onClick={() => void makeReference()}>{t("Make this the reference batch")}</button>}{" "}
          <button type="button" className="button" data-action="toggle-comparable" onClick={() => void toggleComparable()}>{detail.is_comparable ? t("Take out of the comparable batches") : t("Add to the comparable batches")}</button>
        </>
        : undefined} />
    <p className="muted">{detail.batch.product} · {reference} · {detail.batch.provenance}</p>
    <p className="muted" data-comparable>{comparable.length > 0
      ? t("Comparable batches: {batches}.", { batches: comparable.join(", ") })
      : t("No other batch is marked as comparable.")}{detail.is_comparable ? ` ${t("This batch is one of the comparable batches.")}` : ""}</p>
    <ZoneNote />
    <AsOfControl timeline={detail.timeline} asOf={asOf} onChange={setAsOf} />
    <Section id="phases" title={t("Phase executions")} detail={t("What happened on which asset, and when.")}><ProcessTrain phases={detail.phases} /><Phases detail={detail} /></Section>
    {metrics.findings.length > 0 && <Section id="findings" title={t("Findings")} detail={t("This batch against the reference batch. Tolerances are illustrative settings, not limits.")}>
      {metrics.findings.filter((finding) => !isQuiet(finding)).map((finding) => <FindingPanel key={finding.finding} finding={finding} />)}
      {metrics.findings.some(isQuiet) && <div className="panel" data-findings="within">
        <h3>{t("Checked and within tolerance")}</h3>
        <ul>{metrics.findings.filter(isQuiet).flatMap((finding) => finding.observation.reasons.map((reason, index) => <li key={`${finding.finding}-${index}`}>{reasonText(reason)}</li>))}</ul>
      </div>}
    </Section>}
    <Section id="metrics" title={t("Metrics")} detail={t("Computed on request from the records below and PlantCraft's signals. Masses are estimates from concentration × volume.")}><MetricsTable metrics={metrics} /></Section>
    <Section id="downstream" title={t("Downstream recovery")} detail={t("Each purification step: the product mass that went in and came out, and what is left of the harvest. Where pools were merged, the merged mass is checked against the sum of its parts.")}><DownstreamSection train={metrics.downstream} /></Section>
    <Section id="transfers" title={t("Transfers")} detail={t("What was moved into which vessel, as recorded, against what the volume signals of the vessels at both ends show arriving and leaving. Where a vessel and the record disagree the transfer is flagged; which of them is wrong is not decided.")}><Transfers transfers={metrics.transfers} /></Section>
    <Section id="pools" title={t("Pool measurements")}><Pools detail={detail} /></Section>
    <Section id="trends" title={t("Trends")} detail={t("The bioreactor's online signals over the production phase, read from PlantCraft, and the offline VCD and titer.")}><TrendCharts trends={trends} samples={samples} reference={beside} /></Section>
    <Section id="samples" title={t("Samples")} detail={t("When each sample was collected. A time recorded wrongly can be corrected by an editor; the original is kept.")}>
      <SamplesSection batchId={batchId} samples={samples} detail={detail} canEdit={me.can_edit && !asOf} onChanged={() => setVersion((value) => value + 1)} />
    </Section>
    <Section id="results" title={t("Assay results")} detail={t("Each result has two times: when its sample was collected, and when the result became available.")}><Results samples={samples} /></Section>
  </>;
}
