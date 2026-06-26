import { useMemo, useState } from "react";
import type { UiVariant } from "../../lib/uiVariant";
import type { SearchFilters } from "../../types";
import { MAP_SEARCH_LIMIT } from "../../lib/mapConfig";
import type { Mode } from "./types";
import { useListings } from "./useListings";
import { useIsDesktop } from "./useMediaQuery";
import { type ShellProps, CompareBar } from "./shell";
import VariantPicker from "./VariantPicker";
import LayoutCalm from "./LayoutCalm";
import LayoutPremium from "./LayoutPremium";
import LayoutMapFirst from "./LayoutMapFirst";

/** Bake-off shell. Owns shared state, fetches real data, renders one of three
 *  candidate layouts. Self-contained — delete this folder to remove. */
export default function BakeoffApp({ variant }: { variant: UiVariant }) {
  const [mode, setMode] = useState<Mode>("resale");
  const [filters, setFilters] = useState<SearchFilters>({ limit: MAP_SEARCH_LIMIT });
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());
  const [compareIds, setCompareIds] = useState<Set<string>>(new Set());
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

  const Layout = variant === "b" ? LayoutPremium : variant === "c" ? LayoutMapFirst : LayoutCalm;

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Layout {...props} />
      <CompareBar saved={savedIds.size} comparing={compareIds.size} />
      <VariantPicker current={variant} />
    </div>
  );
}
