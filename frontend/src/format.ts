/** Rounding for display only: the server sends full values, the page never shows more precision
 * than the inputs carry (docs/scientific-assumptions.md, "Display"). No formula lives here. */
import { locale } from "./i18n";

/** The decimal place of the last of `digits` significant digits of `value`: 1 for tenths,
 * 0 for units, -1 for tens. */
function place(value: number, digits: number): number {
  if (value === 0) return digits - 1;
  const rounded = Number(value.toPrecision(digits));
  return digits - 1 - Math.floor(Math.log10(Math.abs(rounded)));
}

/** `value` at `digits` significant digits ("10,170", "29.6", "97.0"); nothing for no value. */
export function significant(value: number | null | undefined, digits: number): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "";
  const decimals = Math.max(0, place(value, digits));
  return Number(value.toPrecision(digits)).toLocaleString(locale, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

/** A difference of two shown values, signed ("+1.6", "-2,860"), at the coarser of their two
 * last shown places: it never looks more precise than either number beside it. */
export function signedBetween(difference: number | null | undefined, value: number | null | undefined, reference: number | null | undefined, digits: number): string {
  if (difference == null || value == null || reference == null) return "";
  const at = Math.min(place(value, digits), place(reference, digits));
  const rounded = Math.round(difference * 10 ** at) / 10 ** at;
  const decimals = Math.max(0, at);
  return rounded.toLocaleString(locale, { minimumFractionDigits: decimals, maximumFractionDigits: decimals, signDisplay: "exceptZero" });
}

/** A recorded value as the server sent it. Trailing zeros are not shown (0.300 reads 0.3): the
 * page does not know how many decimals the assay reports (docs/gaps.md). */
export function recorded(value: number): string {
  return value.toLocaleString(locale, { maximumFractionDigits: 6 });
}
