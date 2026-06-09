// Pure helpers for commute results. Unit-tested.

export type CommuteBand = "green" | "yellow" | "red";

export const BAND_COLORS: Record<CommuteBand, string> = {
  green: "#16a34a",
  yellow: "#ca8a04",
  red: "#dc2626",
};

export function bandColor(band: string): string {
  return BAND_COLORS[band as CommuteBand] ?? "#9ca3af";
}

export function formatMinutes(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return "—";
  const rounded = Math.round(minutes);
  if (rounded < 60) return `${rounded} min`;
  const h = Math.floor(rounded / 60);
  const m = rounded % 60;
  return m === 0 ? `${h}h` : `${h}h ${m}m`;
}

export interface DestinationInput {
  name: string;
  lat: number;
  lon: number;
  visits_per_week: number;
  mode?: string;
}

// Build the POST body for /commute/optimize and /commute/heatmap.
export function toCommutePayload(destinations: DestinationInput[], limit = 100) {
  return {
    destinations: destinations.map((d) => ({
      name: d.name,
      lat: d.lat,
      lon: d.lon,
      visits_per_week: d.visits_per_week,
      mode: d.mode ?? "pt",
    })),
    limit,
  };
}
