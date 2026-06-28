import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  searchProperties, getPrivateTransactions, getBtoResaleSupply, getBlockScores,
} from "../../lib/api";
import { MAP_SEARCH_LIMIT } from "../../lib/mapConfig";
import { scoreFromCounts } from "../../lib/lifestyle";
import type { SearchFilters, BlockSummary, PrivateTransaction, BtoResaleSupplyRow } from "../../types";
import type { CardItem, Mode, Weights } from "./types";
import { blendScore } from "./types";

const sgd = (n?: number | null) => (n != null ? `$${Math.round(n).toLocaleString()}` : "—");
const clamp = (n: number) => Math.max(0, Math.min(100, n));
const CUR_YEAR = new Date().getFullYear();

export interface Place { lat: number; lon: number }

function haversineKm(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const R = 6371, toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(bLat - aLat), dLon = toRad(bLon - aLon);
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

/** Commute score: if the user saved places (home/work/school), score by average
 *  proximity to them (0km=100, 12km=0); otherwise fall back to nearest-MRT. */
function commuteScore(b: BlockSummary, places: Place[]): number {
  if (places.length && b.lat != null && b.lon != null) {
    const avg = places.reduce((s, p) => s + haversineKm(b.lat!, b.lon!, p.lat, p.lon), 0) / places.length;
    return clamp(100 - (avg / 12) * 100);
  }
  const mrt = b.nearest_mrt_distance_m;
  return mrt == null ? 50 : clamp(100 - (mrt / 1000) * 100);           // 0m=100, ≥1km=0
}

/** Per-factor 0–100 sub-scores for a resale block, from precomputed signals.
 *  Lifestyle uses server-precomputed amenity counts (weighted at read time); if
 *  those are absent it falls back to the schools-count proxy. */
function resaleSubs(b: BlockSummary, appreciation: number | undefined, places: Place[]): Record<string, number | null> {
  const lifestyle = scoreFromCounts(b.amenity_counts) ?? clamp((b.schools_within_1km ?? 0) * 33);
  return {
    commute: commuteScore(b, places),
    lifestyle,
    appreciation: appreciation ?? null,
    value: b.median_psf == null ? null : clamp(100 - ((b.median_psf - 300) / 600) * 100), // $300=100, $900=0
    lease: clamp(((99 - (CUR_YEAR - b.lease_commencement_year)) / 99) * 100),
  };
}

function walk(m?: number | null): string {
  if (m == null) return "MRT —";
  return `${Math.max(1, Math.round(m / 80))} min to MRT`; // ~80 m/min
}

// Base resale card (subs computed; `score` is blended later, per weights, so a
// weight tweak doesn't re-run the heavy sub-score maths).
function fromResale(b: BlockSummary, scores: Record<string, number>, places: Place[]): CardItem {
  const appr = scores[String(b.block_id)];
  const subs = resaleSubs(b, appr, places);
  return {
    id: `r-${b.block_id}`,
    mode: "resale",
    subs,
    title: `Blk ${b.block_number} ${b.street_name}`,
    subtitle: b.town,
    badge: undefined,
    price: b.median_price,
    priceLabel: "median",
    psf: b.median_psf,
    metrics: [
      { label: "Walk", value: walk(b.nearest_mrt_distance_m) },
      { label: "Schools", value: `${b.schools_within_1km ?? 0} within 1km` },
      { label: "Lease from", value: String(b.lease_commencement_year) },
    ],
    score: null,
    appreciation: appr,
    sortDate: new Date(b.lease_commencement_year, 0, 1).getTime(),
    lat: b.lat,
    lon: b.lon,
    block: b,
  };
}

function fromPrivate(t: PrivateTransaction): CardItem {
  return {
    id: `p-${t.id}`,
    mode: "private",
    title: t.project_name ?? t.address ?? "Private home",
    subtitle: `District ${t.district ?? "—"} · ${t.planning_region ?? ""}`.trim(),
    badge: t.property_type,
    price: t.price,
    priceLabel: t.sale_type.replace("_", " ").toLowerCase(),
    psf: t.psf,
    metrics: [
      { label: "Area", value: t.area_sqft ? `${t.area_sqft} sqft` : "—" },
      { label: "Tenure", value: t.tenure ? (t.tenure.includes("Freehold") ? "Freehold" : "Leasehold") : "—" },
      { label: "Sold", value: t.sale_date.slice(0, 7) },
    ],
    area: t.area_sqft ?? undefined,
    sortDate: Date.parse(t.sale_date) || undefined,
    lat: t.lat ?? undefined,
    lon: t.lon ?? undefined,
  };
}

function fromBto(r: BtoResaleSupplyRow): CardItem {
  return {
    id: `b-${r.id}`,
    mode: "bto",
    title: r.project_name,
    subtitle: r.town ?? "—",
    badge: r.flat_classification,
    price: null,
    psf: null,
    metrics: [
      { label: "Flat types", value: r.flat_types ?? "—" },
      { label: "MOP", value: `${r.mop_years} yrs` },
      { label: "Resale est.", value: r.estimated_resale_eligible_date?.slice(0, 7) ?? "—" },
    ],
    pinLabel: r.estimated_resale_eligible_date
      ? `Resale '${r.estimated_resale_eligible_date.slice(2, 4)}` : undefined,
    sortDate: r.estimated_resale_eligible_date ? Date.parse(r.estimated_resale_eligible_date) || undefined : undefined,
    lat: r.lat ?? undefined,
    lon: r.lon ?? undefined,
  };
}

/** Client-side filters for private/BTO (resale is filtered server-side). */
function passesPrivate(it: CardItem, f: SearchFilters): boolean {
  if (f.property_type && it.badge !== f.property_type) return false;
  if (f.max_price != null && (it.price ?? Infinity) > f.max_price) return false;
  if (f.min_price != null && (it.price ?? -Infinity) < f.min_price) return false;
  if (f.max_psf != null && (it.psf ?? Infinity) > f.max_psf) return false;
  if (f.min_psf != null && (it.psf ?? -Infinity) < f.min_psf) return false;
  return true;
}
function passesBto(it: CardItem, f: SearchFilters): boolean {
  if (f.town && !it.subtitle.toLowerCase().includes(f.town.toLowerCase())) return false;
  if (f.flat_type) {
    const types = it.metrics.find((m) => m.label === "Flat types")?.value ?? "";
    if (!types.toLowerCase().includes(f.flat_type.toLowerCase())) return false;
  }
  return true;
}

/** Fetches every selected mode and merges them into one tagged list, so one or
 *  more property types can be shown together on the map + list. */
export function useListings(modes: Mode[], filters: SearchFilters, weights: Weights, places: Place[] = []) {
  const want = (m: Mode) => modes.includes(m);
  const key = modes.join(",");
  const wkey = JSON.stringify(weights);
  const pkey = JSON.stringify(places);
  const fkey = JSON.stringify(filters);

  const resale = useQuery({
    queryKey: ["bo-resale", filters],
    queryFn: () => searchProperties({ ...filters, limit: MAP_SEARCH_LIMIT }),
    enabled: want("resale"),
  });
  const priv = useQuery({
    queryKey: ["bo-private"],
    queryFn: () => getPrivateTransactions({ limit: 2000 }),
    enabled: want("private"),
  });
  const bto = useQuery({
    queryKey: ["bo-bto"],
    queryFn: () => getBtoResaleSupply({ sort: "soonest" }),
    enabled: want("bto"),
  });
  const scoresQ = useQuery({
    queryKey: ["bo-block-scores"],
    queryFn: getBlockScores,
    enabled: want("resale"),
    staleTime: 36e5,
  });
  const blocks = useMemo<BlockSummary[]>(
    () => (want("resale") ? resale.data?.results ?? [] : []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [key, resale.data],
  );

  // Heavy part: per-block sub-scores. Recomputed only when the data/places/
  // amenities change — NOT when weights change.
  const resaleBase = useMemo<CardItem[]>(() => {
    if (!want("resale")) return [];
    const scores = scoresQ.data?.scores ?? {};
    return blocks.map((b) => fromResale(b, scores, places));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, pkey, blocks, scoresQ.data]);

  // Cheap part: blend sub-scores with the current weights, and apply the filters
  // to private/BTO client-side (resale is already filtered server-side).
  const items = useMemo<CardItem[]>(() => {
    const out: CardItem[] = [];
    if (want("resale")) out.push(...resaleBase.map((c) => ({ ...c, score: blendScore(c.subs, weights) })));
    if (want("private")) out.push(...(priv.data?.results ?? []).map(fromPrivate).filter((it) => passesPrivate(it, filters)));
    if (want("bto")) out.push(...(bto.data?.results ?? []).map(fromBto).filter((it) => passesBto(it, filters)));
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, wkey, fkey, resaleBase, priv.data, bto.data]);

  const active = [
    want("resale") ? resale : null,
    want("private") ? priv : null,
    want("bto") ? bto : null,
  ].filter(Boolean) as { isLoading: boolean; isError: boolean }[];
  const isLoading = active.some((q) => q.isLoading);
  const isError = items.length === 0 && active.length > 0 && active.every((q) => q.isError);

  return { items, blocks, isLoading, isError, sgd };
}
