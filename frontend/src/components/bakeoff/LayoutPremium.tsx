import { useState } from "react";
import { Search, SlidersHorizontal, ChevronDown, ChevronUp } from "lucide-react";
import { MODE_META } from "./types";
import ModeSwitch from "./ModeSwitch";
import FilterSheet from "./FilterSheet";
import BakeoffMap from "./BakeoffMap";
import DetailCard from "./DetailCard";
import { type ShellProps, ResultsCount, CardList } from "./shell";

/** Variant B — Minimal Command. Almost-bare map; one floating command bar that
 *  expands into mode + filters + results, then collapses to pure map. */
export default function LayoutPremium(p: ShellProps) {
  const [expanded, setExpanded] = useState(true);
  const selected = p.items.find((i) => i.id === p.selectedId) ?? null;

  return (
    <div className="fixed inset-0">
      <BakeoffMap items={p.items} selectedId={p.selectedId} hoveredId={p.hoveredId} onSelect={p.setSelectedId} />

      {/* Centered command bar */}
      <div className="pointer-events-none absolute inset-x-0 top-0 z-[1000] flex justify-center p-3 sm:p-5">
        <div className="bo-glass bo-fade-up pointer-events-auto w-[min(96vw,560px)] overflow-hidden rounded-3xl">
          {/* Bar */}
          <div className="flex items-center gap-2 px-3 py-2">
            <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
            <input value={p.query} onChange={(e) => p.setQuery(e.target.value)}
              onFocus={() => setExpanded(true)}
              placeholder={`Search ${MODE_META[p.mode].label} homes…`}
              className="h-9 flex-1 bg-transparent text-sm outline-none" />
            <button type="button" onClick={() => p.setFilterOpen(true)} className="rounded-full p-2 hover:bg-muted">
              <SlidersHorizontal className="h-4 w-4" />
            </button>
            <button type="button" onClick={() => setExpanded((e) => !e)} className="rounded-full p-2 hover:bg-muted">
              {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
          </div>

          {/* Expanded panel */}
          {expanded && (
            <div className="border-t border-border/60">
              <div className="flex items-center justify-between px-3 py-2">
                <ModeSwitch mode={p.mode} onChange={p.setMode} size="sm" />
                <ResultsCount n={p.items.length} mode={p.mode} />
              </div>
              <div className="bo-stagger max-h-[60vh] space-y-2 overflow-y-auto px-3 pb-3"
                onMouseLeave={() => p.setHoveredId(null)}>
                <CardList p={p} variant="c" />
              </div>
            </div>
          )}
        </div>
      </div>

      {selected && (
        <div className="pointer-events-none absolute bottom-4 left-1/2 z-[1100] -translate-x-1/2">
          <DetailCard item={selected} saved={p.savedIds.has(selected.id)} comparing={p.compareIds.has(selected.id)}
            onClose={() => p.setSelectedId(null)} onSave={() => p.toggleSave(selected.id)} onCompare={() => p.toggleCompare(selected.id)} />
        </div>
      )}

      <FilterSheet filters={p.filters} onChange={p.setFilters} asSheet open={p.filterOpen} onClose={() => p.setFilterOpen(false)} />
    </div>
  );
}
