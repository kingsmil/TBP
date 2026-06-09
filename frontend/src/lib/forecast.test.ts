import { describe, it, expect } from "vitest";
import { projectedChangePct, trendDirection, TREND_ARROW } from "./forecast";

describe("trendDirection", () => {
  it("classifies slope", () => {
    expect(trendDirection(2)).toBe("up");
    expect(trendDirection(-2)).toBe("down");
    expect(trendDirection(0.1)).toBe("flat");
    expect(trendDirection(null)).toBe("flat");
  });
  it("maps to an arrow", () => {
    expect(TREND_ARROW[trendDirection(2)]).toBe("▲");
  });
});

describe("projectedChangePct", () => {
  it("computes percentage change", () => {
    expect(projectedChangePct(500, 550)).toBe(10);
    expect(projectedChangePct(600, 540)).toBe(-10);
  });
  it("handles nulls", () => {
    expect(projectedChangePct(null, 550)).toBeNull();
    expect(projectedChangePct(500, null)).toBeNull();
  });
});
