// Pure helpers for rendering 0-100 accessibility scores. Unit-tested.

export type ScoreBand = "excellent" | "good" | "fair" | "poor" | "unknown";

export function scoreBand(score: number | null | undefined): ScoreBand {
  if (score === null || score === undefined) return "unknown";
  if (score >= 75) return "excellent";
  if (score >= 50) return "good";
  if (score >= 25) return "fair";
  return "poor";
}

export const SCORE_COLORS: Record<ScoreBand, string> = {
  excellent: "#16a34a",
  good: "#65a30d",
  fair: "#ca8a04",
  poor: "#dc2626",
  unknown: "#9ca3af",
};

export const SCORE_LABELS: Record<ScoreBand, string> = {
  excellent: "Excellent",
  good: "Good",
  fair: "Fair",
  poor: "Poor",
  unknown: "—",
};

export function scoreColor(score: number | null | undefined): string {
  return SCORE_COLORS[scoreBand(score)];
}

export function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined) return "—";
  return String(Math.round(score));
}
