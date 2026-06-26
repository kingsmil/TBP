import { useQuery } from "@tanstack/react-query";
import {
  searchProperties, getPrivateTransactions, getBtoResaleSupply,
} from "../../lib/api";
import { MAP_SEARCH_LIMIT } from "../../lib/mapConfig";
import type { SearchFilters, BlockSummary } from "../../types";
import type { CardItem, Mode } from "./types";

const sgd = (n?: number | null) => (n != null ? `$${Math.round(n).toLocaleString()}` : "—");

/** A light 0–100 "match" score for resale, purely for the demo score bar:
 *  closer MRT + more schools + more liquidity = higher. */
function resaleScore(b: BlockSummary): number {
  const mrt = b.nearest_mrt_distance_m;
  const mrtScore = mrt == null ? 50 : Math.max(0, Math.min(100, 100 - (mrt / 1200) * 100));
  const schoolScore = Math.min(100, (b.schools_within_1km ?? 0) * 25);
  const liq = Math.min(100, (b.txn_count ?? 0) * 4);
  return Math.round(mrtScore * 0.55 + schoolScore * 0.3 + liq * 0.15);
}

function walk(m?: number | null): string {
  if (m == null) return "MRT —";
  return `${Math.max(1, Math.round(m / 80))} min to MRT`; // ~80 m/min
}

function fromResale(b: BlockSummary): CardItem {
  return {
    id: `r-${b.block_id}`,
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
    score: resaleScore(b),
    lat: b.lat,
    lon: b.lon,
    block: b,
  };
}

export function useListings(mode: Mode, filters: SearchFilters) {
  const resale = useQuery({
    queryKey: ["bo-resale", filters],
    queryFn: () => searchProperties({ ...filters, limit: MAP_SEARCH_LIMIT }),
    enabled: mode === "resale",
  });
  const priv = useQuery({
    queryKey: ["bo-private", filters.flat_type],
    queryFn: () => getPrivateTransactions({ limit: 60 }),
    enabled: mode === "private",
  });
  const bto = useQuery({
    queryKey: ["bo-bto"],
    queryFn: () => getBtoResaleSupply({ sort: "soonest" }),
    enabled: mode === "bto",
  });

  let items: CardItem[] = [];
  let blocks: BlockSummary[] = [];
  let isLoading = false;
  let isError = false;

  if (mode === "resale") {
    blocks = resale.data?.results ?? [];
    items = blocks.map(fromResale);
    isLoading = resale.isLoading; isError = resale.isError;
  } else if (mode === "private") {
    items = (priv.data?.results ?? []).map((t) => ({
      id: `p-${t.id}`,
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
    }));
    isLoading = priv.isLoading; isError = priv.isError;
  } else {
    items = (bto.data?.results ?? []).map((r) => ({
      id: `b-${r.id}`,
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
    }));
    isLoading = bto.isLoading; isError = bto.isError;
  }

  return { items, blocks, isLoading, isError, sgd };
}
