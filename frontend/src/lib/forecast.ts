// Pure helpers for forecast display. Unit-tested.

export type TrendDirection = "up" | "flat" | "down";

export function trendDirection(
  slopePerMonth: number | null | undefined,
  threshold = 0.5,
): TrendDirection {
  if (slopePerMonth === null || slopePerMonth === undefined) return "flat";
  if (slopePerMonth > threshold) return "up";
  if (slopePerMonth < -threshold) return "down";
  return "flat";
}

export const TREND_ARROW: Record<TrendDirection, string> = {
  up: "▲",
  flat: "▬",
  down: "▼",
};

export const TREND_COLORS: Record<TrendDirection, string> = {
  up: "#16a34a",
  flat: "#9ca3af",
  down: "#dc2626",
};

export function projectedChangePct(
  current: number | null | undefined,
  projected: number | null | undefined,
): number | null {
  if (!current || projected === null || projected === undefined) return null;
  return Math.round(((projected - current) / current) * 1000) / 10;
}
