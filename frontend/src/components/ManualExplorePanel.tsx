import FilterPanel from "./FilterPanel";
import EstateComparison from "./EstateComparison";
import PsfTrendChart from "./PsfTrendChart";
import StatCard from "./StatCard";
import { formatPsf, formatSGD } from "../lib/format";
import type { ComparisonResponse, EstateAnalytics, SearchFilters, SearchResponse } from "../types";

interface Props {
  filters: SearchFilters;
  onChangeFilters: (next: SearchFilters) => void;
  search: SearchResponse | undefined;
  estate: EstateAnalytics | undefined;
  comparison: ComparisonResponse | undefined;
  loading: {
    search: boolean;
    estate: boolean;
    comparison: boolean;
  };
}

export default function ManualExplorePanel({
  filters,
  onChangeFilters,
  search,
  estate,
  comparison,
  loading,
}: Props) {
  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="border-b border-border px-5 py-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-primary">Manual mode</p>
        <p className="mt-1 text-xs leading-snug text-muted-foreground">
          Browse the live dataset, tune filters, and compare estates directly against the map.
        </p>
      </div>

      <FilterPanel filters={filters} onChange={onChangeFilters} />

      <div className="grid grid-cols-2 gap-2 border-y border-border px-4 py-4">
        <StatCard
          label="Matches"
          value={String(search?.count ?? 0)}
          isLoading={loading.search}
        />
        <StatCard
          label="Median PSF"
          value={formatPsf(estate?.metrics.median_psf ?? null)}
          hint="estate avg"
          isLoading={loading.estate}
        />
        <StatCard
          label="Median Price"
          value={formatSGD(estate?.metrics.median_price ?? null)}
          isLoading={loading.estate}
        />
        <StatCard
          label="Growth"
          value={estate?.metrics.growth_pct != null ? `${estate.metrics.growth_pct}%` : "—"}
          isLoading={loading.estate}
        />
      </div>

      <div className="border-b border-border px-5 py-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          PSF Trend
        </p>
        <PsfTrendChart series={estate?.psf_over_time ?? []} />
      </div>

      <div className="min-h-0 flex-1 px-5 py-4">
        <div className="mb-3 flex items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Estate Comparison
          </p>
          {loading.comparison && (
            <p className="text-[10px] text-muted-foreground">Loading live data…</p>
          )}
        </div>
        <EstateComparison rows={comparison?.estates ?? []} />
      </div>
    </div>
  );
}
