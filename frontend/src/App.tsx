import { useState, useCallback, useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  PanelLeftClose,
  PanelLeftOpen,
  SlidersHorizontal,
  BarChart2,
  Table2,
  TrendingUp,
  LogIn,
  LogOut,
  Sparkles,
  Moon,
  Sun,
  MessageSquare,
  Compass,
  Newspaper,
  MonitorCog,
  ListOrdered,
  Info,
  ChevronDown,
  MapPin,
} from "lucide-react";
import CasesPanel from "./components/CasesPanel";
import DirectTransitFilter from "./components/DirectTransitFilter";
import DisplayPanel from "./components/DisplayPanel";
import EstateComparison from "./components/EstateComparison";
import FilterPanel from "./components/FilterPanel";
import HomeOSDetailPanel from "./components/HomeOSDetailPanel";
import MapView, { type MapViewState } from "./components/MapView";
import ModelSelector from "./components/ModelSelector";
import { MAP_SEARCH_LIMIT } from "./lib/mapConfig";
import NewsPanel from "./components/NewsPanel";
import PipelinePanel from "./components/PipelinePanel";
import PsfTrendChart from "./components/PsfTrendChart";
import ScoreRankingPanel from "./components/ScoreRankingPanel";
import InfoPanel from "./components/InfoPanel";
import ProductChooser from "./components/ProductChooser";
import BtoDashboard from "./components/BtoDashboard";
import PrivateDashboard from "./components/PrivateDashboard";
import StatCard from "./components/StatCard";
import AuthModal from "./components/AuthModal";
import SavedPlacesPanel from "./components/SavedPlacesPanel";
import UpgradeModal from "./components/UpgradeModal";
import { Separator } from "./components/ui/separator";
import {
  chatInCase,
  getEstateAnalytics,
  getEstateComparison,
  investigateStream,
  refineStream,
  searchProperties,
  apiSubscriptionStatus,
} from "./lib/api";
import { clearAuth, getStoredUser, type AuthUser } from "./lib/auth";
import { formatPsf, formatSGD } from "./lib/format";
import { getStoredModel, setStoredModel, DEFAULT_MODEL } from "./lib/modelPreference";
import { AI_MODE_ENABLED } from "./lib/featureFlags";
import type {
  AgentEvent,
  DirectTransitDestination,
  DirectTransitResponse,
  HomeOSCase,
  HomeOSCaseSummary,
  HomeOSAvatar,
  SearchFilters,
} from "./types";

const DEFAULT_ESTATE = 1;

type Mode = "ai" | "explore";
type RightPanel = "pipeline" | "block_detail";
type Theme = "light" | "dark";

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
  // Subscribed users land in AI mode; everyone else starts in free Explore mode.
  // When AI mode is disabled entirely, the app is a pure manual product.
  const [mode, setMode] = useState<Mode>(() =>
    AI_MODE_ENABLED && getStoredUser()?.is_subscribed ? "ai" : "explore",
  );

  // Top-level product choice: resale / bto / private / unsure (the chooser).
  const [product, setProductState] = useState<"resale" | "bto" | "private" | "unsure">(() => {
    const saved = window.localStorage.getItem("hdb-product");
    return saved === "resale" || saved === "bto" || saved === "private" ? saved : "unsure";
  });
  const setProduct = useCallback((p: "resale" | "bto" | "private" | "unsure") => {
    setProductState(p);
    try { window.localStorage.setItem("hdb-product", p); } catch { /* ignore */ }
  }, []);
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = window.localStorage.getItem("hdb-match-theme");
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.style.colorScheme = theme;
    window.localStorage.setItem("hdb-match-theme", theme);
  }, [theme]);

  // ── Auth state ──────────────────────────────────────────────────────────────
  const [authUser, setAuthUser] = useState<AuthUser | null>(() => getStoredUser());
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showSavedModal, setShowSavedModal] = useState(false);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);

  // Re-check subscription status on mount (in case it changed after Stripe redirect)
  useEffect(() => {
    if (!authUser) return;
    apiSubscriptionStatus()
      .then((s) => {
        const updated: AuthUser = { email: s.email, is_subscribed: s.is_subscribed };
        setAuthUser(updated);
        import("./lib/auth").then(({ saveAuth, getToken }) => {
          const t = getToken();
          if (t) saveAuth(t, updated);
        });
      })
      .catch(() => {/* token expired — stay as-is */});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Handle ?payment=success redirect from Stripe
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("payment") === "success") {
      window.history.replaceState({}, "", window.location.pathname);
      // Refresh subscription status
      apiSubscriptionStatus().then((s) => {
        const updated: AuthUser = { email: s.email, is_subscribed: s.is_subscribed };
        setAuthUser(updated);
        import("./lib/auth").then(({ saveAuth, getToken }) => {
          const t = getToken();
          if (t) saveAuth(t, updated);
        });
      }).catch(() => {});
    }
  }, []);

  const isSubscribed = authUser?.is_subscribed ?? false;

  // Defense-in-depth: never allow AI mode when it's disabled, or without an
  // active subscription. Covers stale state, lapsed subscriptions, and the
  // AI-disabled product configuration.
  useEffect(() => {
    if (mode === "ai" && (!AI_MODE_ENABLED || !isSubscribed)) {
      setMode("explore");
    }
  }, [mode, isSubscribed]);

  function handleModeSwitch(next: Mode) {
    if (next === "ai" && !AI_MODE_ENABLED) {
      return;
    }
    if (next === "ai" && !isSubscribed) {
      setShowUpgradeModal(true);
      return;
    }
    setMode(next);
  }

  function handleLogout() {
    clearAuth();
    setAuthUser(null);
    setMode("explore");
  }

  // Shared
  const [filters, setFilters] = useState<SearchFilters>({ limit: MAP_SEARCH_LIMIT });
  const [directTransit, setDirectTransit] = useState<DirectTransitResponse | null>(null);
  const [directTransitDestinations, setDirectTransitDestinations] = useState<DirectTransitDestination[]>([]);
  const [aiSelectedBlockId, setAiSelectedBlockId] = useState<number | null>(null);
  const [exploreSelectedBlockId, setExploreSelectedBlockId] = useState<number | null>(null);
  const [shortlistIds, setShortlistIds] = useState<number[]>([]);
  const [scoreRankedIds, setScoreRankedIds] = useState<number[]>([]);
  // Explore product sub-tabs: manual exploration, score ranking, info/rankings.
  const [exploreTab, setExploreTab] = useState<"explore" | "scoring" | "info">("explore");
  const [hasAiMapFilter, setHasAiMapFilter] = useState(false);
  const [aiMapView, setAiMapView] = useState<MapViewState>({ center: [1.352, 103.82], zoom: 12 });
  const [exploreMapView, setExploreMapView] = useState<MapViewState>({ center: [1.352, 103.82], zoom: 12 });
  const [sidebarOpen, setSidebarOpen] = useState(true); // explore mode only
  const [aiSidebarOpen, setAiSidebarOpen] = useState(true);
  const [nearbyBusRadiusM, setNearbyBusRadiusM] = useState(200);

  // AI mode
  const [cases, setCases] = useState<HomeOSCaseSummary[]>([]);
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [activeCaseFull, setActiveCaseFull] = useState<HomeOSCase | null>(null);
  const [streamingEvents, setStreamingEvents] = useState<AgentEvent[]>([]);
  const [chatChunks, setChatChunks] = useState("");
  const [rightPanel, setRightPanel] = useState<RightPanel>("pipeline");
  const [rightTab, setRightTab] = useState<"display" | "news">("display");
  const [isStreaming, setIsStreaming] = useState(false);
  const [framedCaseId, setFramedCaseId] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>(() => getStoredModel() ?? DEFAULT_MODEL);

  const selectedBlockId = mode === "ai" ? aiSelectedBlockId : exploreSelectedBlockId;

  const handleModelChange = useCallback((model: string) => {
    setSelectedModel(model);
    setStoredModel(model);
  }, []);

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

        if (event.event === "agent_summary" && event.agent === "search" && event.data) {
          const candidateIds = (event.data as Record<string, unknown>)["candidate_ids"];
          if (Array.isArray(candidateIds)) {
            const filteredIds = candidateIds.filter((id): id is number => typeof id === "number");
            setShortlistIds(filteredIds);
            setHasAiMapFilter(true);
          }
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
          setHasAiMapFilter(true);
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
    setHasAiMapFilter(false);
    setAiSelectedBlockId(null);
    setFramedCaseId(null);
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

    await _processStream(
      investigateStream(profileText, 5, selectedModel || undefined),
      tempId,
      profileText,
      createdAt,
      tempId,
    );
  }, [_processStream, selectedModel]);

  const handleRefine = useCallback(async (message: string) => {
    if (!activeCaseId || activeCaseId.startsWith("pending-")) return;
    const currentCase = activeCaseFull;
    if (!currentCase) return;

    setFramedCaseId(null);

    setCases((prev) =>
      prev.map((c) => c.case_id === activeCaseId ? { ...c, status: "running" } : c)
    );
    setActiveCaseFull((prev) => prev ? {
      ...prev,
      status: "running",
      conversation: [...prev.conversation, { role: "user", content: message }],
    } : prev);

    await _processStream(
      refineStream(activeCaseId, message, selectedModel || undefined),
      activeCaseId,
      currentCase.profile_text,
      currentCase.created_at,
      activeCaseId,
    );
  }, [activeCaseId, activeCaseFull, _processStream, selectedModel]);

  const handleSelectCase = useCallback((caseId: string) => {
    setActiveCaseId(caseId);
    setRightPanel("pipeline");
    setAiSelectedBlockId(null);
  }, []);

  const handleSelectBlock = useCallback((blockId: number) => {
    setAiSelectedBlockId(blockId);
    setRightPanel("block_detail");
  }, []);

  const clearSelectedBlock = useCallback(() => {
    if (mode === "ai") {
      setAiSelectedBlockId(null);
      setRightPanel("pipeline");
    } else {
      setExploreSelectedBlockId(null);
    }
  }, [mode]);

  useEffect(() => {
    if (selectedBlockId == null) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      clearSelectedBlock();
    };
    document.addEventListener("keydown", handleKeyDown, true);
    return () => document.removeEventListener("keydown", handleKeyDown, true);
  }, [clearSelectedBlock, selectedBlockId]);

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
  const selectedRecommendation = activeCaseFull?.shortlist.find(
    (row) => row.block_id === aiSelectedBlockId,
  ) ?? null;
  const aiMapBlocks = useMemo(() => {
    if (!hasAiMapFilter) return blocks;
    const visibleIds = new Set(shortlistIds);
    return blocks.filter((block) => visibleIds.has(block.block_id));
  }, [blocks, hasAiMapFilter, shortlistIds]);

  useEffect(() => {
    if (!hasAiMapFilter || aiSelectedBlockId == null || shortlistIds.includes(aiSelectedBlockId)) return;
    setAiSelectedBlockId(null);
    setRightPanel("pipeline");
  }, [aiSelectedBlockId, hasAiMapFilter, shortlistIds]);
  const activeProfileText =
    activeCaseFull?.profile_text ??
    cases.find((c) => c.case_id === activeCaseId)?.profile_text ??
    "";

  // Login + saved state are available regardless of AI mode (Feature 1); only
  // the AI upgrade flow is gated behind AI_MODE_ENABLED.
  const authOverlays = (
    <>
      {showAuthModal && (
        <AuthModal
          onSuccess={(user) => {
            setAuthUser(user);
            setShowAuthModal(false);
            // Migrate any anonymous local state into the new account.
            import("./lib/userState").then((m) => m.pushLocalStateToServer().catch(() => {}));
          }}
          onClose={() => setShowAuthModal(false)}
        />
      )}
      {showSavedModal && (
        <SavedPlacesPanel
          authUser={authUser}
          onClose={() => setShowSavedModal(false)}
          onSignIn={() => { setShowSavedModal(false); setShowAuthModal(true); }}
        />
      )}
      {AI_MODE_ENABLED && showUpgradeModal && (
        <UpgradeModal
          isLoggedIn={!!authUser}
          onClose={() => setShowUpgradeModal(false)}
          onLoginRequired={() => setShowAuthModal(true)}
        />
      )}
    </>
  );

  const themeButton = (
    <button
      type="button"
      onClick={() => setTheme((current) => current === "light" ? "dark" : "light")}
      title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
      aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
      className="flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-lg border border-border bg-muted/50 px-3 text-xs font-semibold text-foreground shadow-sm transition-colors hover:bg-muted"
    >
      {theme === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
      <span>{theme === "light" ? "Dark" : "Light"}</span>
    </button>
  );

  // ── Product gate: chooser / BTO before the resale (explore) product ───
  if (product === "unsure") {
    return <ProductChooser onSelect={setProduct} />;
  }
  if (product === "bto") {
    return (
      <BtoDashboard
        onBack={() => setProduct("unsure")}
        theme={theme}
        onToggleTheme={() => setTheme((c) => (c === "light" ? "dark" : "light"))}
      />
    );
  }
  if (product === "private") {
    return (
      <PrivateDashboard
        onBack={() => setProduct("unsure")}
        theme={theme}
        onToggleTheme={() => setTheme((c) => (c === "light" ? "dark" : "light"))}
      />
    );
  }

  // ── Explore mode — 2-column (behaviour unchanged) ─────────────────────
  if (mode === "explore") {
    return (
      <div className="flex h-full bg-background">
        {authOverlays}
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
              <RailIcon icon={SlidersHorizontal} label="Filters"           onClick={() => { setExploreTab("explore"); setSidebarOpen(true); }} />
              <RailIcon icon={TrendingUp}        label="Stats"             onClick={() => { setExploreTab("explore"); setSidebarOpen(true); }} />
              <RailIcon icon={BarChart2}         label="PSF Trend"         onClick={() => { setExploreTab("explore"); setSidebarOpen(true); }} />
              <RailIcon icon={Table2}            label="Estate Comparison" onClick={() => { setExploreTab("explore"); setSidebarOpen(true); }} />
              <RailIcon icon={ListOrdered}       label="Scoring"           onClick={() => { setExploreTab("scoring"); setSidebarOpen(true); }} />
              <RailIcon icon={Info}              label="Info / rankings"   onClick={() => { setExploreTab("info"); setSidebarOpen(true); }} />
              <RailIcon icon={MapPin}            label="Saved places"      onClick={() => setShowSavedModal(true)} />
              <Separator className="w-7 my-1" />
              {AI_MODE_ENABLED && (
                <RailIcon icon={Sparkles} label="AI mode" onClick={() => handleModeSwitch("ai")} />
              )}
              <RailIcon icon={theme === "light" ? Moon : Sun} label={`${theme === "light" ? "Dark" : "Light"} mode`} onClick={() => setTheme((current) => current === "light" ? "dark" : "light")} />
              <RailIcon icon={authUser ? LogOut : LogIn} label={authUser ? "Sign out" : "Sign in"} onClick={authUser ? handleLogout : () => setShowAuthModal(true)} />
            </div>
          )}
          {sidebarOpen && (
            <div className="flex flex-col overflow-y-auto flex-1 min-h-0">
              <header className="border-b border-border bg-muted/25 px-5 py-4">
                <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground text-sm font-bold shrink-0">
                    H
                  </div>
                  <div>
                    <h1 className="text-base font-bold text-foreground leading-tight">HDB Match</h1>
                    <p className="text-xs text-muted-foreground">
                      {exploreTab === "scoring" ? "Score ranking" : exploreTab === "info" ? "Appreciation rankings" : "Explore mode"}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setProduct("unsure")}
                    title="Switch between BTO and Resale"
                    className="flex h-9 items-center gap-1 rounded-lg border border-border bg-muted/50 px-2.5 text-[11px] font-semibold text-foreground hover:bg-muted"
                  >
                    Resale
                    <ChevronDown className="h-3 w-3" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowSavedModal(true)}
                    title="Saved places & preferences"
                    className="flex h-9 items-center gap-1 rounded-lg border border-border bg-muted/50 px-2.5 text-[11px] font-semibold text-foreground hover:bg-muted"
                  >
                    <MapPin className="h-3.5 w-3.5" />
                    Saved
                  </button>
                  <button
                    type="button"
                    onClick={authUser ? handleLogout : () => setShowAuthModal(true)}
                    title={authUser ? `Signed in as ${authUser.email}` : "Sign in"}
                    className="flex h-9 items-center gap-1 rounded-lg border border-border bg-muted/50 px-2.5 text-[11px] font-semibold text-foreground hover:bg-muted"
                  >
                    {authUser ? <LogOut className="h-3.5 w-3.5" /> : <LogIn className="h-3.5 w-3.5" />}
                    {authUser ? "Sign out" : "Sign in"}
                  </button>
                  {themeButton}
                </div>
                </div>
                {AI_MODE_ENABLED && (
                  <div className="mt-4 grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => handleModeSwitch("ai")}
                      className="flex min-h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs font-semibold text-foreground shadow-sm hover:bg-muted"
                    >
                      <Sparkles className="h-3 w-3" />
                      AI Mode
                    </button>
                    {authUser ? (
                      <button type="button" onClick={handleLogout} title={`Signed in as ${authUser.email}`} className="flex min-h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs font-semibold text-foreground shadow-sm hover:bg-muted">
                        <LogOut className="h-4 w-4" />
                        Sign out
                      </button>
                    ) : (
                      <button type="button" onClick={() => setShowAuthModal(true)} className="flex min-h-10 items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground shadow-sm hover:bg-primary/90">
                        <LogIn className="h-4 w-4" />
                        Sign in
                      </button>
                    )}
                  </div>
                )}
                {/* Explore / Scoring / Info sub-tabs */}
                <div className="mt-4 grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setExploreTab("explore")}
                    className={`flex min-h-10 items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-xs font-semibold shadow-sm transition-colors ${
                      exploreTab === "explore"
                        ? "bg-primary text-primary-foreground"
                        : "border border-border bg-card text-foreground hover:bg-muted"
                    }`}
                  >
                    <Compass className="h-3.5 w-3.5" />
                    Explore
                  </button>
                  <button
                    type="button"
                    onClick={() => setExploreTab("scoring")}
                    className={`flex min-h-10 items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-xs font-semibold shadow-sm transition-colors ${
                      exploreTab === "scoring"
                        ? "bg-primary text-primary-foreground"
                        : "border border-border bg-card text-foreground hover:bg-muted"
                    }`}
                  >
                    <ListOrdered className="h-3.5 w-3.5" />
                    Scoring
                  </button>
                  <button
                    type="button"
                    onClick={() => setExploreTab("info")}
                    className={`flex min-h-10 items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-xs font-semibold shadow-sm transition-colors ${
                      exploreTab === "info"
                        ? "bg-primary text-primary-foreground"
                        : "border border-border bg-card text-foreground hover:bg-muted"
                    }`}
                  >
                    <Info className="h-3.5 w-3.5" />
                    Info
                  </button>
                </div>
              </header>
              {exploreTab === "explore" ? (
                <>
                  <FilterPanel filters={filters} onChange={setFilters} />
                  <Separator />
                  <DirectTransitFilter
                    filters={filters}
                    onResults={setDirectTransit}
                    onDestinationsChange={setDirectTransitDestinations}
                  />
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
                </>
              ) : exploreTab === "scoring" ? (
                <ScoreRankingPanel
                  onResults={(rows) => setScoreRankedIds(rows.map((r) => r.block_id))}
                  onSelectBlock={(id) => setExploreSelectedBlockId(id)}
                />
              ) : (
                <InfoPanel onSelectBlock={(id) => setExploreSelectedBlockId(id)} />
              )}
            </div>
          )}
        </aside>

        <main className="relative min-h-0 min-w-0 flex-1 overflow-hidden">
          <button
            onClick={() => setSidebarOpen((o) => !o)}
            className="absolute left-[10px] top-[82px] z-[1000] flex h-[34px] w-[34px] items-center justify-center rounded-sm border-2 border-black/20 bg-card text-foreground shadow-sm transition-colors hover:bg-muted"
            aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
          >
            {sidebarOpen
              ? <PanelLeftClose className="h-4 w-4" />
              : <PanelLeftOpen  className="h-4 w-4" />}
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
            shortlistIds={scoreRankedIds}
            selectedBlockId={exploreSelectedBlockId}
            onSelectBlock={setExploreSelectedBlockId}
            nearbyBusRadiusM={nearbyBusRadiusM}
            onNearbyBusRadiusChange={setNearbyBusRadiusM}
            hasSelectedProperty={selectedBlock != null}
            destinations={directTransitDestinations}
            initialView={exploreMapView}
            onViewChange={setExploreMapView}
          />
          <HomeOSDetailPanel
            block={selectedBlock}
            profileText={undefined}
            onClose={clearSelectedBlock}
          />
        </main>
      </div>
    );
  }

  // ── AI mode — 3-column layout ─────────────────────────────────────────
  return (
    <div className="flex h-full bg-background">
      {authOverlays}

      {/* Left: Cases */}
      <aside
        style={aiSidebarOpen ? { width: "clamp(320px, 28vw, 440px)" } : undefined}
        className={`flex shrink-0 flex-col overflow-hidden border-r border-border bg-card transition-[width] duration-300 ease-in-out ${
          aiSidebarOpen ? "" : "w-14"
        }`}
      >
        {!aiSidebarOpen && (
          <div className="flex flex-col items-center gap-2 px-2 pt-4">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">H</div>
            <Separator className="my-1 w-7" />
            <RailIcon icon={MessageSquare} label="HomeOS cases" onClick={() => setAiSidebarOpen(true)} />
            <RailIcon icon={Compass} label="Explore mode" onClick={() => setMode("explore")} />
            <RailIcon icon={theme === "light" ? Moon : Sun} label={`${theme === "light" ? "Dark" : "Light"} mode`} onClick={() => setTheme((current) => current === "light" ? "dark" : "light")} />
            <RailIcon icon={authUser ? LogOut : LogIn} label={authUser ? "Sign out" : "Sign in"} onClick={authUser ? handleLogout : () => setShowAuthModal(true)} />
          </div>
        )}
        {aiSidebarOpen && <>
        <header className="border-b border-border bg-muted/25 px-4 py-4">
          <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground text-sm font-bold shrink-0">
              H
            </div>
            <div>
              <h1 className="text-sm font-bold text-foreground leading-tight">HDB Match</h1>
              <p className="text-xs text-muted-foreground">HomeOS Agent</p>
            </div>
          </div>
          {themeButton}
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setMode("explore")}
              className="flex min-h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs font-semibold text-foreground shadow-sm hover:bg-muted"
            >
              <Compass className="h-3.5 w-3.5" />
              Explore
            </button>
            {authUser ? (
              <button
                type="button"
                onClick={handleLogout}
                title={`Signed in as ${authUser.email}`}
                className="flex min-h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs font-semibold text-foreground shadow-sm hover:bg-muted"
              >
                <LogOut className="h-3 w-3" />
                Sign out
              </button>
            ) : (
              <button
                type="button"
                onClick={() => setShowAuthModal(true)}
                className="flex min-h-10 items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground shadow-sm hover:bg-primary/90"
              >
                <LogIn className="h-3 w-3" />
                Sign in
              </button>
            )}
          </div>
        </header>
        <div className="border-b border-border px-4 py-2">
          <ModelSelector value={selectedModel} onChange={handleModelChange} />
        </div>
        <div className="flex-1 overflow-hidden">
          <CasesPanel
            cases={cases}
            activeCaseId={activeCaseId}
            activeCase={activeCaseFull}
            streamingEvents={streamingEvents}
            chatChunks={chatChunks}
            isStreaming={isStreaming}
            isAuthenticated={!!authUser}
            isSubscribed={isSubscribed}
            onNewCase={handleNewCase}
            onSelectCase={handleSelectCase}
            onSendMessage={handleSendMessage}
            onRefine={handleRefine}
            onSignInRequired={() => setShowAuthModal(true)}
            onUpgradeRequired={() => setShowUpgradeModal(true)}
          />
        </div>
        </>}
      </aside>

      {/* Center: Map */}
      <main className="relative min-h-0 min-w-0 flex-1 overflow-hidden">
        <button
          onClick={() => setAiSidebarOpen((open) => !open)}
          className="absolute left-[10px] top-[82px] z-[1000] flex h-[34px] w-[34px] items-center justify-center rounded-sm border-2 border-black/20 bg-card text-foreground shadow-sm transition-colors hover:bg-muted"
          aria-label={aiSidebarOpen ? "Collapse AI sidebar" : "Expand AI sidebar"}
        >
          {aiSidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
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
          blocks={aiMapBlocks}
          shortlistIds={activeCaseFull?.status === "done" ? shortlistIds : []}
          selectedBlockId={aiSelectedBlockId}
          onSelectBlock={handleSelectBlock}
          profileText={activeProfileText}
          nearbyBusRadiusM={nearbyBusRadiusM}
          recommendationsOnly={activeCaseFull?.status === "done"}
          initialView={aiMapView}
          onViewChange={setAiMapView}
          fitRecommendations={
            activeCaseFull?.status === "done"
            && activeCaseFull.case_id !== framedCaseId
            && shortlistIds.length > 0
          }
          onRecommendationsFitted={() => setFramedCaseId(activeCaseFull?.case_id ?? null)}
        />
      </main>

      {/* Right: Display/News tabs + Pipeline or Block Detail */}
      <aside className="flex w-80 shrink-0 flex-col border-l border-border bg-card overflow-hidden">
        <div className="grid shrink-0 grid-cols-2 gap-1.5 border-b border-border bg-muted/40 p-2.5">
          {(["display", "news"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setRightTab(tab)}
              className={`flex min-h-11 items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-semibold capitalize transition-all ${
                rightTab === tab
                  ? "border-primary/40 bg-card text-foreground shadow-sm"
                  : "border-transparent text-muted-foreground hover:border-border hover:bg-card/60 hover:text-foreground"
              }`}
            >
              {tab === "display"
                ? <MonitorCog className="h-4 w-4" />
                : <Newspaper className="h-4 w-4" />}
              {tab === "display" ? "Display" : "News"}
            </button>
          ))}
        </div>
        {rightTab === "display" ? (
          <>
            <DisplayPanel
              nearbyBusRadiusM={nearbyBusRadiusM}
              onNearbyBusRadiusChange={setNearbyBusRadiusM}
              hasSelectedProperty={selectedBlock != null}
            />
            <Separator />
            <div className="min-h-0 flex-1 overflow-hidden">
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
                  caseId={activeCaseId ?? undefined}
                  recommendation={selectedRecommendation}
                  onClose={clearSelectedBlock}
                  onBack={clearSelectedBlock}
                />
              )}
            </div>
          </>
        ) : (
          <NewsPanel />
        )}
      </aside>
    </div>
  );
}
