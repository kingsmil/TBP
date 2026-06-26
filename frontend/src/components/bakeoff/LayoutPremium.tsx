import { SlidersHorizontal } from "lucide-react";
import { MODE_META } from "./types";
import ModeSwitch from "./ModeSwitch";
import FilterSheet from "./FilterSheet";
import { type ShellProps, SearchBar, ResultsCount, CardList } from "./shell";

/** Variant B — Premium Cards. Card grid, insight tiles, polished, map as a tab. */
export default function LayoutPremium(p: ShellProps) {
  return (
    <div className="min-h-screen pb-24">
      {/* Gradient hero */}
      <div className="bg-gradient-to-b from-primary/10 to-transparent">
        <div className="mx-auto max-w-6xl px-4 pt-5 sm:px-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-xs font-bold text-primary-foreground">H</div>
              <span className="text-sm font-bold">HDB Match</span>
            </div>
            <ModeSwitch mode={p.mode} onChange={p.setMode} size="sm" />
          </div>
          <div className="py-6 text-center">
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Your next home, beautifully simple</h1>
            <p className="mt-1 text-sm text-muted-foreground">{MODE_META[p.mode].blurb}</p>
            <div className="mx-auto mt-4 flex max-w-xl gap-2">
              <SearchBar value={p.query} onChange={p.setQuery} placeholder={`Search ${MODE_META[p.mode].label}…`} />
              <button type="button" onClick={() => p.setFilterOpen(true)}
                className="flex h-11 items-center gap-2 rounded-full bg-primary px-4 text-sm font-semibold text-primary-foreground shadow-sm hover:bg-primary/90">
                <SlidersHorizontal className="h-4 w-4" /> <span className="hidden sm:inline">Filters</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mb-3 flex items-center justify-between">
          <ResultsCount n={p.items.length} mode={p.mode} />
        </div>
        <CardList p={p} variant="b" grid />
      </div>

      <FilterSheet filters={p.filters} onChange={p.setFilters} asSheet open={p.filterOpen} onClose={() => p.setFilterOpen(false)} />
    </div>
  );
}
