# Case Detail: Instant Load + Per-Line Agent Provenance + Agent Trace

**Date:** 2026-06-10
**Status:** Approved design — ready for implementation plan

## Problem

Clicking a recommendation in the HomeOS detail panel has a ~5 second delay before the
"HomeOS evidence" section populates.

Root cause: the panel's open handler calls `getHomeOSCaseFile(block_id, profile_text)`
(`HomeOSDetailPanel.tsx:34`), which hits `POST /homeos/case-file/{block_id}`
(`api/main.py:259`) and runs `build_homeos_case_file()` (`homeos/pipeline.py:924`).
That function re-runs all four agents (`market_analysis_agent`, `location_graph_agent`,
`risk_value_agent`, `viewing_questions_agent`) from scratch, each re-querying the DB for
that one block.

This work was **already done** when the recommendation list was built. The streaming
pipeline (`_deep_analysis_stream`, `homeos/pipeline.py:201`) computes per-block evidence
and writes it into `case["pipeline"]` as events (`agent_data`, `tool_calls`,
`agent_summary`), retained in the in-memory case store (`homeos/case_store.py`). The
detail panel already receives `caseId` and `recommendation` props (`App.tsx:546-547`)
but ignores the stored data and recomputes.

Additional correctness issue: in **AI mode**, the streaming agents produce evidence via
LLM tool-calls (`pipeline.py:233-240`), while the click path recomputes with the
**sync, DB-only** agents. So clicking can show *different* evidence than what was
streamed.

## Goals

1. **Eliminate the 5s click delay** by reading the already-computed evidence from the
   case store instead of recomputing.
2. **Per-line agent provenance** — tag each reason / watchout with the agent that
   produced it (Market / Lifestyle / Risk).
3. **Agent trace** — surface each agent's inner working (tool calls, args, results) for
   the clicked block, which is already persisted in the case.

## Non-Goals

- Persisting cases across server restarts (store remains in-memory; out of scope).
- Changing the streaming pipeline's computation (we read what it already stores).
- Per-line provenance for **questions** — not honestly attributable (see below).

## Approach: A — read stored evidence (no recompute)

Chosen over (B) memoizing `build_homeos_case_file` (first click still cold/slow, doesn't
reuse streamed work) and (C) precomputing assembled case files inside the streaming loop
(modifies the hot path). Approach A reuses the exact evidence the user saw streamed, adds
no work to the streaming path, and degrades gracefully for blocks never analysed in a case.

### Backend

#### 1. `worth_viewing_score` → structured, attributed items

File: `backend/app/homeos/scoring.py:20`.

Change the return type of `reasons` / `watchouts` from `list[str]` to a list of items:

```python
class EvidenceItem(TypedDict):
    text: str
    source: Literal["market", "location", "risk"]
```

Every `reasons.append(...)` / `watchouts.append(...)` already sits in a branch that reads
exactly one agent's evidence dict, so tag at the point of generation:

- budget / transaction-count branches → `source="market"`
- MRT / primary-school / commute branches → `source="location"`
- the seed `watchouts = list(risk.get("watchouts", []))` and any `score_adjustment`
  driven lines → `source="risk"`

Return signature becomes
`tuple[float, list[EvidenceItem], list[EvidenceItem]]`.

**Ripple — update all consumers** that currently treat these as `list[str]`:
- `build_homeos_case_file` (`pipeline.py:940`) — `top_reasons` / `top_watchouts`.
- `_deep_analysis_stream` shortlist row construction and the `case_done` event payload
  (`pipeline.py:~364`).
- `investigate_homeos_profile` row construction (`pipeline.py:983-993`).
- Any place that joins reason/watchout strings (e.g. the schedule-viewing message,
  `pipeline.py:~1017` uses `agent_questions`, not reasons — verify during implementation).
  Provide a tiny helper `item_texts(items) -> list[str]` for any string-only consumer.

#### 2. `assemble_case_file_from_case(case_id, block_id)`

New function (new module `backend/app/homeos/case_assembler.py`, or alongside in
`pipeline.py`). Reads from the case store; performs **no DB recomputation**.

Steps:
1. `case = case_store.get_case(case_id)`; return `None` if absent.
2. Filter `case["pipeline"]` to events where `event.get("block_id") == block_id`.
3. Group by agent (`market`, `location`, `risk`); collect each agent's latest
   `agent_data` (evidence), all `tool_calls`, and `agent_summary` narrative.
4. If the block has no `agent_data` events in this case (was never analysed), return
   `None` → caller falls back to recompute.
5. Locate the shortlist row for `block_id` (carries `verdict`, `worth_viewing_score`,
   `top_reasons`, `top_watchouts` — now structured items).
6. Assemble the response in the **existing `HomeOSCaseFile` shape** plus a `trace` field:
   - `evidence.recent_sales` ← market `agent_data` (use `summary` if present, else
     `narrative`).
   - `evidence.connections` ← location `agent_data.connections`.
   - `evidence.future_signals` ← risk `agent_data` (`future_mrt`, `future_supply`).
   - `evidence.risks` ← watchout texts.
   - `evidence.agent_questions` ← stored questions if present, else compute via
     `viewing_questions_agent(assembled_evidence)` (pure templating from the assembled
     evidence, no DB).
   - `trace` ← new field (see schema below).

#### 3. Endpoint: optional `case_id`, with fallback

File: `backend/app/api/main.py:259`.

- Extend `HomeOSCaseFileRequest` with `case_id: str | None = None`.
- Handler logic:
  ```python
  if req.case_id:
      assembled = assemble_case_file_from_case(req.case_id, block_id)
      if assembled is not None:
          return assembled
  return build_homeos_case_file(repo, req.profile_text, block_id)  # fallback
  ```
- Keeps a single endpoint. Explore-mode clicks (no `case_id`) and non-shortlisted blocks
  transparently use the existing recompute path; `trace` is then empty/omitted.

#### Trace schema

```python
class TraceToolCall(TypedDict):
    tool_name: str
    args: Any
    result: NotRequired[Any]   # present when a matching ToolReturnPart was captured

class AgentTrace(TypedDict):
    agent: Literal["market", "location", "risk"]
    narrative: str             # from agent_summary
    tool_calls: list[TraceToolCall]
```

`tool_calls` data already exists via `_extract_tool_calls` (`pipeline.py:155`), which
captures `tool_name`, `args`, and `result`. Populated only in AI mode; empty in mock
mode (agents don't call tools there).

### Frontend

#### 4. Types — `frontend/src/types.ts`

```ts
export type AgentSource = "market" | "location" | "risk";
export interface EvidenceItem { text: string; source: AgentSource; }

export interface TraceToolCall { tool_name: string; args: unknown; result?: unknown; }
export interface AgentTrace { agent: AgentSource; narrative: string; tool_calls: TraceToolCall[]; }
```

- `HomeOSShortlistRow.top_reasons` / `top_watchouts`: `string[]` → `EvidenceItem[]`.
- `HomeOSCaseFile.top_reasons` / `top_watchouts`: `string[]` → `EvidenceItem[]`.
- `HomeOSCaseFile.trace?: AgentTrace[]`.

#### 5. API — `frontend/src/lib/api.ts:225`

`getHomeOSCaseFile(blockId, profileText, caseId?)` — include `case_id` in the POST body
when provided.

#### 6. Detail panel — `frontend/src/components/HomeOSDetailPanel.tsx`

- Pass `caseId` through to `getHomeOSCaseFile` in the open `useEffect` (`:34`).
- **`<AgentChip source>`** component. Label + colour map:
  - `market` → "Market" 🟢
  - `location` → "Lifestyle" 🔵
  - `risk` → "Risk" 🟠
  Render a chip next to each reason and each watchout. Chips render **instantly** from the
  `recommendation` prop (structured items), before the evidence fetch resolves.
- **Questions** section: render unchipped, labelled "Synthesised from all agents".
- **Key numbers**: unchipped (unchanged).
- **`<AgentTraceSection trace>`**: collapsed per-agent expanders (Market / Lifestyle /
  Risk). Each expander header shows a one-line summary (e.g. "2 tools"). Inside, each
  tool call shows `tool_name` + `args` inline and a one-line result summary with a
  `[⤢]` control to expand the full raw JSON result. **Hide the entire section when
  `trace` is empty/absent** (mock mode, or recompute fallback).

New components: `AgentChip`, `AgentTraceSection`, `ToolCallRow` (placement under the
existing `components/` directory, following current patterns).

## Data Flow (after)

1. User clicks a recommendation → panel opens with `recommendation` (structured reasons /
   watchouts) + `caseId`.
2. Chips render immediately from `recommendation`.
3. `useEffect` → `getHomeOSCaseFile(blockId, profileText, caseId)`.
4. Backend: `case_id` present and block in case → `assemble_case_file_from_case` returns
   stored evidence + trace (no recompute, ~instant).
5. Evidence text, questions, and the agent trace fill in.
6. No `caseId` / block not in case → recompute fallback (current behaviour); trace hidden.

## Testing

**Backend**
- `assemble_case_file_from_case` maps stored events → the `HomeOSCaseFile` shape
  (evidence + trace) for a block present in a case.
- Returns `None` when the case is missing or the block was never analysed → endpoint
  falls back to recompute.
- `worth_viewing_score` emits the correct `source` for each reason / watchout branch
  (budget→market, mrt/school/commute→location, seeded watchouts→risk).
- Endpoint: `case_id` present → assembler path; absent → recompute path.

**Frontend**
- Chips render from `EvidenceItem[]` with correct label/colour per source.
- Trace expanders collapse/expand; tool-call result summary expands to raw JSON.
- Trace section hidden when `trace` is empty.
- Questions render unchipped under the "Synthesised from all agents" label.

## Risks / Notes

- **`worth_viewing_score` return-shape change** is the largest ripple — mechanical but
  touches the shortlist row, `case_done` event, `investigate_homeos_profile`, and the
  frontend types. Land the backend shape change and all consumers together.
- **AI-mode vs mock-mode evidence shape**: assembler uses `summary ?? narrative` and
  tolerates missing `connections` / `future_signals` keys.
- **In-memory store**: after a server restart the case is gone; the endpoint's recompute
  fallback covers this (slow but correct).
- **Mock mode**: no tool calls recorded → trace section simply hidden; chips and instant
  evidence still work (evidence comes from stored `agent_data`).
```
