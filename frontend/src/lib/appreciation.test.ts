import { describe, it, expect } from "vitest";
import { confidenceColor, formatLevel, riskColor } from "./appreciation";

describe("riskColor", () => {
  it("treats low risk as good (green) and high as bad (red)", () => {
    expect(riskColor("low")).toBe("#16a34a");
    expect(riskColor("high")).toBe("#dc2626");
  });
  it("falls back for unknown", () => {
    expect(riskColor("???")).toBe("#9ca3af");
  });
});

describe("confidenceColor", () => {
  it("treats high confidence as good and low as grey", () => {
    expect(confidenceColor("high")).toBe("#16a34a");
    expect(confidenceColor("low")).toBe("#9ca3af");
  });
});

describe("formatLevel", () => {
  it("capitalises and handles null", () => {
    expect(formatLevel("medium")).toBe("Medium");
    expect(formatLevel(null)).toBe("—");
  });
});
