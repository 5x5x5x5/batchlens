export interface Me {
  username: string; name: string; level: string; access: string; role: string; can_edit: boolean; is_admin: boolean;
  processcraft_url: string; version: string; service_key: boolean;
}

/** The shapes of src/batchlens/api/routers/batches.py. Every instant is UTC text. */
/** `kind`: "product", or a solution lot's ("medium", "buffer"), whose `product` names the solution. */
export interface Batch { batch_id: string; product: string; is_reference: boolean; created_at: string; provenance: string; kind?: string }

export interface BatchRow extends Batch {
  /** The batch's window: its first phase execution's start to its last one's end. */
  start: string | null; end: string | null;
  /** Still running: it has no end yet. */
  running?: boolean;
  /** The production bioreactor: its id, and its name in PlantCraft (none when it is not there). */
  asset_id: string | null; asset_name: string | null;
  /** In the set of comparable batches the others are read against. */
  is_comparable?: boolean;
}

export interface BatchList { time_zone: string; batches: BatchRow[] }

/** `end` is null in an as-of view of a phase that had not ended yet. */
export interface Phase { phase_id: string; batch_id: string; kind: string; asset_id: string; start: string; end: string | null; provenance: string; asset_name: string | null }

export interface Pool {
  measurement_id: string; batch_id: string; phase_id: string; pool: string; volume: number; volume_unit: string;
  concentration: number; concentration_unit: string; method: string; measured_at: string; result_available_at: string; provenance: string;
}

export interface BatchDetail {
  time_zone: string; as_of: string | null; batch: Batch; is_comparable?: boolean; phases: Phase[]; pools: Pool[];
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
  /** Where the value sits among the comparable batches' (its reason carries their count,
   * median, lowest and highest); null when no batch is comparable. */
  comparable?: Result | null;
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
  /** Hours since the last feed before each sample; null before the first feed. */
  hours_since_feed?: number | null; reference_hours_since_feed?: number | null;
  /** For a buffer lot beside the reference's: the solution, both lots, and each lot's age in
   * days when its step began to draw it. */
  solution?: string; lot_id?: string; reference_lot_id?: string; age_days?: number; reference_age_days?: number;
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

export interface Metrics { batch_id: string; as_of: string | null; reference_batch_id: string | null; comparable_batch_ids?: string[]; metrics: Metric[]; findings: Finding[]; downstream: Downstream; transfers: Transfer[] }

/** Material moved from one asset into another, as recorded, with its balance against the
 * destination's volume signal. In an as-of view of one under way, `end` and `volume` are null. */
export interface Transfer {
  transfer_id: string; kind: string; from_asset_id: string; to_asset_id: string; from_lot_id: string;
  /** The solution lot drawn from: what it is, and its age in days when the transfer began. */
  lot_solution?: string | null; lot_age_days?: number | null;
  start: string; end: string | null; volume: number | null; volume_unit: string; balance: Result;
}

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
