import type { BlockSummary } from "../../types";

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
  score?: number | null;   // 0–100 "match" for the score bar (resale only)
  appreciation?: number;   // appreciation sub-score (resale)
  area?: number;           // floor area sqft (private)
  sortDate?: number;       // recency epoch ms: sale date / eligible / lease year
  lat?: number;
  lon?: number;
  block?: BlockSummary;     // resale only — feeds the map + detail
}

export const MODE_META: Record<Mode, { label: string; blurb: string; color: string }> = {
  resale: { label: "HDB Resale", blurb: "Existing flats on the open market", color: "#2563eb" },
  bto: { label: "BTO", blurb: "New flats — launches & resale eligibility", color: "#16a34a" },
  private: { label: "Private", blurb: "Condos, apartments, EC & landed", color: "#9333ea" },
};
