import { describe, expect, it } from "vitest";
import { distanceMetres } from "./geo";

describe("distanceMetres", () => {
  it("returns zero for the same coordinate", () => {
    expect(distanceMetres({ lat: 1.35, lon: 103.82 }, { lat: 1.35, lon: 103.82 })).toBe(0);
  });

  it("calculates short Singapore distances in metres", () => {
    const distance = distanceMetres(
      { lat: 1.35, lon: 103.82 },
      { lat: 1.3509, lon: 103.82 },
    );
    expect(distance).toBeGreaterThan(99);
    expect(distance).toBeLessThan(101);
  });
});
