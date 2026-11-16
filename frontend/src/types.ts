export interface Me {
  username: string; name: string; level: string; access: string; role: string; can_edit: boolean; is_admin: boolean;
  processcraft_url: string; version: string; service_key: boolean;
}

/** The shapes of src/batchlens/api/routers/batches.py. Every instant is UTC text. */
export interface Batch { batch_id: string; product: string; is_reference: boolean; created_at: string; provenance: string }

export interface BatchRow extends Batch {
  /** The batch's window: its first phase execution's start to its last one's end. */
  start: string | null; end: string | null;
  /** Still running: it has no end yet. */
  running?: boolean;
  /** The production bioreactor: its id, and its name in PlantCraft (none when it is not there). */
  asset_id: string | null; asset_name: string | null;
}

export interface BatchList { time_zone: string; batches: BatchRow[] }

/** `end` is null in an as-of view of a phase that had not ended yet. */
export interface Phase { phase_id: string; batch_id: string; kind: string; asset_id: string; start: string; end: string | null; provenance: string; asset_name: string | null }

export interface Pool {
  measurement_id: string; batch_id: string; phase_id: string; pool: string; volume: number; volume_unit: string;
  concentration: number; concentration_unit: string; method: string; measured_at: string; result_available_at: string; provenance: string;
}

export interface BatchDetail {
  time_zone: string; as_of: string | null; batch: Batch; phases: Phase[]; pools: Pool[];
  /** From the batch's start to the last moment anything about it became known. */
  timeline: { start: string | null; end: string | null };
  /** What people changed, with the values replaced, oldest first. */
  corrections: Correction[];
}

export interface Correction { correction_id: string; batch_id: string; record_id: string; field: string; old_value: string; new_value: string; reason: string; corrected_by: string; corrected_at: string }

/** Why a result is as it is: a code and the values involved (words in words.ts). */
export interface Reason { code: string; values: Record<string, unknown> }

export interface Metric {
  metric: string; value: number | null; unit: string; status: string; reasons: Reason[]; inputs: string[]; calculation_version: string;
  reference: { value: number | null; status: string } | null;
  /** This batch minus the reference, computed by the server. */
  difference: number | null;
}

/** A result of src/batchlens/calc: value, unit, status, reasons, inputs. */
export interface Result { metric: string; value: number | null; unit: string; status: string; reasons: Reason[]; inputs: string[]; calculation_version: string }

/** What stands out against the reference batch, in three separate parts: what was observed,
 * what that amounts to, and the cause, which the app never attributes. */
export interface Finding {
  finding: string;
  observation: Result;
  consequence: { metric: string; unit: string; status: string; value: number | null; reference: number | null; difference: number | null } | null;
  /** For a divergence: the other results of the samples it rests on, beside the reference's. */
  evidence: Evidence[];
  cause: null;
}

export interface Evidence {
  at: string; sample_id: string; reference_sample_id: string; culture_day: number;
  results: Array<{ analyte: string; unit: string; result_id: string; value: number; reference_result_id: string | null; reference_value: number | null; difference: number | null }>;
}

/** The purification train: each step's masses and yield, the recovery from harvest, and what
 * each pool was made from. */
export interface Downstream {
  steps: Array<{ step: string; mass_in: Result; mass_out: Result; step_yield: Result; from_harvest: Result; reference_yield?: number | null; yield_difference?: number | null }>;
  overall: Result;
  overall_reference: number | null;
  genealogy: Array<{ pool: string; measurement_id: string; mass: Result; sources: string[]; merge_balance: Result | null }>;
}

export interface Metrics { batch_id: string; as_of: string | null; reference_batch_id: string | null; metrics: Metric[]; findings: Finding[]; downstream: Downstream }

export interface AssayResult { result_id: string; sample_id: string; analyte: string; value: number; unit: string; method: string; result_available_at: string; validity: string; provenance: string }

export interface Sample {
  sample_id: string; batch_id: string; phase_id: string; collected_at: string; provenance: string; results: AssayResult[];
  /** The kind of the phase the sample was taken in (a seed passage or the production culture). */
  phase_kind: string | null;
  /** Days since the start of the sample's own phase. */
  culture_day: number | null;
  /** A person corrected this sample's collection time (the history is on the batch). */
  corrected: boolean;
  /** With `align_to`: the instant of the same culture age on the other batch's timeline. */
  aligned_at: string | null;
}

export interface Samples { batch_id: string; as_of: string | null; aligned_to: string | null; samples: Sample[] }

export interface Trend { role: string; signal_id: string | null; name: string | null; unit: string | null; t: string[]; v: Array<number | null>; status: string; reasons: Reason[] }

export interface Trends { batch_id: string; as_of: string | null; asset_id: string | null; start: string | null; end: string | null; step_seconds: number | null; signals: Trend[] }
