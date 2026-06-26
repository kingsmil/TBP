import { useState } from "react";
import { SlidersHorizontal, ChevronUp, ChevronDown } from "lucide-react";
import { MODE_META } from "./types";
import ModeSwitch from "./ModeSwitch";
import FilterSheet from "./FilterSheet";
import BakeoffMap from "./BakeoffMap";
import DetailCard from "./DetailCard";
import { type ShellProps, SearchBar, ResultsCount, CardList } from "./shell";

type Snap = "peek" | "half" | "full";
const NEXT: Record<Snap, Snap> = { peek: "half", half: "full", full: "peek" };
const HEIGHT: Record<Snap, string> = { peek: "h-20", half: "h-[48%]", full: "h-[88%]" };

/** Variant C — Immersive Explorer. Full-screen map + price pins; floating glass
 *  panel (desktop) / draggable bottom sheet (mobile). Airbnb-style. */
export default function LayoutMapFirst(p: ShellProps) {
  const [snap, setSnap] = useState<Snap>("half");
  const selected = p.items.find((i) => i.id === p.selectedId) ?? null;

  return (
    <div className="fixed inset-0">
      <BakeoffMap items={p.items} selectedId={p.selectedId} hoveredId={p.hoveredId} onSelect={p.setSelectedId} />

      {/* Floating top: search + mode + filters */}
      <div className="bo-fade-up pointer-events-none absolute inset-x-0 top-0 z-[1000] p-3 sm:p-4">
        <div className="mx-auto flex max-w-2xl items-center gap-2 sm:ml-[21rem]">
          <div className="bo-glass pointer-events-auto flex flex-1 items-center rounded-full px-2 py-1.5">
            <SearchBar value={p.query} onChange={p.setQuery} placeholder={`Search ${MODE_META[p.mode].label}…`} />
          </div>
          <button type="button" onClick={() => p.setFilterOpen(true)}
            className="bo-glass pointer-events-auto flex h-11 w-11 items-center justify-center rounded-full">
            <SlidersHorizontal className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Desktop floating panel (left) */}
      <div className="pointer-events-none absolute left-0 top-0 z-[900] hidden h-full p-3 sm:block">
        <div className="bo-glass pointer-events-auto flex h-full w-80 flex-col overflow-hidden rounded-2xl">
          <div className="flex items-center justify-between gap-2 border-b border-border/60 px-3 py-2.5">
            <ModeSwitch mode={p.mode} onChange={p.setMode} size="sm" />
          </div>
          <div className="px-3 py-2"><ResultsCount n={p.items.length} mode={p.mode} /></div>
          <div className="bo-stagger min-h-0 flex-1 space-y-2 overflow-y-auto px-3 pb-3"
            onMouseLeave={() => p.setHoveredId(null)}>
            <CardList p={p} variant="c" />
          </div>
        </div>
      </div>

      {/* Mobile draggable bottom sheet */}
      <div className={`bo-glass absolute inset-x-0 bottom-0 z-[950] flex flex-col rounded-t-2xl transition-[height] duration-300 sm:hidden ${HEIGHT[snap]}`}>
        <button type="button" onClick={() => setSnap((s) => NEXT[s])} className="flex w-full flex-col items-center gap-1 py-2">
          <span className="h-1 w-10 rounded-full bg-muted-foreground/40" />
          <span className="flex items-center gap-1.5 text-sm font-semibold">
            {snap === "full" ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
            {p.items.length} {MODE_META[p.mode].label} homes
          </span>
        </button>
        <div className="flex items-center justify-center pb-2"><ModeSwitch mode={p.mode} onChange={p.setMode} size="sm" /></div>
        {snap !== "peek" && (
          <div className="bo-stagger min-h-0 flex-1 space-y-2 overflow-y-auto px-3 pb-6"><CardList p={p} variant="c" /></div>
        )}
      </div>

      {/* Floating detail card */}
      {selected && (
        <div className="pointer-events-none absolute bottom-24 left-1/2 z-[1100] -translate-x-1/2 sm:bottom-4 sm:left-[22rem] sm:translate-x-0">
          <DetailCard item={selected} saved={p.savedIds.has(selected.id)} comparing={p.compareIds.has(selected.id)}
            onClose={() => p.setSelectedId(null)} onSave={() => p.toggleSave(selected.id)} onCompare={() => p.toggleCompare(selected.id)} />
        </div>
      )}

      <FilterSheet filters={p.filters} onChange={p.setFilters} asSheet open={p.filterOpen} onClose={() => p.setFilterOpen(false)} />
    </div>
  );
}
