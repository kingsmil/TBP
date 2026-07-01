import { useState } from "react";
import { SlidersHorizontal, PanelLeftClose, PanelLeftOpen, Sparkles, X } from "lucide-react";
import AgentPanel from "./AgentPanel";
import AppMenu from "./AppMenu";
import ModeSwitch from "./ModeSwitch";
import FilterSheet from "./FilterSheet";
import BakeoffMap from "./BakeoffMap";
import DetailPanel from "./DetailPanel";
import LocationSearch from "./LocationSearch";
import PrioritiesControl from "./PrioritiesPanel";
import { type ShellProps, ResultsCount, CardList, SortSelect } from "./shell";

/** Floating Glass — full-screen map canvas; frosted panels float on top. */
export default function LayoutFloatingGlass(p: ShellProps) {
  const [railOpen, setRailOpen] = useState(true);
  const [showAgent, setShowAgent] = useState(false);
  const selected = p.items.find((i) => i.id === p.selectedId) ?? null;

  return (
    <div className="fixed inset-0 flex">
      {/* Desktop results rail — in-flow, so the map resizes around it. Rendered
          only on desktop so its 150-card list isn't built (hidden) on mobile. */}
      {p.isDesktop && (
      <aside className={`flex shrink-0 flex-col overflow-hidden border-r border-border bg-card transition-[width] duration-300 ${railOpen ? "w-[420px]" : "w-12"}`}>
        <div className="flex items-center justify-between px-3 py-2">
          {railOpen && <ResultsCount n={p.items.length} />}
          <button type="button" onClick={() => setRailOpen((o) => !o)}
            title={railOpen ? "Collapse list" : "Expand list"}
            className="rounded-md p-1 hover:bg-muted">
            {railOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
          </button>
        </div>
        {railOpen && (
          <>
            <div className="flex items-center gap-2 px-3 pb-2">
              <span className="text-[11px] text-muted-foreground">Sort</span>
              <SortSelect value={p.sort} onChange={p.setSort} modes={p.modes} />
            </div>
            <div className="bo-stagger bo-noscroll min-h-0 flex-1 space-y-2 overflow-y-auto px-3 pb-3"
              onMouseLeave={() => p.setHoveredId(null)}>
              <CardList p={p} />
            </div>
          </>
        )}
      </aside>
      )}

      {/* Map area (fills the rest) */}
      <div className="relative min-w-0 flex-1">
        <BakeoffMap items={p.items} selectedId={p.selectedId} onSelect={p.setSelectedId} fitKey={p.modes.join(",")} colorByScore={p.colorByScore} theme={p.theme} searchTarget={p.searchCenter} />

        {/* Top floating controls */}
        <div className="bo-fade-up pointer-events-none absolute inset-x-0 top-0 z-[1000] p-3 sm:p-4">
          <div className="mx-auto flex max-w-3xl flex-col gap-2">
            <div className="pointer-events-auto flex items-center gap-2">
              <LocationSearch value={p.query} onChange={p.setQuery}
                onPick={(lat, lon) => p.onPickLocation(lat, lon)} />
              <button type="button" onClick={() => p.setFilterOpen(true)}
                className="bo-glass flex h-11 items-center gap-2 rounded-full px-4 text-sm font-semibold">
                <SlidersHorizontal className="h-4 w-4" /> <span className="hidden sm:inline">Filters</span>
              </button>
              {/* Priorities / match score are resale-only, so only show them there. */}
              {p.modes.includes("resale") && (
                <PrioritiesControl weights={p.weights} setWeights={p.setWeights}
                  colorByScore={p.colorByScore} setColorByScore={p.setColorByScore} />
              )}
              <AppMenu {...p} />
            </div>
            <div className="pointer-events-auto flex justify-center gap-2">
              <ModeSwitch active={p.modes} onToggle={p.toggleMode} combine={p.combine} onCombine={p.setCombine} size="sm" />
              <button type="button" onClick={() => setShowAgent(true)}
                title="Open HomeOS Agent"
                className="bo-glass flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold text-primary">
                <Sparkles className="h-3.5 w-3.5" /> Agent
              </button>
            </div>
            {p.agentShortlistIds.length > 0 && (
              <div className="pointer-events-auto flex justify-center">
                <div className="bo-glass flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold">
                  <Sparkles className="h-3.5 w-3.5 text-primary" />
                  {p.agentShortlistIds.length} agent match{p.agentShortlistIds.length === 1 ? "" : "es"}
                  <button
                    type="button"
                    onClick={p.onClearAgentRecommendations}
                    className="rounded-full p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                    aria-label="Clear agent matches"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Mobile results sheet (peek) */}
        {!p.isDesktop && <MobileSheet p={p} />}
      </div>

      {/* Detail panel (fixed to viewport: right rail on desktop, sheet on mobile) */}
      {selected && (
        <DetailPanel item={selected} saved={p.savedIds.has(selected.id)} comparing={p.compareIds.has(selected.id)}
          savedPlaces={p.savedPlaces}
          caseId={p.activeCaseId ?? undefined}
          onClose={() => p.setSelectedId(null)} onSave={() => p.toggleSave(selected.id)} onCompare={() => p.toggleCompare(selected.id)} />
      )}

      <FilterSheet filters={p.filters} onChange={p.setFilters} modes={p.modes} asSheet open={p.filterOpen} onClose={() => p.setFilterOpen(false)} />
      <AgentPanel
        open={showAgent}
        onClose={() => setShowAgent(false)}
        onRecommendations={p.onAgentRecommendations}
        onSignInRequired={p.onSignInRequired}
        onUpgradeRequired={p.onUpgradeRequired}
      />
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
      <div className="-mt-2 flex items-center justify-center gap-2 px-4 pb-2 text-sm font-semibold">
        <ResultsCount n={p.items.length} />
        {open && <SortSelect value={p.sort} onChange={p.setSort} modes={p.modes} />}
      </div>
      {open && <div className="bo-stagger bo-noscroll h-[calc(100%-6rem)] space-y-2 overflow-y-auto px-3 pb-6"><CardList p={p} /></div>}
    </div>
  );
}
