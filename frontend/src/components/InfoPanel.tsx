import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { TrendingUp, MapPin, Building2 } from "lucide-react";
import { getRegionRankings, getBlockRankings } from "../lib/api";
import type { BlockRankingRow, RegionRankingRow } from "../types";

interface Props {
  /** Select a block on the map when a block row is clicked. */
  onSelectBlock: (blockId: number) => void;
}

type SortBy = "cagr" | "score";

interface Rankable {
  cagr_pct: number | null;
  appreciation_score: number | null;
}

function fmtCagr(v: number | null) {
  return v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

function cagrColor(v: number | null) {
  if (v == null) return "text-muted-foreground";
  if (v >= 5) return "text-emerald-600";
  if (v >= 0) return "text-foreground";
  return "text-red-600";
}

function scoreColor(v: number | null) {
  if (v == null) return "text-muted-foreground";
  if (v >= 66) return "text-emerald-600";
  if (v >= 40) return "text-foreground";
  return "text-amber-600";
}

function sortRows<T extends Rankable>(rows: T[], by: SortBy): T[] {
  const val = (r: T) => (by === "cagr" ? r.cagr_pct : r.appreciation_score) ?? -Infinity;
  return [...rows].sort((a, b) => val(b) - val(a));
}

function Headline({ row, by }: { row: Rankable; by: SortBy }) {
  if (by === "score") {
    return (
      <span className={`shrink-0 text-right text-sm font-bold tabular-nums ${scoreColor(row.appreciation_score)}`}>
        {row.appreciation_score == null ? "—" : Math.round(row.appreciation_score)}
        <span className="block text-[9px] font-normal uppercase tracking-wide text-muted-foreground">potential</span>
      </span>
    );
  }
  return (
    <span className={`shrink-0 text-right text-sm font-bold tabular-nums ${cagrColor(row.cagr_pct)}`}>
      {fmtCagr(row.cagr_pct)}
      <span className="block text-[9px] font-normal uppercase tracking-wide text-muted-foreground">CAGR/yr</span>
    </span>
  );
}

export default function InfoPanel({ onSelectBlock }: Props) {
  const [view, setView] = useState<"regions" | "blocks">("regions");
  const [sortBy, setSortBy] = useState<SortBy>("cagr");

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

  const first = regions.data?.results[0];
  const window = first ? `${first.year_start}–${first.year_end}` : null;
  const computedAt = regions.data?.computed_at
    ? new Date(regions.data.computed_at).toLocaleDateString()
    : null;
  const notReady = regions.isError || (regions.data != null && regions.data.count === 0);

  const tabBtn = (active: boolean) =>
    `flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-semibold transition-colors ${
      active ? "bg-primary text-primary-foreground" : "border border-border bg-card text-foreground hover:bg-muted"
    }`;
  const pill = (active: boolean) =>
    `rounded-md px-2 py-1 text-[11px] font-semibold transition-colors ${
      active ? "bg-primary text-primary-foreground" : "border border-border bg-card text-muted-foreground hover:bg-muted"
    }`;

  return (
    <div className="space-y-3 px-5 py-4">
      <div>
        <h2 className="flex items-center gap-1.5 text-sm font-semibold">
          <TrendingUp className="h-4 w-4" /> Appreciation rankings
        </h2>
        <p className="text-xs text-muted-foreground">
          {sortBy === "cagr"
            ? `Ranked by annualised resale-price growth (CAGR)${window ? ` over ${window}` : ""}.`
            : "Ranked by forward-looking appreciation potential (0–100)."}
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
          {/* Regions / Blocks */}
          <div className="grid grid-cols-2 gap-2">
            <button type="button" onClick={() => setView("regions")} className={tabBtn(view === "regions")}>
              <MapPin className="h-3.5 w-3.5" /> Regions
            </button>
            <button type="button" onClick={() => setView("blocks")} className={tabBtn(view === "blocks")}>
              <Building2 className="h-3.5 w-3.5" /> Blocks
            </button>
          </div>

          {/* Sort + legend */}
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Sort</span>
              <button type="button" onClick={() => setSortBy("cagr")} className={pill(sortBy === "cagr")}>Growth</button>
              <button type="button" onClick={() => setSortBy("score")} className={pill(sortBy === "score")}>Potential</button>
            </div>
            {sortBy === "cagr" && (
              <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500" />≥5%</span>
                <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-foreground/60" />0–5%</span>
                <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-500" />&lt;0%</span>
              </div>
            )}
          </div>

          {view === "regions" ? (
            <div className="space-y-1.5">
              {regions.isLoading && <p className="text-xs text-muted-foreground">Loading…</p>}
              {sortRows<RegionRankingRow>(regions.data?.results ?? [], sortBy).map((r, i) => (
                <div key={r.planning_area_id} className="flex items-center gap-2.5 rounded-md border border-border bg-card px-2.5 py-2">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-bold text-primary">
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-xs font-semibold">{r.name ?? `Area ${r.planning_area_id}`}</div>
                    <div className="truncate text-[10px] text-muted-foreground">
                      {r.region ?? ""}{r.block_count ? ` · ${r.block_count} blocks` : ""}
                    </div>
                  </div>
                  <Headline row={r} by={sortBy} />
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-1.5">
              {blocks.isLoading && <p className="text-xs text-muted-foreground">Loading…</p>}
              {sortRows<BlockRankingRow>(blocks.data?.results ?? [], sortBy).map((b, i) => (
                <button
                  key={b.block_id}
                  type="button"
                  onClick={() => onSelectBlock(b.block_id)}
                  className="flex w-full items-center gap-2.5 rounded-md border border-border bg-card px-2.5 py-2 text-left hover:bg-muted"
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-bold text-primary">
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-xs font-semibold">{b.block_number} {b.street_name}</div>
                    <div className="truncate text-[10px] text-muted-foreground">{b.town}</div>
                  </div>
                  <Headline row={b} by={sortBy} />
                </button>
              ))}
            </div>
          )}

          {computedAt && (
            <p className="pt-1 text-[10px] text-muted-foreground">
              Last updated {computedAt}. Heuristic estimate, not financial advice.
            </p>
          )}
        </>
      )}
    </div>
  );
}
