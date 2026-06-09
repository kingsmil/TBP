// Pure helpers for appreciation / risk / confidence display. Unit-tested.

export type Level = "low" | "medium" | "high";

// Risk: low is GOOD (green), high is BAD (red).
export const RISK_COLORS: Record<Level, string> = {
  low: "#16a34a",
  medium: "#ca8a04",
  high: "#dc2626",
};

// Confidence: high is GOOD (green), low is weak (grey).
export const CONFIDENCE_COLORS: Record<Level, string> = {
  high: "#16a34a",
  medium: "#ca8a04",
  low: "#9ca3af",
};

export function riskColor(level: string): string {
  return RISK_COLORS[level as Level] ?? "#9ca3af";
}

export function confidenceColor(level: string): string {
  return CONFIDENCE_COLORS[level as Level] ?? "#9ca3af";
}

export function formatLevel(level: string | null | undefined): string {
  if (!level) return "—";
  return level.charAt(0).toUpperCase() + level.slice(1);
}
