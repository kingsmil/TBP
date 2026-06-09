import { describe, it, expect } from "vitest";
import { formatScore, scoreBand, scoreColor } from "./score";

describe("scoreBand", () => {
  it("buckets by threshold", () => {
    expect(scoreBand(90)).toBe("excellent");
    expect(scoreBand(60)).toBe("good");
    expect(scoreBand(30)).toBe("fair");
    expect(scoreBand(10)).toBe("poor");
    expect(scoreBand(null)).toBe("unknown");
  });

  it("is inclusive at boundaries", () => {
    expect(scoreBand(75)).toBe("excellent");
    expect(scoreBand(50)).toBe("good");
    expect(scoreBand(25)).toBe("fair");
  });
});

describe("scoreColor / formatScore", () => {
  it("maps band to a colour", () => {
    expect(scoreColor(80)).toBe("#16a34a");
    expect(scoreColor(undefined)).toBe("#9ca3af");
  });

  it("rounds scores and handles null", () => {
    expect(formatScore(72.6)).toBe("73");
    expect(formatScore(null)).toBe("—");
  });
});
