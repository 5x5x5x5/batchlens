import { t } from "./i18n";

/** On every page: what this data is, and what it must never be used for. */
export function DemoBanner() {
  return <div className="notice demo-banner" role="note">{t("SYNTHETIC DEMO · NON-GxP · NOT FOR PROCESS CONTROL, RELEASE OR BATCH DISPOSITION")}</div>;
}
