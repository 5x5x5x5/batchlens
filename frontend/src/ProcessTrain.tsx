/** The process train as a picture: one drawing per step, in process order, with the asset it
 * ran on. A step the batch has not reached (or had not, at the chosen time), or has no record
 * of, is drawn faded and says which. The drawings are schematic symbols, not the equipment. */
import { t } from "./i18n";
import type { Phase } from "./types";
import { phaseName } from "./words";

/** Process order. The picture shows every step, whether or not the batch has a record of it. */
export const TRAIN = ["seed_n2", "seed_n1", "production_culture", "harvest", "protein_a_capture", "viral_inactivation", "cation_exchange", "anion_exchange", "viral_filtration", "ufdf"];

/** A packed chromatography column, with what tells the three of them apart written on the bed. */
function Column({ mark }: { mark: string }) {
  return <>
    <path d="M24 4v6M24 46v6" />
    <rect x="15" y="10" width="18" height="36" rx="2" />
    <rect className="fill" x="15" y="17" width="18" height="24" />
    <path d="M15 17h18M15 41h18" />
    <text x="24" y="32.5">{mark}</text>
  </>;
}

/** A seed bioreactor: a small stirred tank, with its place in the seed train written on it. */
function SeedTank({ mark, small }: { mark: string; small?: boolean }) {
  const [x, top, width] = small ? [16, 26, 16] : [13, 18, 22];
  return <>
    <rect x="21" y={top - 7} width="6" height="5" rx="1" />
    <rect x={x} y={top} width={width} height={50 - top} rx="4" />
    <path className="fill" d={`M${x} ${top + 8}h${width}v${38 - top}a4 4 0 0 1-4 4h-${width - 8}a4 4 0 0 1-4-4z`} />
    <path d={`M24 ${top - 2}v6`} />
    <text x="24" y="44">{mark}</text>
  </>;
}

function Glyph({ kind }: { kind: string }) {
  switch (kind) {
    case "seed_n2": return <SeedTank mark="N-2" small />;
    case "seed_n1": return <SeedTank mark="N-1" />;
    case "production_culture": // stirred tank: motor, shaft, two impellers, liquid, sparger
      return <>
        <rect x="20" y="3" width="8" height="6" rx="1" />
        <path d="M12 14a4 4 0 0 1 4-4h16a4 4 0 0 1 4 4v24a12 12 0 0 1-24 0z" />
        <path className="fill" d="M12 22h24v16a12 12 0 0 1-24 0z" />
        <path d="M24 9v33M17 30h14M17 42h14M12 22h24" />
        <circle cx="16" cy="36" r="1" /><circle cx="32" cy="27" r="1" /><circle cx="30" cy="38" r="1" />
      </>;
    case "harvest": // depth filter: a housing with stacked pads, cloudy in, clear out
      return <>
        <path d="M4 16h8M36 40h8" />
        <rect x="12" y="8" width="24" height="40" rx="3" />
        <path className="fill" d="M12 16h24v24h-24z" />
        <path d="M12 16h24M12 24h24M12 32h24M12 40h24" />
        <circle cx="6" cy="12" r="1" /><circle cx="9" cy="20" r="1" />
      </>;
    case "protein_a_capture": return <Column mark="A" />;
    case "cation_exchange": return <Column mark="CEX" />;
    case "anion_exchange": return <Column mark="AEX" />;
    case "viral_inactivation": // a hold vessel at low pH
      return <>
        <path d="M11 14a13 5 0 0 1 26 0v26a13 5 0 0 1-26 0z" />
        <path className="fill" d="M11 22h26v18a13 5 0 0 1-26 0z" />
        <path d="M11 22h26M24 45v7" />
        <text x="24" y="36">pH</text>
      </>;
    case "viral_filtration": // a filter capsule with a fine membrane
      return <>
        <path d="M24 3v7M24 46v7" />
        <rect x="14" y="10" width="20" height="36" rx="10" />
        <path className="fill" d="M14 24h20v8h-20z" />
        <path d="M14 24h20M14 32h20M18 24v8M22 24v8M26 24v8M30 24v8" />
      </>;
    case "ufdf": // tangential flow: a membrane cassette, the retentate loop, permeate leaving
      return <>
        <rect className="fill" x="8" y="22" width="32" height="12" rx="1" />
        <path d="M8 28h32" strokeDasharray="2 2" />
        <path d="M40 25h4V8H4v17h4M20 5l-4 3 4 3" />
        <path d="M24 34v14M20 44l4 4 4-4" />
      </>;
    default: return <rect x="10" y="10" width="28" height="36" rx="3" />;
  }
}

export function ProcessTrain({ phases }: { phases: Phase[] }) {
  return <ol className="train" aria-label={t("Process train")}>
    {TRAIN.map((kind, index) => {
      const phase = phases.find((candidate) => candidate.kind === kind);
      // A step before one the batch has a record of was not "not started": it has no record.
      const passed = TRAIN.slice(index + 1).some((later) => phases.some((candidate) => candidate.kind === later));
      const state = !phase ? "pending" : phase.end ? "done" : "running";
      return <li key={kind} data-step={kind} data-state={state}>
        <svg viewBox="0 0 48 56" aria-hidden="true" focusable="false"><Glyph kind={kind} /></svg>
        <strong>{phaseName(kind)}</strong>
        <span className="muted">{phase ? phase.asset_id : passed ? t("No record") : t("Not started")}{state === "running" && ` · ${t("In progress")}`}</span>
      </li>;
    })}
  </ol>;
}
