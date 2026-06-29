import type { BlockSummary, BtoResaleSupplyRow } from "../../types";

export type Mode = "bto" | "resale" | "private";

export interface CardMetric {
  label: string;
  value: string;
}

/** Unified card model rendered by every variant + every mode. */
export interface CardItem {
  id: string;
  mode: Mode;              // which dataset it came from (drives pin colour)
  title: string;
  subtitle: string;
  badge?: string;          // flat type / sale type / classification
  price?: number | null;   // headline $ (or null)
  priceLabel?: string;     // e.g. "median", "from"
  psf?: number | null;
  metrics: CardMetric[];   // up to 3 friendly chips
  pinLabel?: string;       // overrides the map-pin text (else price / badge)
  score?: number | null;   // 0–100 "match" (weighted blend, resale only)
  subs?: Record<string, number | null>; // per-factor sub-scores (for re-weighting + explainability)
  appreciation?: number;   // appreciation sub-score (resale)
  area?: number;           // floor area sqft (private)
  sortDate?: number;       // recency epoch ms: sale date / eligible / lease year
  lat?: number;
  lon?: number;
  block?: BlockSummary;     // resale only — feeds the map + detail
  bto?: BtoResaleSupplyRow; // bto only — feeds the detail panel
}

/** Client-side scoring factors (resale). Weights drive the "match" blend. */
export const SCORE_FACTORS = [
  { key: "commute", label: "Commute" },
  { key: "lifestyle", label: "Lifestyle" },
  { key: "appreciation", label: "Appreciation" },
  { key: "value", label: "Value (PSF)" },
  { key: "lease", label: "Lease" },
] as const;
export type Weights = Record<string, number>;
export const DEFAULT_WEIGHTS: Weights = { commute: 30, lifestyle: 20, appreciation: 20, value: 20, lease: 10 };

/** Migrate older saved weights (the "schools" factor became "lifestyle"). */
export function migrateWeights(w: Weights): Weights {
  if (w && w.schools != null && w.lifestyle == null) {
    const { schools, ...rest } = w;
    return { ...rest, lifestyle: schools };
  }
  return w;
}

/** Weighted-normalised blend of a block's per-factor sub-scores (nulls excluded). */
export function blendScore(subs: Record<string, number | null> | undefined, weights: Weights): number | null {
  if (!subs) return null;
  let wsum = 0, acc = 0;
  for (const { key } of SCORE_FACTORS) {
    const v = subs[key]; const w = weights[key] ?? 0;
    if (v == null || w <= 0) continue;
    acc += v * w; wsum += w;
  }
  return wsum > 0 ? Math.round(acc / wsum) : null;
}

export const MODE_META: Record<Mode, { label: string; blurb: string; color: string }> = {
  resale: { label: "HDB Resale", blurb: "Existing flats on the open market", color: "#2563eb" },
  bto: { label: "BTO", blurb: "New flats — launches & resale eligibility", color: "#16a34a" },
  private: { label: "Private", blurb: "Condos, apartments, EC & landed", color: "#9333ea" },
};
