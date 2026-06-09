# HomeOS AI Layer — Technical Requirements Document

**Date:** 2026-06-09
**Status:** Draft — pending approval
**Context:** HDB Match hackathon. Theme: Agents. Builds on the existing deterministic HomeOS agent system.

---

## 1. Goals

Replace the deterministic HomeOS pipeline with an LLM-powered multi-agent system that:

1. Parses household profiles with natural language understanding (not regex)
2. Has each agent produce a human-readable narrative alongside its raw evidence
3. Streams the agent pipeline live to the UI so the work is visible
4. Lets the user ask follow-up questions grounded in the case evidence
5. Groups all work into a **Case** — one Case per profile submission

The hackathon demo story:

> User types a household description → HomeOS opens a Case → five agents stream their reasoning live → shortlist appears on the map → user asks "why Bishan?" → AI justifies using agent evidence

---

## 2. Non-Goals

- No external messaging (WhatsApp, email, Telegram)
- No Case persistence across page refreshes (in-memory only for hackathon)
- No LLM re-investigation on follow-up (Q&A only, no shortlist mutation)
- No new data sources — agents read existing Repository data only

---

## 3. Agent Framework: Pydantic AI

### 3.1 Why Pydantic AI

- Native support for `AnthropicModel` and `OpenAIModel` (OpenRouter uses the OpenAI-compatible API)
- Provider swap is one line: `AnthropicModel("claude-haiku-4-5-20251001")` → `OpenAIModel("openai/gpt-4o-mini", base_url="https://openrouter.ai/api/v1", api_key=...)`
- Structured outputs via Pydantic models — agents return typed dataclasses, not raw dicts
- Built-in streaming support
- Lightweight — no LangChain graph model or heavy abstractions

### 3.2 Agent Definitions

Each HomeOS sub-agent is a `pydantic_ai.Agent` instance with:
- A system prompt describing its role
- A result type (Pydantic model) defining its structured output
- Access to the `Repository` via dependency injection

```python
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel

model = AnthropicModel("claude-haiku-4-5-20251001")

profile_agent = Agent(
    model,
    result_type=HomeOSAvatar,
    system_prompt="You are a Singapore HDB buyer advisor. Parse household descriptions into structured preferences.",
)

market_agent = Agent(
    model,
    result_type=MarketEvidence,
    system_prompt="You are an HDB market analyst. Summarise recent resale evidence for a buyer profile.",
)
```

### 3.3 Provider — Vercel AI Gateway (hackathon requirement)

The hackathon requires using **Vercel AI Gateway** as the LLM provider. It is OpenAI-compatible and accepts a single `AI_GATEWAY_API_KEY` that routes to any underlying model (Anthropic, Google Gemini, OpenAI, xAI, etc.).

`get_model()` auto-detects the gateway key and activates it automatically:

```python
def get_model():
    gateway_key = os.getenv("AI_GATEWAY_API_KEY", "")
    provider = os.getenv("LLM_PROVIDER", "vercel" if gateway_key else "test")
    model_name = os.getenv("LLM_MODEL", "google/gemini-2.0-flash")

    if provider == "vercel":
        from pydantic_ai.models.openai import OpenAIModel
        from pydantic_ai.providers.openai import OpenAIProvider
        return OpenAIModel(
            model_name,
            provider=OpenAIProvider(
                base_url="https://ai-gateway.vercel.sh/v1",
                api_key=gateway_key,
            ),
        )
    from pydantic_ai.models.test import TestModel
    return TestModel()  # CI/unit tests — no key needed
```

Setting just `AI_GATEWAY_API_KEY` in `.env` is sufficient; `LLM_PROVIDER` defaults to `vercel`.

### 3.4 Structured Output Types

Each agent returns a typed Pydantic model:

```python
class HomeOSAvatar(BaseModel):
    label: str
    buyer_type: Literal["family", "single", "couple", "investor"]
    summary: str
    preferences: HomeOSPreferences

class MarketEvidence(BaseModel):
    transaction_count: int
    median_price: float | None
    median_psf: float | None
    budget_signal: Literal["within_budget", "above_budget", "unknown"]
    confidence: Literal["high", "medium", "low"]
    narrative: str          # LLM-written sentence for the pipeline trace

class LocationEvidence(BaseModel):
    connections: list[Connection]
    narrative: str

class RiskEvidence(BaseModel):
    watchouts: list[str]
    score_adjustment: float
    narrative: str

class AgentQuestions(BaseModel):
    questions: list[str]
    narrative: str
```

### 3.5 Model

Default: `claude-haiku-4-5-20251001` for speed and cost. Override via `LLM_MODEL` env var.
Each agent call: max ~300 tokens output. Total per investigation (~5 blocks × 4 agents): ~6000 tokens.

---

## 4. Case

A Case is the unit of work for one investigation.

```python
@dataclass
class Case:
    case_id: str          # uuid4
    created_at: str       # ISO timestamp
    profile_text: str
    avatar: dict          # parsed by ProfileAgent
    pipeline: list[AgentEvent]   # ordered log of all agent events
    shortlist: list[dict]
    conversation: list[dict]     # {"role": "user"|"assistant", "content": str}
    status: Literal["running", "done", "error"]
```

Cases are stored in a module-level `dict[str, Case]` in `backend/app/services/homeos_case_store.py`. In-memory, no DB.

---

## 5. Agent Events (SSE Protocol)

Every agent emits a sequence of typed events over the SSE stream.

### Event Types

```python
# Agent begins work on a block (or on the profile for ProfileAgent)
AgentStart   = {"event": "agent_start",   "agent": str, "block_id": int | None}

# Raw evidence dict from the agent (same shape as existing deterministic output)
AgentData    = {"event": "agent_data",    "agent": str, "block_id": int | None, "data": dict}

# LLM-written one-paragraph narrative summarising what the agent found
AgentSummary = {"event": "agent_summary", "agent": str, "block_id": int | None, "narrative": str}

# Agent finished
AgentDone    = {"event": "agent_done",    "agent": str, "block_id": int | None}

# All agents done, shortlist ready
CaseDone     = {"event": "case_done",     "case_id": str, "shortlist": list[dict]}

# Unrecoverable error
CaseError    = {"event": "case_error",    "case_id": str, "message": str}
```

### Agent Sequence Per Investigation

```
ProfileAgent          (once, no block_id)
  → for each candidate block (up to limit):
      MarketAgent       (block_id)
      LocationAgent     (block_id)
      RiskAgent         (block_id)
      QuestionsAgent    (block_id)
  → WorthViewingScorer  (block_id, aggregates above agents)
CaseDone
```

---

## 6. Backend API Changes

### New Endpoints

#### `POST /homeos/investigate-stream`

Request:
```json
{ "profile_text": "Family, 800k, 4-room, near schools", "limit": 5 }
```

Response: `text/event-stream` (SSE). Each line is `data: <json>\n\n`.

Creates a Case, stores it, streams all agent events. When done, the Case is queryable via GET.

#### `GET /homeos/cases`

Returns all in-memory cases (list, newest first):
```json
[{ "case_id": "...", "created_at": "...", "profile_text": "...", "status": "done", "shortlist_count": 5 }]
```

#### `GET /homeos/cases/{case_id}`

Returns full Case including pipeline trace and shortlist.

#### `POST /homeos/cases/{case_id}/chat`

Request:
```json
{ "message": "Why did you pick Bishan over Tampines?" }
```

Response: `text/event-stream`. LLM streams an answer using the full case pipeline trace as context. Appends the exchange to `case.conversation`.

### Modified Endpoints

`POST /homeos/investigate` (existing) — keep as-is for non-streaming clients and tests. The new stream endpoint is additive.

---

## 7. LLM Prompts

### ProfileAgent prompt
```
You are a Singapore HDB property buyer advisor.
Parse this household description into structured buyer preferences.
Return JSON only. No explanation.

Schema: { buyer_type, flat_type, max_price, commute_priority, school_priority, risk_tolerance, appreciation_priority, label, summary }

Description: {profile_text}
```

### Per-agent narrative prompt (shared template)
```
You are a Singapore HDB analyst writing a one-sentence finding for a buyer.
Agent: {agent_name}
Evidence: {evidence_json}
Buyer profile: {avatar_summary}

Write one plain-English sentence (max 30 words) summarising what this evidence means for this buyer.
No markdown, no bullet points.
```

### Q&A prompt
```
You are HomeOS, an HDB buyer agent. Answer the buyer's question using only the evidence below.
Be direct, cite specific numbers. Max 150 words.

Case evidence:
{pipeline_trace_json}

Conversation so far:
{conversation_history}

Question: {user_message}
```

---

## 8. Frontend Layout

### Three-Column Layout

```
┌─────────────────┬──────────────────────┬─────────────────────┐
│  Cases (280px)  │   Map (flex-1)       │  Detail (320px)     │
│                 │                      │                      │
│  [+ New Case]   │  [blocks, markers]   │  STATE A: Pipeline  │
│                 │                      │  streaming agent log │
│  ● Case #1      │                      │                      │
│    Family 800k  │                      │  STATE B: Block      │
│    5 blocks     │                      │  detail panel        │
│                 │                      │  (on node click)     │
│  ● Case #2      │                      │                      │
│    Single, MRT  │                      │  [Chat input at      │
│    3 blocks     │                      │   bottom in State A] │
└─────────────────┴──────────────────────┴─────────────────────┘
```

### Left Panel: CasesPanel
- "New Case" button + profile text input at top
- Scrollable list of past cases (in-memory)
- Each case card: profile excerpt, timestamp, block count, status badge
- Clicking a case makes it the active case (populates pipeline panel)

### Right Panel: Shared detail slot

**State A — Pipeline** (default when case is active):
- Header: Case label + status
- Scrollable agent event log — each event renders as a row:
  - `agent_start` → spinner row "Market Agent analysing Blk 17…"
  - `agent_summary` → tick row with narrative text
  - `agent_done` → row completes
- Chat input pinned to bottom: text field + send button
- Chat responses stream inline below the pipeline log

**State B — Block Detail** (when map node clicked):
- Existing `HomeOSDetailPanel` content
- Back button → returns to State A

### Map
- No layout change
- Shortlisted blocks: violet markers
- Selected block: red marker
- `onSelectBlock` → switches right panel to State B

---

## 9. Frontend State

```typescript
// Global app state additions
cases: Case[]
activeCaseId: string | null
rightPanelState: "pipeline" | "block_detail"
selectedBlockId: number | null
```

A `Case` on the frontend mirrors the backend shape:
```typescript
interface Case {
  case_id: string
  created_at: string
  profile_text: string
  avatar: HomeOSAvatar | null
  pipeline: AgentEvent[]
  shortlist: HomeOSShortlistRow[]
  conversation: ChatMessage[]
  status: "running" | "done" | "error"
}
```

`AgentEvent` mirrors the SSE event types above.

---

## 10. File Structure

### Backend (new/modified)

| File | Change | Responsibility |
|---|---|---|
| `backend/app/services/homeos_ai_models.py` | Create | Pydantic output models for all agents (`HomeOSAvatar`, `MarketEvidence`, `LocationEvidence`, `RiskEvidence`, `AgentQuestions`) |
| `backend/app/services/homeos_ai_agents.py` | Create | Pydantic AI `Agent` instances for each sub-agent + `get_model()` provider factory |
| `backend/app/services/homeos_case_store.py` | Create | In-memory `Case` store: `create_case`, `get_case`, `list_cases`, `append_event`, `append_message` |
| `backend/app/services/homeos_agents.py` | Modify | Each agent calls its Pydantic AI agent, yields `AgentEvent`s including LLM narrative |
| `backend/app/services/homeos.py` | Modify | `investigate_stream` async generator, `chat_in_case` |
| `backend/app/api/schemas.py` | Modify | `HomeOSStreamRequest`, `HomeOSChatRequest` schemas |
| `backend/app/api/main.py` | Modify | Wire SSE + cases + chat endpoints |
| `backend/tests/test_homeos_ai_models.py` | Create | Pydantic model validation tests |
| `backend/tests/test_homeos_stream.py` | Create | Stream event sequence tests with `TestModel` (Pydantic AI's built-in test double) |

### Frontend (new/modified)

| File | Change | Responsibility |
|---|---|---|
| `frontend/src/types.ts` | Modify | `Case`, `AgentEvent`, `ChatMessage` types |
| `frontend/src/lib/api.ts` | Modify | `investigateStream()`, `getCases()`, `getCase()`, `chatInCase()` |
| `frontend/src/components/CasesPanel.tsx` | Create | Left panel: case list + new case input |
| `frontend/src/components/PipelinePanel.tsx` | Create | Right panel State A: streaming agent log + chat |
| `frontend/src/components/HomeOSDetailPanel.tsx` | Modify | Add back button for State B |
| `frontend/src/App.tsx` | Modify | Three-column layout, `rightPanelState`, `cases` state |

---

## 11. Testing Strategy

- LLM calls mocked in all unit tests via a `MockLLMProvider` that returns canned responses
- SSE stream tested by consuming the generator directly (no HTTP in unit tests)
- Frontend components tested with mocked API responses
- Manual end-to-end test: run backend + frontend, submit a profile, watch stream

---

## 12. Dependencies

Add to `backend/requirements.txt`:
```
pydantic-ai==0.0.14
```

Pydantic AI bundles the Anthropic SDK as an optional dependency. Install with:
```
pip install "pydantic-ai[anthropic]"
```

## 13. Environment Variables

| Var | Default | Description |
|---|---|---|
| `AI_GATEWAY_API_KEY` | — | **Required for hackathon demo.** Vercel AI Gateway key — auto-activates Vercel provider when set. |
| `LLM_MODEL` | `google/gemini-2.0-flash` | Gateway model string (`provider/model-name`). See vercel.com/ai-gateway/models. |
| `LLM_PROVIDER` | `vercel` (auto) | Override: `vercel`, `anthropic`, `openrouter`, or `test`. Defaults to `vercel` when `AI_GATEWAY_API_KEY` is set, `test` otherwise. |
| `ANTHROPIC_API_KEY` | — | Only needed if `LLM_PROVIDER=anthropic` (direct, bypasses gateway). |
| `OPENROUTER_API_KEY` | — | Only needed if `LLM_PROVIDER=openrouter`. |

---

## 14. Open Questions

- None — all decisions made in brainstorming session.
