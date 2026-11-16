/** Times as the pages show them: in the installation's zone, with the zone named. */
import { configureTimeZone, displayTimeZone, timeZoneLabel } from "@plantcraft/ui";
import { formatDate, t } from "./i18n";

/** The installation's zone as the server read it from PlantCraft (the frame's cookie says the
 * same inside the platform; an app opened on its own has no cookie). */
export function useInstallationZone(zone: string | undefined) {
  if (zone) configureTimeZone({ plant: zone });
}

export function when(value: string | null | undefined): string {
  return value ? formatDate(value) : "";
}

/** The line that names the zone every time on the page is shown in. */
export function ZoneNote() {
  return <p className="muted small">{t("Times are shown in {zone}.", { zone: timeZoneLabel(displayTimeZone()) })}</p>;
}

export function NotInPlantCraft() {
  return <small>{t("Not found in PlantCraft")}</small>;
}
