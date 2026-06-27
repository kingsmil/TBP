import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  searchProperties, getPrivateTransactions, getBtoResaleSupply, getBlockScores,
} from "../../lib/api";
import { MAP_SEARCH_LIMIT } from "../../lib/mapConfig";
import type { SearchFilters, BlockSummary, PrivateTransaction, BtoResaleSupplyRow } from "../../types";
import type { CardItem, Mode } from "./types";

const sgd = (n?: number | null) => (n != null ? `$${Math.round(n).toLocaleString()}` : "—");
const clamp = (n: number) => Math.max(0, Math.min(100, n));

/** Real 0–100 match blend from precomputed signals:
 *  commute (MRT proximity) + lifestyle (schools) + appreciation (precomputed). */
function matchScore(b: BlockSummary, appreciation?: number): number {
  const mrt = b.nearest_mrt_distance_m;
  const commute = mrt == null ? 50 : clamp(100 - (mrt / 1000) * 100); // 0m=100, ≥1km=0
  const lifestyle = clamp((b.schools_within_1km ?? 0) * 33); // 3+ schools ≈ 100
  const parts: [number, number][] = [[commute, 0.4], [lifestyle, 0.3]];
  if (appreciation != null) parts.push([appreciation, 0.3]);
  const wsum = parts.reduce((s, [, w]) => s + w, 0);
  return Math.round(parts.reduce((s, [v, w]) => s + v * w, 0) / wsum);
}

function walk(m?: number | null): string {
  if (m == null) return "MRT —";
  return `${Math.max(1, Math.round(m / 80))} min to MRT`; // ~80 m/min
}

function fromResale(b: BlockSummary, scores: Record<string, number>): CardItem {
  return {
    id: `r-${b.block_id}`,
    mode: "resale",
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
    score: matchScore(b, scores[String(b.block_id)]),
    appreciation: scores[String(b.block_id)],
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

/** Fetches every selected mode and merges them into one tagged list, so one or
 *  more property types can be shown together on the map + list. */
export function useListings(modes: Mode[], filters: SearchFilters) {
  const want = (m: Mode) => modes.includes(m);
  const key = modes.join(",");

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

  const items = useMemo<CardItem[]>(() => {
    const scores = scoresQ.data?.scores ?? {};
    const out: CardItem[] = [];
    if (want("resale")) out.push(...blocks.map((b) => fromResale(b, scores)));
    if (want("private")) out.push(...(priv.data?.results ?? []).map(fromPrivate));
    if (want("bto")) out.push(...(bto.data?.results ?? []).map(fromBto));
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, blocks, priv.data, bto.data, scoresQ.data]);

  const active = [
    want("resale") ? resale : null,
    want("private") ? priv : null,
    want("bto") ? bto : null,
  ].filter(Boolean) as { isLoading: boolean; isError: boolean }[];
  const isLoading = active.some((q) => q.isLoading);
  const isError = items.length === 0 && active.length > 0 && active.every((q) => q.isError);

  return { items, blocks, isLoading, isError, sgd };
}
