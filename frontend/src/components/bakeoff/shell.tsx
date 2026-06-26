import { Search, Heart, GitCompareArrows } from "lucide-react";
import type { SearchFilters } from "../../types";
import type { CardItem, Mode } from "./types";
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

/** Sticky bottom bar summarising saved + compare selections. */
export function CompareBar({ saved, comparing }: { saved: number; comparing: number }) {
  if (saved === 0 && comparing === 0) return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-[1500] flex justify-center p-3 sm:bottom-6">
      <div className="pointer-events-auto flex items-center gap-4 rounded-full border border-border bg-card/95 px-5 py-2.5 text-sm shadow-lg backdrop-blur">
        <span className="flex items-center gap-1.5"><Heart className="h-4 w-4 text-primary" /> {saved} saved</span>
        <span className="h-4 w-px bg-border" />
        <span className="flex items-center gap-1.5"><GitCompareArrows className="h-4 w-4 text-primary" /> {comparing} to compare</span>
      </div>
    </div>
  );
}
