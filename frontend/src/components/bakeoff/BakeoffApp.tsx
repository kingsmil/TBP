import { useEffect, useMemo, useState } from "react";
import "./bakeoff.css";
import { Undo2 } from "lucide-react";
import type { SearchFilters } from "../../types";
import { MAP_SEARCH_LIMIT } from "../../lib/mapConfig";
import { setRedesign } from "../../lib/uiVariant";
import type { Mode } from "./types";
import { useListings } from "./useListings";
import { useIsDesktop } from "./useMediaQuery";
import { type ShellProps, CompareBar } from "./shell";
import LayoutFloatingGlass from "./LayoutFloatingGlass";

function loadSet(key: string): Set<string> {
  try {
    const raw = localStorage.getItem(key);
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch { return new Set(); }
}
function saveSet(key: string, set: Set<string>) {
  try { localStorage.setItem(key, JSON.stringify([...set])); } catch { /* ignore */ }
}

/** The "Floating Glass" redesign shell (full-screen map + floating UI). Owns
 *  shared state + live data. Mounted opt-in (?ui=on) while it's built out. */
export default function BakeoffApp() {
  const [mode, setMode] = useState<Mode>("resale");
  const [filters, setFilters] = useState<SearchFilters>({ limit: MAP_SEARCH_LIMIT });
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [savedIds, setSavedIds] = useState<Set<string>>(() => loadSet("hdb_saved"));
  const [compareIds, setCompareIds] = useState<Set<string>>(() => loadSet("hdb_compare"));

  // Persist saved + compare locally so they survive reloads (real persistence;
  // account sync can layer on later via the saved-state APIs).
  useEffect(() => saveSet("hdb_saved", savedIds), [savedIds]);
  useEffect(() => saveSet("hdb_compare", compareIds), [compareIds]);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const isDesktop = useIsDesktop();

  const { items: allItems, blocks, isLoading, isError } = useListings(mode, filters);

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return allItems;
    return allItems.filter((it) =>
      it.title.toLowerCase().includes(q) || it.subtitle.toLowerCase().includes(q));
  }, [allItems, query]);

  const toggle = (set: React.Dispatch<React.SetStateAction<Set<string>>>) => (id: string) =>
    set((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const props: ShellProps = {
    mode, setMode, filters, setFilters, query, setQuery,
    items, blocks, isLoading, isError,
    selectedId, setSelectedId,
    savedIds, toggleSave: toggle(setSavedIds),
    compareIds, toggleCompare: toggle(setCompareIds),
    hoveredId, setHoveredId,
    filterOpen, setFilterOpen, isDesktop,
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <LayoutFloatingGlass {...props} />
      <CompareBar saved={savedIds.size} comparing={compareIds.size} />
      <button type="button" onClick={() => setRedesign(false)}
        title="Back to the classic app"
        className="bo-glass fixed bottom-4 right-4 z-[3000] flex items-center gap-2 rounded-full px-4 py-2.5 text-sm font-semibold sm:bottom-6 sm:right-6">
        <Undo2 className="h-4 w-4" /> Classic
      </button>
    </div>
  );
}
