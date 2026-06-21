import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { TrendingUp, MapPin, Building2 } from "lucide-react";
import { getRegionRankings, getBlockRankings } from "../lib/api";
import type { BlockRankingRow } from "../types";

interface Props {
  /** Select a block on the map when a block row is clicked. */
  onSelectBlock: (blockId: number) => void;
}

function cagr(v: number | null) {
  return v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

function cagrColor(v: number | null) {
  if (v == null) return "text-muted-foreground";
  if (v >= 5) return "text-emerald-600";
  if (v >= 0) return "text-foreground";
  return "text-red-600";
}

export default function InfoPanel({ onSelectBlock }: Props) {
  const [view, setView] = useState<"regions" | "blocks">("regions");

  const regions = useQuery({
    queryKey: ["region-rankings"],
    queryFn: () => getRegionRankings(30),
    staleTime: 1000 * 60 * 30,
  });
  const blocks = useQuery({
    queryKey: ["block-rankings"],
    queryFn: () => getBlockRankings(40),
    staleTime: 1000 * 60 * 30,
    enabled: view === "blocks",
  });

  const window =
    regions.data?.results[0] != null
      ? `${regions.data.results[0].year_start}–${regions.data.results[0].year_end}`
      : null;
  const computedAt = regions.data?.computed_at
    ? new Date(regions.data.computed_at).toLocaleDateString()
    : null;

  const notReady =
    regions.isError ||
    (regions.data != null && regions.data.count === 0);

  return (
    <div className="space-y-3 px-5 py-4">
      <div>
        <h2 className="flex items-center gap-1.5 text-sm font-semibold">
          <TrendingUp className="h-4 w-4" /> Appreciation rankings
        </h2>
        <p className="text-xs text-muted-foreground">
          Ranked by annualised resale-price growth (CAGR){window ? ` over ${window}` : ""}.
        </p>
      </div>

      {notReady ? (
        <div className="rounded-md border border-dashed border-border bg-muted/40 p-3 text-xs text-muted-foreground">
          Rankings haven't been generated yet. Run{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-[10px]">
            python -m app.analysis.build_rankings
          </code>{" "}
          on the server (needs live PostGIS data).
        </div>
      ) : (
        <>
          {/* Regions / Blocks toggle */}
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setView("regions")}
              className={`flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-semibold transition-colors ${
                view === "regions"
                  ? "bg-primary text-primary-foreground"
                  : "border border-border bg-card text-foreground hover:bg-muted"
              }`}
            >
              <MapPin className="h-3.5 w-3.5" /> Regions
            </button>
            <button
              type="button"
              onClick={() => setView("blocks")}
              className={`flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-semibold transition-colors ${
                view === "blocks"
                  ? "bg-primary text-primary-foreground"
                  : "border border-border bg-card text-foreground hover:bg-muted"
              }`}
            >
              <Building2 className="h-3.5 w-3.5" /> Blocks
            </button>
          </div>

          {view === "regions" ? (
            <div className="space-y-1.5">
              {regions.isLoading && <p className="text-xs text-muted-foreground">Loading…</p>}
              {regions.data?.results.map((r) => (
                <div
                  key={r.planning_area_id}
                  className="flex items-center gap-2.5 rounded-md border border-border bg-card px-2.5 py-2"
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-bold text-primary">
                    {r.rank}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-xs font-semibold">{r.name ?? `Area ${r.planning_area_id}`}</div>
                    <div className="truncate text-[10px] text-muted-foreground">
                      {r.region ?? ""}{r.block_count ? ` · ${r.block_count} blocks` : ""}
                    </div>
                  </div>
                  <span className={`shrink-0 text-right text-sm font-bold tabular-nums ${cagrColor(r.cagr_pct)}`}>
                    {cagr(r.cagr_pct)}
                    <span className="block text-[9px] font-normal uppercase tracking-wide text-muted-foreground">CAGR/yr</span>
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-1.5">
              {blocks.isLoading && <p className="text-xs text-muted-foreground">Loading…</p>}
              {blocks.data?.results.map((b: BlockRankingRow) => (
                <button
                  key={b.block_id}
                  type="button"
                  onClick={() => onSelectBlock(b.block_id)}
                  className="flex w-full items-center gap-2.5 rounded-md border border-border bg-card px-2.5 py-2 text-left hover:bg-muted"
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-bold text-primary">
                    {b.rank}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-xs font-semibold">{b.block_number} {b.street_name}</div>
                    <div className="truncate text-[10px] text-muted-foreground">{b.town}</div>
                  </div>
                  <span className={`shrink-0 text-right text-sm font-bold tabular-nums ${cagrColor(b.cagr_pct)}`}>
                    {cagr(b.cagr_pct)}
                    <span className="block text-[9px] font-normal uppercase tracking-wide text-muted-foreground">CAGR/yr</span>
                  </span>
                </button>
              ))}
            </div>
          )}

          {computedAt && (
            <p className="pt-1 text-[10px] text-muted-foreground">
              Last updated {computedAt}. Not financial advice.
            </p>
          )}
        </>
      )}
    </div>
  );
}
