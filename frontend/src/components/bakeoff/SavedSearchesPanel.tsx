import { useEffect } from "react";
import { Bell, X, Trash2, Plus, Search } from "lucide-react";
import type { SearchFilters } from "../../types";
import type { Mode } from "./types";
import { MODE_META } from "./types";

export interface SavedSearch {
  id: string;
  name: string;
  modes: Mode[];
  filters: SearchFilters;
  count: number; // result count when last saved/seen — baseline for "new"
}

/** Human summary of a search's modes + filters. */
export function describeSearch(modes: Mode[], f: SearchFilters): string {
  const parts: string[] = [modes.map((m) => MODE_META[m].label).join(" + ")];
  if (f.flat_type) parts.push(f.flat_type);
  if (f.property_type) parts.push(f.property_type);
  if (f.town) parts.push(f.town);
  if (f.max_price) parts.push(`≤ $${Math.round(f.max_price / 1000)}k`);
  if (f.max_psf) parts.push(`≤ $${f.max_psf} psf`);
  if (f.max_mrt_distance_m) parts.push(`${Math.round(f.max_mrt_distance_m / 80)} min MRT`);
  if (f.min_schools_within_1km) parts.push("near schools");
  return parts.join(" · ");
}

interface Props {
  searches: SavedSearch[];
  liveCount: number;          // current result count (for the "+N new" hint on apply)
  onApply: (s: SavedSearch) => void;
  onRemove: (id: string) => void;
  onSaveCurrent: () => void;
  onClose: () => void;
}

export default function SavedSearchesPanel({ searches, onApply, onRemove, onSaveCurrent, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="bo-glass flex max-h-[85vh] w-full max-w-md flex-col overflow-hidden rounded-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <div className="flex items-center gap-2">
            <Bell className="h-4 w-4 text-primary" />
            <h2 className="text-base font-bold">Saved searches</h2>
            <span className="text-xs text-muted-foreground">({searches.length})</span>
          </div>
          <button type="button" onClick={onClose} className="rounded-md p-1 hover:bg-muted"><X className="h-4 w-4" /></button>
        </div>

        <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto p-4">
          <button type="button" onClick={onSaveCurrent}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-primary/50 bg-primary/5 py-2.5 text-sm font-semibold text-primary hover:bg-primary/10">
            <Plus className="h-4 w-4" /> Save current search
          </button>

          {searches.length === 0 && (
            <p className="px-1 pt-1 text-center text-xs text-muted-foreground">
              Save a filter set to quickly re-run it later — and see what's new since you last looked.
            </p>
          )}

          {searches.map((s) => (
            <div key={s.id}
              className="group relative rounded-2xl border border-border bg-card/70 p-3 transition-colors hover:border-primary/40">
              <button type="button" onClick={() => onApply(s)} className="block w-full pr-7 text-left">
                <div className="truncate text-sm font-semibold">{s.name}</div>
                <div className="mt-0.5 truncate text-[11px] text-muted-foreground">{describeSearch(s.modes, s.filters)}</div>
                <div className="mt-1.5 flex items-center gap-1.5 text-xs text-primary">
                  <Search className="h-3.5 w-3.5" /> Run search
                  <span className="text-muted-foreground">· {s.count.toLocaleString()} when saved</span>
                </div>
              </button>
              <button type="button" onClick={() => onRemove(s.id)} title="Remove"
                className="absolute right-1.5 top-1.5 flex h-7 w-7 items-center justify-center rounded-full bg-card/90 text-muted-foreground opacity-0 shadow-sm transition-opacity hover:text-red-600 group-hover:opacity-100">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
