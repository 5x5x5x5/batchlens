/** The words for what the server sends as ids and codes: metrics, phases, analytes, statuses
 * and the reasons of a result. English here, translated through t() like every string. */
import { t } from "./i18n";
import type { Reason } from "./types";

export function metricName(metric: string): string {
  switch (metric) {
    case "ivcd": return t("Integral of viable cell density (IVCD)");
    case "qp": return t("Specific productivity (qP)");
    case "harvest_mass": return t("Product mass at harvest");
    case "protein_a_load_mass": return t("Protein A load mass");
    case "protein_a_eluate_mass": return t("Protein A eluate mass");
    case "harvest_to_load_yield": return t("Harvest-to-load yield");
    case "protein_a_recovery": return t("Protein A recovery");
    default: return metric;
  }
}

/** Significant digits a metric is shown with: what its inputs carry (cell counts and pool
 * concentrations three, the titer and the online volume four). */
export function metricDigits(metric: string): number {
  return metric === "harvest_mass" ? 4 : 3;
}

export function phaseName(kind: string): string {
  switch (kind) {
    case "production_culture": return t("Production culture");
    case "harvest": return t("Harvest");
    case "protein_a_capture": return t("Protein A capture");
    default: return kind;
  }
}

export function poolName(pool: string): string {
  switch (pool) {
    case "protein_a_load": return t("Protein A load");
    case "protein_a_eluate": return t("Protein A eluate");
    default: return pool;
  }
}

export function analyteName(analyte: string): string {
  switch (analyte) {
    case "vcd": return t("Viable cell density");
    case "viability": return t("Viability");
    case "glucose": return t("Glucose");
    case "lactate": return t("Lactate");
    case "titer": return t("Titer");
    default: return analyte;
  }
}

export function roleName(role: string): string {
  switch (role) {
    case "ph": return t("pH");
    case "do": return t("Dissolved oxygen");
    case "temperature": return t("Temperature");
    case "volume": return t("Volume");
    default: return role;
  }
}

function roleWord(role: string): string {
  switch (role) {
    case "ph": return t("pH");
    case "do": return t("dissolved oxygen");
    case "temperature": return t("temperature");
    case "volume": return t("volume");
    default: return role;
  }
}

export function statusWord(status: string): string {
  switch (status) {
    case "usable": return t("Usable");
    case "suspect": return t("Suspect");
    case "insufficient": return t("Insufficient");
    case "invalid": return t("Invalid");
    default: return status;
  }
}

/** The suite's status id (its tone) for a result's status. */
export function statusTone(status: string): string {
  return { usable: "ok", suspect: "suspect", insufficient: "insufficient_data", invalid: "error" }[status] ?? "inactive";
}

/** A reason as a sentence. A code without words is shown as it is, never hidden. */
export function reasonText(reason: Reason): string {
  const v = reason.values;
  const text = (key: string) => String(v[key] ?? "");
  switch (reason.code) {
    case "result_not_yet_available": return t("Result not yet available: {ids}.", { ids: (v.ids as string[] | undefined ?? []).join(", ") });
    case "estimated_from_concentration_times_volume": return t("Estimated from concentration × volume ({method}).", { method: text("method") });
    case "fewer_than_two_samples": return t("Fewer than two cell counts.");
    case "fewer_than_two_paired_samples": return t("Fewer than two samples have both a cell count and a titer.");
    case "gap_exceeds_maximum": return t("A gap of {gap} days between cell counts exceeds the limit of {max} days.", { gap: Number(v.gap_days).toFixed(1), max: text("max_gap_days") });
    case "wrong_unit": return t("{id} is in {unit}; {expected} is required, and units are never converted.", { id: text("id"), unit: text("unit") || "?", expected: text("expected") });
    case "non_finite_value": return t("{id} is not a finite number.", { id: text("id") });
    case "negative_value": return t("{id} is negative.", { id: text("id") });
    case "times_not_increasing": return t("Sample times are duplicated or out of order at {id}.", { id: text("id") });
    case "zero_denominator": return t("The denominator ({metric}) is zero.", { metric: metricName(text("metric")) });
    case "input_not_usable": return t("{metric} has no value ({status}).", { metric: metricName(text("metric")), status: statusWord(text("status")) });
    case "input_suspect": return t("{metric} is suspect.", { metric: metricName(text("metric")) });
    case "above_plausibility_bound": return t("Above the plausibility bound of {bound} %.", { bound: text("bound_percent") });
    case "negative_productivity": return t("The titer fell over the window.");
    case "phase_not_ended": return t("The production phase had not ended.");
    case "phase_not_started": return t("The production phase had not started.");
    case "phase_missing": return t("The batch has no production culture phase.");
    case "no_titer_in_phase": return t("No titer sample in the production phase.");
    case "no_titer_near_phase_end": return t("The last titer sample was collected more than {hours} h before the end of the phase.", { hours: text("window_hours") });
    case "no_volume_near_sample": return t("No bioreactor volume value within {seconds} s before the sample.", { seconds: text("max_age_seconds") });
    case "measurement_missing": return t("No pool measurement recorded.");
    case "asset_not_found": return t("Asset {asset} was not found in PlantCraft.", { asset: text("asset_id") });
    case "signal_not_found": return v.role
      ? t("{asset} has no {role} signal in PlantCraft.", { asset: text("asset_id"), role: roleWord(text("role")) })
      : t("Signal {signal} was not found in PlantCraft.", { signal: text("signal_id") });
    case "within_reference": return t("{metric} is within {tolerance} points of the reference batch ({value} % against {reference} %).", { metric: metricName(text("metric")), tolerance: text("tolerance_points"), value: Number(v.value).toFixed(1), reference: Number(v.reference_value).toFixed(1) });
    case "no_divergence": return t("Titer stayed within {tolerance} % of the reference batch at the end of {pairs} compared samples.", { tolerance: text("tolerance_percent"), pairs: text("pairs") });
    case "fewer_than_two_reference_pairs": return t("Fewer than two titer samples could be compared with the reference batch.");
    case "samples_without_reference_pair": return t("Left out, with no reference sample within {hours} h of the same culture age: {ids}.", { hours: text("pairing_window_hours"), ids: (v.ids as string[] | undefined ?? []).join(", ") });
    case "series_unreadable": return t("PlantCraft could not read the signal's history.");
    default: return reason.code;
  }
}
