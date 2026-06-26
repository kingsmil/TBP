import { useState } from "react";
import { SlidersHorizontal, ChevronUp, ChevronDown } from "lucide-react";
import { MODE_META } from "./types";
import ModeSwitch from "./ModeSwitch";
import FilterSheet from "./FilterSheet";
import MapPane from "./MapPane";
import { type ShellProps, SearchBar, ResultsCount, CardList } from "./shell";

/** Variant C — Map Explorer. Split map+list (desktop); map + bottom sheet (mobile).
 *  Modes without coordinates (BTO/Private) gracefully fall back to a list. */
export default function LayoutMapFirst(p: ShellProps) {
  const [sheetOpen, setSheetOpen] = useState(true);
  const hasMap = p.mode === "resale";

  const header = (
    <div className="flex items-center gap-2 border-b border-border bg-card/95 px-4 py-2.5 backdrop-blur">
      <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-xs font-bold text-primary-foreground">H</div>
      <SearchBar value={p.query} onChange={p.setQuery} placeholder={`Search ${MODE_META[p.mode].label}…`} />
      <button type="button" onClick={() => p.setFilterOpen(true)}
        className="flex h-11 w-11 items-center justify-center rounded-full border border-border bg-card hover:bg-muted">
        <SlidersHorizontal className="h-4 w-4" />
      </button>
    </div>
  );

  const modeRow = (
    <div className="flex items-center justify-between px-4 py-2">
      <ModeSwitch mode={p.mode} onChange={p.setMode} size="sm" />
      <ResultsCount n={p.items.length} mode={p.mode} />
    </div>
  );

  // Modes without a map (or desktop list-only) → simple list-primary screen.
  if (!hasMap) {
    return (
      <div className="min-h-screen pb-24">
        {header}{modeRow}
        <div className="mx-auto max-w-3xl px-4"><CardList p={p} variant="c" /></div>
        <FilterSheet filters={p.filters} onChange={p.setFilters} asSheet open={p.filterOpen} onClose={() => p.setFilterOpen(false)} />
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col">
      {header}
      {/* Desktop: split list | map */}
      <div className="hidden min-h-0 flex-1 sm:flex">
        <div className="flex w-[44%] max-w-xl flex-col border-r border-border">
          {modeRow}
          <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-6"><CardList p={p} variant="c" /></div>
        </div>
        <div className="min-w-0 flex-1">
          <MapPane blocks={p.blocks} selectedId={p.selectedId} onSelectBlock={p.setSelectedId} />
        </div>
      </div>

      {/* Mobile: full map + draggable-style bottom sheet */}
      <div className="relative min-h-0 flex-1 sm:hidden">
        <MapPane blocks={p.blocks} selectedId={p.selectedId} onSelectBlock={p.setSelectedId} />
        <div className={`absolute inset-x-0 bottom-0 rounded-t-2xl border-t border-border bg-card shadow-2xl transition-[height] duration-300 ${
          sheetOpen ? "h-[55%]" : "h-14"
        }`}>
          <button type="button" onClick={() => setSheetOpen((o) => !o)}
            className="flex w-full items-center justify-center gap-2 py-3 text-sm font-semibold">
            {sheetOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
            {p.items.length} results
          </button>
          {sheetOpen && (
            <div className="h-[calc(100%-3rem)] overflow-y-auto px-3 pb-6"><CardList p={p} variant="c" /></div>
          )}
        </div>
      </div>

      <FilterSheet filters={p.filters} onChange={p.setFilters} asSheet open={p.filterOpen} onClose={() => p.setFilterOpen(false)} />
    </div>
  );
}
