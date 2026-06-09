import { describe, it, expect } from "vitest";
import {
  buildSearchQuery,
  formatDistance,
  formatPsf,
  formatSGD,
  mrtAccessClass,
} from "./format";

describe("formatters", () => {
  it("formats SGD and handles null", () => {
    expect(formatSGD(550000)).toContain("550,000");
    expect(formatSGD(null)).toBe("—");
  });

  it("formats psf", () => {
    expect(formatPsf(612.4)).toBe("$612 psf");
    expect(formatPsf(undefined)).toBe("—");
  });

  it("formats distance in m and km", () => {
    expect(formatDistance(350)).toBe("350 m");
    expect(formatDistance(1500)).toBe("1.5 km");
    expect(formatDistance(null)).toBe("—");
  });
});

describe("mrtAccessClass", () => {
  it("buckets by walking distance", () => {
    expect(mrtAccessClass(300)).toBe("good");
    expect(mrtAccessClass(800)).toBe("ok");
    expect(mrtAccessClass(2000)).toBe("far");
    expect(mrtAccessClass(null)).toBe("unknown");
  });
});

describe("buildSearchQuery", () => {
  it("omits undefined and empty values", () => {
    const q = buildSearchQuery({ town: "TAMPINES", flat_type: undefined });
    expect(q).toBe("town=TAMPINES");
  });

  it("expands bbox into four params", () => {
    const q = buildSearchQuery({ bbox: [103.9, 1.34, 103.97, 1.36] });
    const params = new URLSearchParams(q);
    expect(params.get("minx")).toBe("103.9");
    expect(params.get("maxy")).toBe("1.36");
  });

  it("serialises numeric filters", () => {
    const q = buildSearchQuery({ max_mrt_distance_m: 500, min_psf: 400 });
    const params = new URLSearchParams(q);
    expect(params.get("max_mrt_distance_m")).toBe("500");
    expect(params.get("min_psf")).toBe("400");
  });
});
