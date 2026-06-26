import type { BlockSummary } from "../../types";

export type Mode = "bto" | "resale" | "private";

export interface CardMetric {
  label: string;
  value: string;
}

/** Unified card model rendered by every variant + every mode. */
export interface CardItem {
  id: string;
  title: string;
  subtitle: string;
  badge?: string;          // flat type / sale type / classification
  price?: number | null;   // headline $ (or null)
  priceLabel?: string;     // e.g. "median", "from"
  psf?: number | null;
  metrics: CardMetric[];   // up to 3 friendly chips
  pinLabel?: string;       // overrides the map-pin text (else price / badge)
  score?: number | null;   // 0–100 "match" for the score bar (resale only)
  lat?: number;
  lon?: number;
  block?: BlockSummary;     // resale only — feeds the map + detail
}

export const MODE_META: Record<Mode, { label: string; blurb: string }> = {
  resale: { label: "HDB Resale", blurb: "Existing flats on the open market" },
  bto: { label: "BTO", blurb: "New flats — launches & resale eligibility" },
  private: { label: "Private", blurb: "Condos, apartments, EC & landed" },
};
