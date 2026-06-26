import { useState } from "react";
import { SlidersHorizontal, Map as MapIcon, List as ListIcon } from "lucide-react";
import { MODE_META } from "./types";
import ModeSwitch from "./ModeSwitch";
import FilterSheet from "./FilterSheet";
import MapPane from "./MapPane";
import { type ShellProps, SearchBar, ResultsCount, CardList } from "./shell";

/** Variant A — Calm Assistant. List-primary, quiet, companion map. */
export default function LayoutCalm(p: ShellProps) {
  const [mobileMap, setMobileMap] = useState(false);
  const showMap = p.mode === "resale";

  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-4 pb-24 pt-4 sm:px-6">
      {/* Header */}
      <header className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-xs font-bold text-primary-foreground">H</div>
            <span className="text-sm font-bold">HDB Match</span>
          </div>
          <ModeSwitch mode={p.mode} onChange={p.setMode} size="sm" />
        </div>
        <h1 className="text-xl font-bold tracking-tight sm:text-2xl">Find your next home in Singapore</h1>
        <p className="-mt-2 text-sm text-muted-foreground">{MODE_META[p.mode].blurb}</p>
        <div className="flex gap-2">
          <SearchBar value={p.query} onChange={p.setQuery} placeholder={`Search ${MODE_META[p.mode].label}…`} />
          <button type="button" onClick={() => p.setFilterOpen(true)}
            className="flex h-11 items-center gap-2 rounded-full border border-border bg-card px-4 text-sm font-semibold hover:bg-muted sm:hidden">
            <SlidersHorizontal className="h-4 w-4" /> Filters
          </button>
        </div>
      </header>

      {/* Body */}
      <div className="mt-5 flex flex-1 gap-6">
        {/* Desktop filter rail */}
        <aside className="hidden w-64 shrink-0 sm:block">
          <div className="sticky top-4">
            <FilterSheet filters={p.filters} onChange={p.setFilters} />
          </div>
        </aside>

        {/* Results */}
        <main className="min-w-0 flex-1">
          <div className="mb-3 flex items-center justify-between">
            <ResultsCount n={p.items.length} mode={p.mode} />
            {showMap && (
              <button type="button" onClick={() => setMobileMap((m) => !m)}
                className="flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-semibold hover:bg-muted sm:hidden">
                {mobileMap ? <><ListIcon className="h-3.5 w-3.5" /> List</> : <><MapIcon className="h-3.5 w-3.5" /> Map</>}
              </button>
            )}
          </div>
          {mobileMap && showMap ? (
            <div className="h-[70vh] overflow-hidden rounded-2xl border border-border sm:hidden">
              <MapPane blocks={p.blocks} selectedId={p.selectedId} onSelectBlock={p.setSelectedId} />
            </div>
          ) : (
            <CardList p={p} variant="a" />
          )}
        </main>

        {/* Desktop companion map */}
        {showMap && (
          <aside className="hidden w-[38%] max-w-md shrink-0 lg:block">
            <div className="sticky top-4 h-[calc(100vh-2rem)] overflow-hidden rounded-2xl border border-border">
              <MapPane blocks={p.blocks} selectedId={p.selectedId} onSelectBlock={p.setSelectedId} />
            </div>
          </aside>
        )}
      </div>

      <FilterSheet filters={p.filters} onChange={p.setFilters} asSheet open={p.filterOpen} onClose={() => p.setFilterOpen(false)} />
    </div>
  );
}
