import { describe, it, expect } from "vitest";
import { bandColor, formatMinutes, toCommutePayload } from "./commute";

describe("bandColor", () => {
  it("maps bands to colours", () => {
    expect(bandColor("green")).toBe("#16a34a");
    expect(bandColor("yellow")).toBe("#ca8a04");
    expect(bandColor("red")).toBe("#dc2626");
  });
  it("falls back for unknown band", () => {
    expect(bandColor("purple")).toBe("#9ca3af");
  });
});

describe("formatMinutes", () => {
  it("formats sub-hour and hour values", () => {
    expect(formatMinutes(45)).toBe("45 min");
    expect(formatMinutes(60)).toBe("1h");
    expect(formatMinutes(95)).toBe("1h 35m");
    expect(formatMinutes(null)).toBe("—");
  });
});

describe("toCommutePayload", () => {
  it("defaults mode to pt and includes limit", () => {
    const body = toCommutePayload(
      [{ name: "Office", lat: 1.35, lon: 103.94, visits_per_week: 5 }],
      50,
    );
    expect(body.limit).toBe(50);
    expect(body.destinations[0].mode).toBe("pt");
    expect(body.destinations[0].name).toBe("Office");
  });
});
