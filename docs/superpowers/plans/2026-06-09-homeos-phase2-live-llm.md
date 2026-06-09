# HomeOS Phase 2 — Vercel AI Gateway Live Demo

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the already-built CasesPanel and PipelinePanel into App.tsx for a 3-column SSE-streaming AI mode, and fix requirements.txt so the Vercel AI Gateway import path works.

**Architecture:** All five backend services (`homeos_ai_agents`, `homeos_case_store`, `investigate_stream`, `chat_in_case`, SSE endpoints) and all frontend components (`CasesPanel`, `PipelinePanel`, `HomeOSDetailPanel` with back button) are fully implemented. This plan mounts them in App.tsx and flips the one missing pip extra. A single `AI_GATEWAY_API_KEY` env var auto-activates Vercel AI Gateway in `get_model()` — no other config needed for the live demo.

**Tech Stack:** React 18, TypeScript, Pydantic AI 1.106 + openai extra, Vercel AI Gateway (`https://ai-gateway.vercel.sh/v1`), FastAPI SSE.

---

## File Structure

| File | Action | What changes |
|---|---|---|
| `backend/requirements.txt` | Modify | Add `openai` to `pydantic-ai-slim` extras |
| `frontend/src/App.tsx` | Rewrite | 3-column AI mode + preserved Explore mode |

Nothing else needs to change — all other files are already done.

---

## Task 1: Fix pydantic-ai requirements

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Update the requirement line**

In `backend/requirements.txt`, change:
```
pydantic-ai-slim[anthropic]==1.106.0
```
to:
```
pydantic-ai-slim[anthropic,openai]==1.106.0
```

- [ ] **Step 2: Reinstall in the venv**

```bash
cd /Users/moethu/Documents/Codex/hack/estate-finder/backend && ./.venv/bin/pip install "pydantic-ai-slim[anthropic,openai]==1.106.0"
```

Expected: `Successfully installed` or `Requirement already satisfied` — no errors.

- [ ] **Step 3: Verify the import resolves**

```bash
cd /Users/moethu/Documents/Codex/hack/estate-finder/backend && ./.venv/bin/python -c "from pydantic_ai.models.openai import OpenAIModel; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "fix: add openai extra to pydantic-ai-slim for Vercel AI Gateway"
```

---

## Task 2: Rewrite App.tsx — 3-column AI mode

**Files:**
- Modify: `frontend/src/App.tsx`

The current App.tsx (251 lines) uses `HomeOSAgentPanel` which calls the old non-streaming `/homeos/investigate` endpoint. Replace the whole file with a version that:

- **AI mode (default):** fixed 3-column layout — CasesPanel (left, w-72) | Map (center, flex-1) | PipelinePanel or HomeOSDetailPanel (right, w-80)
- **Explore mode:** the existing collapsible sidebar + map overlay, exactly as before

### State machine for right panel (AI mode only)

```
rightPanel = "pipeline"     → PipelinePanel
rightPanel = "block_detail" → HomeOSDetailPanel with onBack → sets rightPanel back to "pipeline"
```

### handleNewCase flow

```
user clicks "Investigate homes"
  → add temp "running" case to cases list
  → for await each event from investigateStream()
      → append to streamingEvents
      → on case_done: update case status, set shortlistIds
  → on stream complete: build activeCaseFull from accumulated events
```

- [ ] **Step 1: Record current TypeScript error count as baseline**

```bash
cd /Users/moethu/Documents/Codex/hack/estate-finder/frontend && npx tsc --noEmit 2>&1 | tail -5
```

Note the count. After the rewrite, it must not increase.

- [ ] **Step 2: Replace App.tsx**

Write the following as the complete contents of `frontend/src/App.tsx`:

```tsx
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
  searchProperties,
} from "./lib/api";
import { formatPsf, formatSGD } from "./lib/format";
import type {
  AgentEvent,
  DirectTransitResponse,
  HomeOSCase,
  HomeOSCaseSummary,
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

  const handleNewCase = useCallback(async (profileText: string) => {
    setStreamingEvents([]);
    setActiveCaseFull(null);
    setShortlistIds([]);
    setRightPanel("pipeline");

    const tempId = `pending-${Date.now()}`;
    const tempSummary: HomeOSCaseSummary = {
      case_id: tempId,
      created_at: new Date().toISOString(),
      profile_text: profileText,
      status: "running",
      shortlist_count: 0,
    };
    setCases((prev) => [tempSummary, ...prev]);
    setActiveCaseId(tempId);

    const accumulated: AgentEvent[] = [];
    let finalCaseId: string | null = null;

    for await (const event of investigateStream(profileText, 5)) {
      accumulated.push(event);
      setStreamingEvents([...accumulated]);

      if (event.event === "case_done") {
        finalCaseId = event.case_id ?? null;
        const shortlist = event.shortlist ?? [];
        setShortlistIds(shortlist.map((r) => r.block_id));
        setCases((prev) =>
          prev.map((c) =>
            c.case_id === tempId
              ? {
                  case_id: event.case_id!,
                  created_at: tempSummary.created_at,
                  profile_text: profileText,
                  status: "done",
                  shortlist_count: shortlist.length,
                }
              : c
          )
        );
      }
      if (event.event === "case_error") {
        setCases((prev) =>
          prev.map((c) =>
            c.case_id === tempId
              ? { ...c, case_id: event.case_id ?? tempId, status: "error" }
              : c
          )
        );
      }
    }

    if (finalCaseId) {
      setActiveCaseId(finalCaseId);
      const caseDone = accumulated.find((e) => e.event === "case_done");
      const profileSummary = accumulated.find(
        (e) => e.event === "agent_summary" && e.agent === "profile"
      );
      setActiveCaseFull({
        case_id: finalCaseId,
        created_at: tempSummary.created_at,
        profile_text: profileText,
        avatar: (profileSummary?.data as HomeOSCase["avatar"]) ?? null,
        pipeline: accumulated,
        shortlist: caseDone?.shortlist ?? [],
        conversation: [],
        status: "done",
      });
    }
    setStreamingEvents([]);
  }, []);

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
            onNewCase={handleNewCase}
            onSelectCase={handleSelectCase}
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
```

- [ ] **Step 3: TypeScript check — zero new errors**

```bash
cd /Users/moethu/Documents/Codex/hack/estate-finder/frontend && npx tsc --noEmit
```

Expected: same error count as baseline (ideally 0). Fix any type errors before continuing.

Common fixes:
- If `HomeOSCase["avatar"]` cast errors: use `HomeOSAvatar | null` import from `"../types"` and cast as `HomeOSAvatar | null`
- If `investigateStream` or `chatInCase` not found: confirm they are exported from `./lib/api`

- [ ] **Step 4: Run frontend test suite**

```bash
cd /Users/moethu/Documents/Codex/hack/estate-finder/frontend && npm run test -- --run 2>&1 | tail -20
```

Expected: all previously-passing tests pass. App.tsx has no existing tests to break.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: 3-column AI mode with CasesPanel, PipelinePanel, and SSE streaming"
```

---

## Task 3: End-to-end smoke test

**Files:** none — verification only.

- [ ] **Step 1: Start backend and frontend**

In one terminal:
```bash
cd /Users/moethu/Documents/Codex/hack/estate-finder && python setup.py --run
```

Or manually:
```bash
# terminal 1
cd backend && ./.venv/bin/uvicorn app.api.main:app --reload --port 8010
# terminal 2
cd frontend && npm run dev
```

- [ ] **Step 2: Verify SSE stream via curl**

```bash
curl -N -s -X POST http://127.0.0.1:8010/homeos/investigate-stream \
  -H 'Content-Type: application/json' \
  -d '{"profile_text":"Family 4 room 800k near schools.","limit":2}' | head -30
```

Expected: multiple `data: {"event": ...}` lines, final line `data: {"event": "case_done", ...}`.

- [ ] **Step 3: Browser walkthrough**

Open `http://localhost:5173` (or whichever port Vite shows). Verify this exact sequence:

1. **Default view:** 3-column layout — CasesPanel left, map center, empty PipelinePanel right
2. **Type profile** in the left text area and click "Investigate homes"
3. **Streaming:** right panel shows live agent event rows appearing one by one
4. **Shortlist:** when `case_done` fires, 5 blocks turn violet on the map
5. **Case badge:** left panel case card updates from "running" to "done" with block count
6. **Chat:** type a question at the bottom of PipelinePanel → response streams in below the log
7. **Block detail:** click a violet map node → right panel switches to block detail view
8. **Back:** click "← Pipeline" → right panel returns to PipelinePanel
9. **Mode switch:** click "Explore" button in left panel header → 2-column explore mode with filters
10. **Return:** click "AI Mode" in explore sidebar header → back to 3-column

- [ ] **Step 4: Verify with real Vercel AI Gateway key**

Ensure `.env` contains:
```
AI_GATEWAY_API_KEY=<your-key>
LLM_MODEL=google/gemini-2.0-flash
```

Restart backend. Run the curl smoke test again. In the `agent_summary` events, `narrative` fields should contain real Gemini-generated text (not empty strings from TestModel).

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: phase 2 complete — Vercel AI Gateway live LLM, 3-column streaming demo"
```

---

## Self-Review

**Spec coverage:**
- Vercel AI Gateway auto-activates on `AI_GATEWAY_API_KEY` ✓ (already in `homeos_ai_agents.py`)
- requirements.txt `openai` extra ✓ (Task 1)
- 3-column AI layout: CasesPanel | Map | PipelinePanel ✓ (Task 2)
- Live SSE streaming — `handleNewCase` for-await loop updates `streamingEvents` ✓
- Shortlist blocks highlight violet on map ✓ (`setShortlistIds` on `case_done`)
- Chat Q&A — `handleSendMessage` streams `chatInCase` chunks ✓
- Block detail panel on map click with `← Pipeline` back button ✓ (rightPanel state machine)
- Explore mode preserved fully — same sidebar + stats + PSF trend + estate comparison ✓

**Placeholder scan:** None. All steps contain complete code.

**Type consistency:**
- `CasesPanel` receives `cases: HomeOSCaseSummary[]`, `activeCaseId: string | null`, `onNewCase: (profileText: string) => void`, `onSelectCase: (caseId: string) => void` — matches `CasesPanel.tsx` Props interface ✓
- `PipelinePanel` receives `activeCase: HomeOSCase | null`, `streamingEvents: AgentEvent[]`, `onSelectBlock: (blockId: number) => void`, `onSendMessage: (message: string) => void`, `chatChunks?: string` — matches `PipelinePanel.tsx` Props interface ✓
- `HomeOSDetailPanel` receives `block`, `profileText`, `onClose`, `onBack` — `onBack` already added in prior session ✓
- `investigateStream(profileText, 5)` yields `AgentEvent` — consumed into `accumulated: AgentEvent[]` ✓
- `chatInCase(activeCaseId, message)` yields `string` — accumulated into `full: string` ✓
- `HomeOSCase.avatar` typed as `HomeOSAvatar | null` — the cast `(profileSummary?.data as HomeOSCase["avatar"]) ?? null` is safe ✓
