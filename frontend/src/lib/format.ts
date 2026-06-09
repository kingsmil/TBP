// Pure, framework-free helpers. These are unit-tested with Vitest because they
// hold display + query logic that should never silently break.

import type { SearchFilters } from "../types";

export function formatSGD(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-SG", {
    style: "currency",
    currency: "SGD",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatPsf(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `$${value.toFixed(0)} psf`;
}

export function formatDistance(metres: number | null | undefined): string {
  if (metres === null || metres === undefined) return "—";
  if (metres < 1000) return `${Math.round(metres)} m`;
  return `${(metres / 1000).toFixed(1)} km`;
}

// Bucket walking distance to the nearest MRT into a fit class. Used for map
// colouring; a richer scoring model arrives in later phases.
export type AccessClass = "good" | "ok" | "far" | "unknown";

export function mrtAccessClass(metres: number | null | undefined): AccessClass {
  if (metres === null || metres === undefined) return "unknown";
  if (metres <= 400) return "good";
  if (metres <= 1000) return "ok";
  return "far";
}

export const ACCESS_COLORS: Record<AccessClass, string> = {
  good: "#4a9a6f",    // softer green (≤400m)
  ok: "#b8943f",      // softer amber (≤1km)
  far: "#b05050",     // softer red (>1km)
  unknown: "#889688", // muted sage from palette
};

// Build a query string from filters, omitting undefined values and expanding
// bbox into its four numeric params (matching the backend contract).
export function buildSearchQuery(filters: SearchFilters): string {
  const params = new URLSearchParams();
  const { bbox, ...rest } = filters;
  if (bbox) {
    const [minx, miny, maxx, maxy] = bbox;
    params.set("minx", String(minx));
    params.set("miny", String(miny));
    params.set("maxx", String(maxx));
    params.set("maxy", String(maxy));
  }
  for (const [key, value] of Object.entries(rest)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  return params.toString();
}
