import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  PanelLeftClose,
  PanelLeftOpen,
  SlidersHorizontal,
  BarChart2,
  Table2,
  TrendingUp,
} from "lucide-react";
import CasesPanel from "./components/CasesPanel";
import DirectTransitFilter from "./components/DirectTransitFilter";
import EstateComparison from "./components/EstateComparison";
import FilterPanel from "./components/FilterPanel";
import HomeOSDetailPanel from "./components/HomeOSDetailPanel";
import MapView from "./components/MapView";
import PipelinePanel from "./components/PipelinePanel";
import PsfTrendChart from "./components/PsfTrendChart";
import StatCard from "./components/StatCard";
import { Separator } from "./components/ui/separator";
import {
  chatInCase,
  getEstateAnalytics,
  getEstateComparison,
  investigateStream,
  refineStream,
  searchProperties,
} from "./lib/api";
import { formatPsf, formatSGD } from "./lib/format";
import type {
  AgentEvent,
  DirectTransitResponse,
  HomeOSCase,
  HomeOSCaseSummary,
  HomeOSAvatar,
  SearchFilters,
} from "./types";

const DEFAULT_ESTATE = 1;

type Mode = "ai" | "explore";
type RightPanel = "pipeline" | "block_detail";

function RailIcon({
  icon: Icon,
  label,
  onClick,
}: {
  icon: React.ElementType;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      className="group relative flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
    >
      <Icon className="h-4 w-4" />
      <span className="pointer-events-none absolute left-full ml-2 whitespace-nowrap rounded-md bg-popover border border-border px-2 py-1 text-xs text-popover-foreground shadow-md opacity-0 group-hover:opacity-100 transition-opacity z-50">
        {label}
      </span>
    </button>
  );
}

export default function App() {
  const [mode, setMode] = useState<Mode>("ai");

  // Shared
  const [filters, setFilters] = useState<SearchFilters>({ limit: 500 });
  const [directTransit, setDirectTransit] = useState<DirectTransitResponse | null>(null);
  const [selectedBlockId, setSelectedBlockId] = useState<number | null>(null);
  const [shortlistIds, setShortlistIds] = useState<number[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true); // explore mode only

  // AI mode
  const [cases, setCases] = useState<HomeOSCaseSummary[]>([]);
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [activeCaseFull, setActiveCaseFull] = useState<HomeOSCase | null>(null);
  const [streamingEvents, setStreamingEvents] = useState<AgentEvent[]>([]);
  const [chatChunks, setChatChunks] = useState("");
  const [rightPanel, setRightPanel] = useState<RightPanel>("pipeline");
  const [isStreaming, setIsStreaming] = useState(false);

  const search = useQuery({
    queryKey: ["search", filters],
    queryFn: () => searchProperties(filters),
  });
  const estate = useQuery({
    queryKey: ["estate", DEFAULT_ESTATE, filters.flat_type],
    queryFn: () => getEstateAnalytics(DEFAULT_ESTATE, filters.flat_type),
    enabled: mode === "explore",
  });
  const comparison = useQuery({
    queryKey: ["comparison", filters.flat_type],
    queryFn: () => getEstateComparison(undefined, filters.flat_type),
    enabled: mode === "explore",
  });

  const blocks = directTransit?.results ?? search.data?.results ?? [];
  const metrics = estate.data?.metrics;

  const _processStream = useCallback(async (
    gen: AsyncGenerator<AgentEvent>,
    caseId: string,
    profileText: string,
    createdAt: string,
    tempId: string,
  ) => {
    const accumulated: AgentEvent[] = [];
    let finalCaseId: string | null = null;
    let finalStatus: "done" | "refining" | "error" = "done";

    setIsStreaming(true);
    try {
      for await (const event of gen) {
        accumulated.push(event);
        setStreamingEvents([...accumulated]);

        // When search returns candidates, highlight them on the map immediately
        if (event.event === "agent_summary" && event.agent === "search" && event.data) {
          const ids = (event.data as Record<string, unknown>)["candidate_ids"] as number[] | undefined;
          if (ids?.length) setShortlistIds(ids);
        }

        if (event.event === "clarifying_question") {
          finalCaseId = event.case_id ?? caseId;
          finalStatus = "refining";
          setCases((prev) =>
            prev.map((c) =>
              c.case_id === tempId
                ? { ...c, case_id: finalCaseId!, status: "refining" }
                : c
            )
          );
        }

        if (event.event === "case_done") {
          finalCaseId = event.case_id ?? null;
          finalStatus = "done";
          const shortlist = event.shortlist ?? [];
          setShortlistIds(shortlist.map((r) => r.block_id));
          setCases((prev) =>
            prev.map((c) =>
              c.case_id === tempId || c.case_id === caseId
                ? {
                    case_id: event.case_id!,
                    created_at: createdAt,
                    profile_text: profileText,
                    status: "done",
                    shortlist_count: shortlist.length,
                  }
                : c
            )
          );
        }

        if (event.event === "case_error") {
          finalStatus = "error";
          setCases((prev) =>
            prev.map((c) =>
              c.case_id === tempId || c.case_id === caseId
                ? { ...c, case_id: event.case_id ?? tempId, status: "error" }
                : c
            )
          );
        }
      }
    } finally {
      setIsStreaming(false);
    }

    const resolvedId = finalCaseId ?? caseId;
    setActiveCaseId(resolvedId);

    const caseDone = accumulated.find((e) => e.event === "case_done");
    const profileSummary = accumulated.find(
      (e) => e.event === "agent_summary" && e.agent === "profile"
    );
    setActiveCaseFull((prev) => ({
      case_id: resolvedId,
      created_at: createdAt,
      profile_text: profileText,
      avatar: (profileSummary?.data as unknown as HomeOSAvatar) ?? prev?.avatar ?? null,
      pipeline: [...(prev?.pipeline ?? []), ...accumulated],
      shortlist: caseDone?.shortlist ?? prev?.shortlist ?? [],
      conversation: prev?.conversation ?? [],
      status: finalStatus,
    }));
    setStreamingEvents([]);
  }, []);

  const handleNewCase = useCallback(async (profileText: string) => {
    setStreamingEvents([]);
    setActiveCaseFull(null);
    setShortlistIds([]);
    setRightPanel("pipeline");

    const tempId = `pending-${Date.now()}`;
    const createdAt = new Date().toISOString();
    const tempSummary: HomeOSCaseSummary = {
      case_id: tempId,
      created_at: createdAt,
      profile_text: profileText,
      status: "running",
      shortlist_count: 0,
    };
    setCases((prev) => [tempSummary, ...prev]);
    setActiveCaseId(tempId);

    await _processStream(investigateStream(profileText, 5), tempId, profileText, createdAt, tempId);
  }, [_processStream]);

  const handleRefine = useCallback(async (message: string) => {
    if (!activeCaseId || activeCaseId.startsWith("pending-")) return;
    const currentCase = activeCaseFull;
    if (!currentCase) return;

    setCases((prev) =>
      prev.map((c) => c.case_id === activeCaseId ? { ...c, status: "running" } : c)
    );
    setActiveCaseFull((prev) => prev ? {
      ...prev,
      status: "running",
      conversation: [...prev.conversation, { role: "user", content: message }],
    } : prev);

    await _processStream(
      refineStream(activeCaseId, message),
      activeCaseId,
      currentCase.profile_text,
      currentCase.created_at,
      activeCaseId,
    );
  }, [activeCaseId, activeCaseFull, _processStream]);

  const handleSelectCase = useCallback((caseId: string) => {
    setActiveCaseId(caseId);
    setRightPanel("pipeline");
    setSelectedBlockId(null);
  }, []);

  const handleSelectBlock = useCallback((blockId: number) => {
    setSelectedBlockId(blockId);
    setRightPanel("block_detail");
  }, []);

  const handleSendMessage = useCallback(
    async (message: string) => {
      if (!activeCaseId || activeCaseId.startsWith("pending-")) return;
      setChatChunks("");
      let full = "";
      for await (const chunk of chatInCase(activeCaseId, message)) {
        full += chunk;
        setChatChunks(full);
      }
      setActiveCaseFull((prev) =>
        prev
          ? {
              ...prev,
              conversation: [
                ...prev.conversation,
                { role: "user", content: message },
                { role: "assistant", content: full },
              ],
            }
          : prev
      );
      setChatChunks("");
    },
    [activeCaseId]
  );

  const selectedBlock = blocks.find((b) => b.block_id === selectedBlockId) ?? null;
  const activeProfileText =
    activeCaseFull?.profile_text ??
    cases.find((c) => c.case_id === activeCaseId)?.profile_text ??
    "";

  // ── Explore mode — 2-column (behaviour unchanged) ─────────────────────
  if (mode === "explore") {
    return (
      <div className="flex h-full bg-background">
        <aside
          style={sidebarOpen ? { width: "clamp(280px, 30%, 480px)" } : undefined}
          className={`flex flex-col border-r border-border bg-card transition-[width] duration-300 ease-in-out overflow-hidden shrink-0 ${
            sidebarOpen ? "" : "w-14"
          }`}
        >
          {!sidebarOpen && (
            <div className="flex flex-col items-center gap-2 pt-4 px-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground text-sm font-bold shrink-0">
                H
              </div>
              <Separator className="w-7 my-1" />
              <RailIcon icon={SlidersHorizontal} label="Filters"           onClick={() => setSidebarOpen(true)} />
              <RailIcon icon={TrendingUp}        label="Stats"             onClick={() => setSidebarOpen(true)} />
              <RailIcon icon={BarChart2}         label="PSF Trend"         onClick={() => setSidebarOpen(true)} />
              <RailIcon icon={Table2}            label="Estate Comparison" onClick={() => setSidebarOpen(true)} />
            </div>
          )}
          {sidebarOpen && (
            <div className="flex flex-col overflow-y-auto flex-1 min-h-0">
              <header className="flex items-center justify-between px-5 py-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground text-sm font-bold shrink-0">
                    H
                  </div>
                  <div>
                    <h1 className="text-base font-bold text-foreground leading-tight">HDB Match</h1>
                    <p className="text-xs text-muted-foreground">Explore mode</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setMode("ai")}
                  className="text-xs rounded-md border border-border px-2 py-1 text-muted-foreground hover:bg-muted"
                >
                  AI Mode
                </button>
              </header>
              <Separator />
              <FilterPanel filters={filters} onChange={setFilters} />
              <Separator />
              <DirectTransitFilter filters={filters} onResults={setDirectTransit} />
              <Separator />
              <div className="grid grid-cols-2 gap-2 p-4">
                <StatCard label="Matches"      value={String(directTransit?.count ?? search.data?.count ?? 0)} isLoading={search.isLoading} />
                <StatCard label="Median PSF"   value={formatPsf(metrics?.median_psf)}   hint="estate avg" isLoading={estate.isLoading} />
                <StatCard label="Median Price" value={formatSGD(metrics?.median_price)}  isLoading={estate.isLoading} />
                <StatCard label="Growth"       value={metrics?.growth_pct != null ? `${metrics.growth_pct}%` : "—"} isLoading={estate.isLoading} />
              </div>
              <Separator />
              <div className="p-4">
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">PSF Trend</h3>
                <PsfTrendChart series={estate.data?.psf_over_time ?? []} />
              </div>
              <Separator />
              <div className="p-4">
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Estate Comparison</h3>
                <EstateComparison rows={comparison.data?.estates ?? []} />
              </div>
            </div>
          )}
        </aside>

        <main className="relative flex-1 overflow-hidden">
          <button
            onClick={() => setSidebarOpen((o) => !o)}
            className="absolute left-[10px] top-[82px] z-[1000] flex h-[34px] w-[34px] items-center justify-center rounded-sm border-2 border-[rgba(0,0,0,0.2)] bg-white shadow-sm hover:bg-gray-100 transition-colors"
            aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
          >
            {sidebarOpen
              ? <PanelLeftClose className="h-4 w-4 text-[#333]" />
              : <PanelLeftOpen  className="h-4 w-4 text-[#333]" />}
          </button>
          {search.isError && (
            <div className="absolute left-1/2 top-4 z-[1000] -translate-x-1/2 rounded-lg bg-destructive/10 border border-destructive/20 px-4 py-2 text-sm text-destructive shadow-sm">
              Failed to load data — is the API running?
            </div>
          )}
          {search.isFetching && (
            <div className="absolute right-4 top-4 z-[1000] rounded-lg bg-card/90 border border-border px-3 py-1.5 text-xs text-muted-foreground shadow-sm backdrop-blur-sm">
              Updating…
            </div>
          )}
          <MapView
            blocks={blocks}
            shortlistIds={shortlistIds}
            selectedBlockId={selectedBlockId}
            onSelectBlock={setSelectedBlockId}
          />
          <HomeOSDetailPanel
            block={selectedBlock}
            profileText={undefined}
            onClose={() => setSelectedBlockId(null)}
          />
        </main>
      </div>
    );
  }

  // ── AI mode — 3-column layout ─────────────────────────────────────────
  return (
    <div className="flex h-full bg-background">
      {/* Left: Cases */}
      <aside className="flex w-72 shrink-0 flex-col border-r border-border bg-card overflow-hidden">
        <header className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground text-sm font-bold shrink-0">
              H
            </div>
            <div>
              <h1 className="text-sm font-bold text-foreground leading-tight">HDB Match</h1>
              <p className="text-xs text-muted-foreground">HomeOS Agent</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setMode("explore")}
            className="text-[10px] rounded px-2 py-1 text-muted-foreground hover:bg-muted border border-border"
          >
            Explore
          </button>
        </header>
        <div className="flex-1 overflow-hidden">
          <CasesPanel
            cases={cases}
            activeCaseId={activeCaseId}
            activeCase={activeCaseFull}
            streamingEvents={streamingEvents}
            chatChunks={chatChunks}
            isStreaming={isStreaming}
            onNewCase={handleNewCase}
            onSelectCase={handleSelectCase}
            onSendMessage={handleSendMessage}
            onRefine={handleRefine}
          />
        </div>
      </aside>

      {/* Center: Map */}
      <main className="relative flex-1 overflow-hidden">
        {search.isError && (
          <div className="absolute left-1/2 top-4 z-[1000] -translate-x-1/2 rounded-lg bg-destructive/10 border border-destructive/20 px-4 py-2 text-sm text-destructive shadow-sm">
            Failed to load data — is the API running?
          </div>
        )}
        {search.isFetching && (
          <div className="absolute right-4 top-4 z-[1000] rounded-lg bg-card/90 border border-border px-3 py-1.5 text-xs text-muted-foreground shadow-sm backdrop-blur-sm">
            Updating…
          </div>
        )}
        <MapView
          blocks={blocks}
          shortlistIds={shortlistIds}
          selectedBlockId={selectedBlockId}
          onSelectBlock={handleSelectBlock}
          profileText={activeProfileText}
        />
      </main>

      {/* Right: Pipeline or Block Detail */}
      <aside className="flex w-80 shrink-0 flex-col border-l border-border bg-card overflow-hidden">
        {rightPanel === "pipeline" ? (
          <PipelinePanel
            activeCase={activeCaseFull}
            streamingEvents={streamingEvents}
            onSelectBlock={handleSelectBlock}
            onSendMessage={handleSendMessage}
            chatChunks={chatChunks}
          />
        ) : (
          <HomeOSDetailPanel
            block={selectedBlock}
            profileText={activeProfileText}
            onClose={() => {
              setSelectedBlockId(null);
              setRightPanel("pipeline");
            }}
            onBack={() => setRightPanel("pipeline")}
          />
        )}
      </aside>
    </div>
  );
}
