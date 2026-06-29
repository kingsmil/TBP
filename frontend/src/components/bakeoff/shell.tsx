import { Search, Heart, GitCompareArrows } from "lucide-react";
import type { SearchFilters } from "../../types";
import type { CardItem, Mode, Weights } from "./types";
import type { BlockSummary } from "../../types";
import PropertyCard from "./PropertyCard";

/** Everything a layout needs. BakeoffApp builds this; each variant arranges it. */
export interface ShellProps {
  modes: Mode[];
  toggleMode: (m: Mode) => void;
  combine: boolean;
  setCombine: (on: boolean) => void;
  filters: SearchFilters;
  setFilters: (f: SearchFilters) => void;
  query: string;
  setQuery: (q: string) => void;
  items: CardItem[];
  blocks: BlockSummary[];
  isLoading: boolean;
  isError: boolean;
  selectedId: string | null;
  setSelectedId: (id: string | null) => void;
  savedIds: Set<string>;
  toggleSave: (id: string) => void;
  compareIds: Set<string>;
  toggleCompare: (id: string) => void;
  hoveredId: string | null;
  setHoveredId: (id: string | null) => void;
  filterOpen: boolean;
  setFilterOpen: (open: boolean) => void;
  isDesktop: boolean;
  authEmail: string | null;
  onAccount: () => void;
  savedPlaces: { label: string; lat: number; lon: number }[];
  sort: string;
  setSort: (s: string) => void;
  weights: Weights;
  setWeights: (w: Weights) => void;
  colorByScore: boolean;
  setColorByScore: (on: boolean) => void;
  onSaved: () => void;
  onSavedHomes: () => void;
  onInsights: () => void;
  onBtoData: () => void;
  onHelp: () => void;
  onAfford: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

const SORT_OPTIONS: { value: string; label: string; modes: Mode[] }[] = [
  { value: "match", label: "Recommended", modes: ["resale"] },
  { value: "price-asc", label: "Price: low to high", modes: ["resale", "private"] },
  { value: "price-desc", label: "Price: high to low", modes: ["resale", "private"] },
  { value: "psf-asc", label: "PSF: low to high", modes: ["resale", "private"] },
  { value: "psf-desc", label: "PSF: high to low", modes: ["resale", "private"] },
  { value: "newest", label: "Newest", modes: ["resale", "private", "bto"] },
  { value: "area-desc", label: "Largest area", modes: ["private"] },
  { value: "appreciation", label: "Best appreciation", modes: ["resale"] },
];

/** Sort options valid for the active mode(s) — hides resale-only sorts in BTO/Private. */
export function sortOptionsFor(modes: Mode[]) {
  return SORT_OPTIONS.filter((o) => o.modes.some((m) => modes.includes(m)));
}

export function SortSelect({ value, onChange, modes }: { value: string; onChange: (s: string) => void; modes: Mode[] }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}
      aria-label="Sort results"
      className="rounded-full border border-border bg-card px-2.5 py-1 text-xs font-medium outline-none">
      {sortOptionsFor(modes).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

export function SearchBar({ value, onChange, placeholder }: {
  value: string; onChange: (v: string) => void; placeholder: string;
}) {
  return (
    <div className="relative flex-1">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <input
        value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
        className="h-11 w-full rounded-full border border-border bg-card pl-10 pr-4 text-sm outline-none ring-primary/30 focus:ring-2"
      />
    </div>
  );
}

export function ResultsCount({ n }: { n: number }) {
  return <p className="text-sm text-muted-foreground"><span className="font-semibold text-foreground">{n.toLocaleString()}</span> results</p>;
}

export function SkeletonList({ count = 5, grid = false }: { count?: number; grid?: boolean }) {
  return (
    <div className={grid ? "grid gap-3 sm:grid-cols-2 xl:grid-cols-3" : "space-y-3"}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="animate-pulse rounded-2xl border border-border bg-card p-4">
          <div className="mb-3 h-4 w-2/3 rounded bg-muted" />
          <div className="mb-2 h-3 w-1/3 rounded bg-muted" />
          <div className="h-6 w-1/2 rounded bg-muted" />
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ error }: { error?: boolean }) {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-10 text-center">
      <p className="text-sm font-medium">{error ? "Couldn't load results" : "No homes match your filters"}</p>
      <p className="mt-1 text-xs text-muted-foreground">{error ? "Is the API running?" : "Try widening your filters."}</p>
    </div>
  );
}

/** Shared result list, wired to ShellProps. */
export function CardList({ p, grid = false }: { p: ShellProps; grid?: boolean }) {
  if (p.isLoading) return <SkeletonList grid={grid} />;
  if (p.isError || p.items.length === 0) return <EmptyState error={p.isError} />;
  const LIST_CAP = 150; // map shows everything (clustered); the list stays snappy
  const shown = p.items.slice(0, LIST_CAP);
  const extra = p.items.length - shown.length;
  return (
    <div className={grid ? "grid gap-3 sm:grid-cols-2 xl:grid-cols-3" : "space-y-3"}>
      {shown.map((it) => (
        <PropertyCard
          key={it.id} item={it}
          selected={p.selectedId === it.id}
          saved={p.savedIds.has(it.id)}
          comparing={p.compareIds.has(it.id)}
          onSelect={() => p.setSelectedId(p.selectedId === it.id ? null : it.id)}
          onSave={() => p.toggleSave(it.id)}
          onCompare={() => p.toggleCompare(it.id)}
          onHover={(h) => p.setHoveredId(h ? it.id : null)}
        />
      ))}
      {extra > 0 && (
        <p className="px-1 py-2 text-center text-xs text-muted-foreground">
          +{extra.toLocaleString()} more on the map — zoom in to explore
        </p>
      )}
    </div>
  );
}

/** Sticky bottom bar summarising saved + compare; opens saved homes / compare. */
export function CompareBar({ saved, comparing, onSaved, onCompare }: {
  saved: number; comparing: number; onSaved: () => void; onCompare: () => void;
}) {
  if (saved === 0 && comparing === 0) return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-[1500] flex justify-center p-3 sm:bottom-6">
      <div className="bo-glass pointer-events-auto flex items-center gap-3 rounded-full px-4 py-2 text-sm shadow-lg">
        <button type="button" onClick={onSaved} disabled={saved === 0}
          className="flex items-center gap-1.5 rounded-full px-1 font-medium hover:text-primary disabled:opacity-60">
          <Heart className="h-4 w-4 text-primary" /> {saved} saved
        </button>
        <span className="h-4 w-px bg-border" />
        <button type="button" onClick={onCompare} disabled={comparing === 0}
          className="flex items-center gap-1.5 rounded-full bg-primary px-3 py-1.5 font-semibold text-primary-foreground disabled:opacity-50">
          <GitCompareArrows className="h-4 w-4" /> Compare{comparing > 0 ? ` (${comparing})` : ""}
        </button>
      </div>
    </div>
  );
}
