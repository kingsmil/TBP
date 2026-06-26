import { useState } from "react";
import { SlidersHorizontal, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { MODE_META } from "./types";
import ModeSwitch from "./ModeSwitch";
import FilterSheet from "./FilterSheet";
import BakeoffMap from "./BakeoffMap";
import DetailPanel from "./DetailPanel";
import { type ShellProps, SearchBar, ResultsCount, CardList } from "./shell";

/** Floating Glass — full-screen map canvas; frosted panels float on top. */
export default function LayoutFloatingGlass(p: ShellProps) {
  const [railOpen, setRailOpen] = useState(true);
  const selected = p.items.find((i) => i.id === p.selectedId) ?? null;

  return (
    <div className="fixed inset-0">
      {/* Map canvas */}
      <BakeoffMap items={p.items} selectedId={p.selectedId} onSelect={p.setSelectedId} />

      {/* Top floating controls */}
      <div className="bo-fade-up pointer-events-none absolute inset-x-0 top-0 z-[1000] p-3 sm:p-4">
        <div className="mx-auto flex max-w-3xl flex-col gap-2">
          <div className="pointer-events-auto flex items-center gap-2">
            <div className="bo-glass flex flex-1 items-center gap-2 rounded-full px-2 py-1.5">
              <SearchBar value={p.query} onChange={p.setQuery} placeholder={`Search ${MODE_META[p.mode].label}…`} />
            </div>
            <button type="button" onClick={() => p.setFilterOpen(true)}
              className="bo-glass flex h-11 items-center gap-2 rounded-full px-4 text-sm font-semibold">
              <SlidersHorizontal className="h-4 w-4" /> <span className="hidden sm:inline">Filters</span>
            </button>
          </div>
          <div className="pointer-events-auto flex justify-center">
            <ModeSwitch mode={p.mode} onChange={p.setMode} size="sm" />
          </div>
        </div>
      </div>

      {/* Desktop results rail (left) */}
      <div className={`pointer-events-none absolute left-0 top-0 z-[900] hidden h-full p-3 pt-28 sm:block`}>
        <div className={`bo-glass pointer-events-auto flex h-full flex-col overflow-hidden rounded-2xl transition-[width] duration-300 ${railOpen ? "w-80" : "w-12"}`}>
          <div className="flex items-center justify-between px-3 py-2">
            {railOpen && <ResultsCount n={p.items.length} mode={p.mode} />}
            <button type="button" onClick={() => setRailOpen((o) => !o)} className="rounded-md p-1 hover:bg-muted">
              {railOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
            </button>
          </div>
          {railOpen && (
            <div className="bo-stagger min-h-0 flex-1 space-y-2 overflow-y-auto px-3 pb-3"
              onMouseLeave={() => p.setHoveredId(null)}>
              <CardList p={p} />
            </div>
          )}
        </div>
      </div>

      {/* Mobile results sheet (peek) */}
      <MobileSheet p={p} />

      {/* Detail panel (self-positioning: right rail on desktop, sheet on mobile) */}
      {selected && (
        <DetailPanel item={selected} saved={p.savedIds.has(selected.id)} comparing={p.compareIds.has(selected.id)}
          onClose={() => p.setSelectedId(null)} onSave={() => p.toggleSave(selected.id)} onCompare={() => p.toggleCompare(selected.id)} />
      )}

      <FilterSheet filters={p.filters} onChange={p.setFilters} asSheet open={p.filterOpen} onClose={() => p.setFilterOpen(false)} />
    </div>
  );
}

function MobileSheet({ p }: { p: ShellProps }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`bo-glass absolute inset-x-0 bottom-0 z-[950] rounded-t-2xl transition-[height] duration-300 sm:hidden ${open ? "h-[60%]" : "h-16"}`}>
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-center gap-2 py-4 text-sm font-semibold">
        <span className="h-1 w-10 rounded-full bg-muted-foreground/40" />
      </button>
      <div className="-mt-2 px-4 pb-2 text-center text-sm font-semibold"><ResultsCount n={p.items.length} mode={p.mode} /></div>
      {open && <div className="bo-stagger h-[calc(100%-5rem)] space-y-2 overflow-y-auto px-3 pb-6"><CardList p={p} /></div>}
    </div>
  );
}
