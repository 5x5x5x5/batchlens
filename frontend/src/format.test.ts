import { describe, expect, it } from "vitest";
import { signedBetween, significant } from "./format";
import { metricDigits, reasonText } from "./words";

describe("display rounding", () => {
  it("shows a value at the significant digits its inputs carry, never more", () => {
    expect(significant(10174.4736, 4)).toBe("10,170");
    expect(significant(171.7462, 3)).toBe("172");
    expect(significant(29.6213, 3)).toBe("29.6");
    expect(significant(97.0049, 3)).toBe("97.0");
    expect(significant(-9.4012, 3)).toBe("-9.40");
    expect(significant(0, 3)).toBe("0.00");
    expect(significant(null, 3)).toBe("");
  });

  it("shows a difference no finer than the coarser of the two values beside it", () => {
    expect(signedBetween(1.6236, 31.2449, 29.6213, 3)).toBe("+1.6");
    expect(signedBetween(-2857.01, 7317.46, 10174.47, 4)).toBe("-2,860"); // 10,170 is known to the ten
    expect(signedBetween(12.8084, 106.3596, 93.5512, 3)).toBe("+13"); // 106 is known to the unit
    expect(signedBetween(null, 1, 2, 3)).toBe("");
    expect(signedBetween(1, 1, null, 3)).toBe("");
  });

  it("knows the digits of every metric the server computes", () => {
    for (const metric of ["ivcd", "qp", "harvest_mass", "protein_a_load_mass", "protein_a_eluate_mass", "harvest_to_load_yield", "protein_a_recovery"]) {
      expect(metricDigits(metric)).toBeGreaterThanOrEqual(3);
    }
  });
});

describe("reasons", () => {
  it("turns a reason code and its values into words", () => {
    expect(reasonText({ code: "asset_not_found", values: { asset_id: "BR-2001" } })).toBe("Asset BR-2001 was not found in PlantCraft.");
    expect(reasonText({ code: "result_not_yet_available", values: { ids: ["BL-0001-S15-titer"] } })).toBe("Result not yet available: BL-0001-S15-titer.");
    expect(reasonText({ code: "estimated_from_concentration_times_volume", values: { method: "Protein A HPLC" } })).toBe("Estimated from concentration × volume (Protein A HPLC).");
    expect(reasonText({ code: "above_plausibility_bound", values: { bound_percent: 105 } })).toBe("Above the plausibility bound of 105 %.");
  });

  it("never hides a code it has no words for", () => {
    expect(reasonText({ code: "something_new", values: {} })).toBe("something_new");
  });
});
