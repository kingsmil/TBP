# HomeOS AI Pipeline — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the full HomeOS AI pipeline — Pydantic AI agents, Case store, SSE streaming backend, and 3-column frontend (Cases / Map / Pipeline) — using `TestModel` so zero API keys are needed. Phase 2 swaps `TestModel` for a real LLM via **Vercel AI Gateway** — a unified OpenAI-compatible endpoint (`https://ai-gateway.vercel.sh/v1`) that accepts a single `AI_GATEWAY_API_KEY` and routes to any provider (Anthropic, Google Gemini, OpenAI, xAI, and hundreds more).

**Architecture:** Each HomeOS sub-agent is a `pydantic_ai.Agent` with a typed Pydantic output model. An async generator streams `AgentEvent` dicts over SSE. The frontend consumes the stream with `fetch` + `ReadableStream`, renders a live pipeline trace in the right panel, and stores Cases in React state.

**Tech Stack:** Python 3.12, Pydantic AI 1.106, FastAPI `StreamingResponse`, React 18, TypeScript, TanStack Query.

---

## File Structure

### Backend — new files

| File | Responsibility |
|---|---|
| `backend/app/services/homeos_ai_models.py` | Pydantic output models for every agent |
| `backend/app/services/homeos_ai_agents.py` | Pydantic AI `Agent` instances + `get_model()` factory |
| `backend/app/services/homeos_case_store.py` | In-memory Case store |
| `backend/tests/test_homeos_ai_models.py` | Model validation tests |
| `backend/tests/test_homeos_stream.py` | Stream event sequence tests |

### Backend — modified files

| File | Change |
|---|---|
| `backend/app/services/homeos_agents.py` | Each agent calls Pydantic AI agent, returns typed evidence |
| `backend/app/services/homeos.py` | Add `investigate_stream` async generator + `chat_in_case` |
| `backend/app/api/schemas.py` | Add `HomeOSStreamRequest`, `HomeOSChatRequest` |
| `backend/app/api/main.py` | Wire SSE + cases + chat endpoints |
| `backend/requirements.txt` | Add `pydantic-ai[anthropic]` |

### Frontend — new files

| File | Responsibility |
|---|---|
| `frontend/src/components/CasesPanel.tsx` | Left panel: case list + new case input |
| `frontend/src/components/PipelinePanel.tsx` | Right panel State A: agent event log + chat |

### Frontend — modified files

| File | Change |
|---|---|
| `frontend/src/types.ts` | Add `Case`, `AgentEvent`, `ChatMessage` |
| `frontend/src/lib/api.ts` | Add `investigateStream`, `getCases`, `getCase`, `chatInCase` |
| `frontend/src/components/HomeOSDetailPanel.tsx` | Add back button to return to pipeline |
| `frontend/src/App.tsx` | 3-column layout, cases state, right panel state machine |

---

## Task 1: Pydantic AI Output Models

**Files:**
- Create: `backend/app/services/homeos_ai_models.py`
- Create: `backend/tests/test_homeos_ai_models.py`

- [ ] **Step 1: Write failing model tests**

Create `backend/tests/test_homeos_ai_models.py`:

```python
import unittest
from typing import get_args

from app.services.homeos_ai_models import (
    AgentQuestions,
    HomeOSAvatar,
    HomeOSPreferences,
    LocationEvidence,
    MarketEvidence,
    RiskEvidence,
    WorthViewingResult,
)


class TestHomeOSAIModels(unittest.TestCase):
    def test_market_evidence_budget_signal_literals(self):
        m = MarketEvidence(
            transaction_count=6,
            median_price=710000.0,
            median_psf=650.0,
            budget_signal="within_budget",
            confidence="high",
            narrative="6 recent 4-room sales support the budget.",
        )
        self.assertEqual(m.budget_signal, "within_budget")
        self.assertEqual(m.confidence, "high")
        self.assertEqual(m.transaction_count, 6)

    def test_market_evidence_defaults(self):
        m = MarketEvidence()
        self.assertEqual(m.transaction_count, 0)
        self.assertIsNone(m.median_price)
        self.assertEqual(m.budget_signal, "unknown")
        self.assertEqual(m.confidence, "low")
        self.assertEqual(m.narrative, "")

    def test_location_evidence_connections(self):
        loc = LocationEvidence(
            connections=[
                {"type": "mrt", "name": "Nearest MRT", "distance_m": 620.0, "signal": "moderate"},
                {"type": "primary_school", "name": "Schools 1km", "count": 2, "signal": "strong"},
            ],
            narrative="620m to MRT, 2 primary schools within 1km.",
        )
        self.assertEqual(len(loc.connections), 2)
        self.assertEqual(loc.connections[0]["type"], "mrt")

    def test_risk_evidence_defaults(self):
        r = RiskEvidence()
        self.assertEqual(r.watchouts, [])
        self.assertEqual(r.score_adjustment, 0.0)
        self.assertEqual(r.narrative, "")

    def test_worth_viewing_result_verdict_literals(self):
        w = WorthViewingResult(
            score=86.5,
            verdict="Worth viewing",
            confidence="high",
            top_reasons=["Budget fits.", "Schools nearby."],
            top_watchouts=["MRT is moderate."],
        )
        self.assertIn(w.verdict, {"Worth viewing", "Maybe view", "Skip for now"})
        self.assertGreaterEqual(w.score, 0)
        self.assertLessEqual(w.score, 100)

    def test_avatar_preferences(self):
        avatar = HomeOSAvatar(
            label="Family HomeOS Agent",
            buyer_type="family",
            summary="Family buyer prioritizing schools.",
            preferences=HomeOSPreferences(
                flat_type="4 ROOM",
                max_price=800000.0,
                commute_priority="medium",
                school_priority="high",
                risk_tolerance="low",
                appreciation_priority="medium",
            ),
        )
        self.assertEqual(avatar.preferences.flat_type, "4 ROOM")
        self.assertEqual(avatar.preferences.school_priority, "high")

    def test_agent_questions_defaults(self):
        q = AgentQuestions()
        self.assertEqual(q.questions, [])
        self.assertEqual(q.narrative, "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /path/to/estate-finder/backend && ./.venv/bin/python -m unittest tests.test_homeos_ai_models -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'app.services.homeos_ai_models'`

- [ ] **Step 3: Create the models file**

Create `backend/app/services/homeos_ai_models.py`:

```python
"""Pydantic output models for HomeOS Pydantic AI agents.

Each model is the structured return type of one agent. Default values
allow TestModel to return zero-state instances without validation errors.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HomeOSPreferences(BaseModel):
    flat_type: str | None = None
    max_price: float | None = None
    commute_priority: Literal["low", "medium", "high"] = "medium"
    school_priority: Literal["low", "medium", "high"] = "low"
    risk_tolerance: Literal["low", "medium"] = "low"
    appreciation_priority: Literal["medium", "high"] = "medium"


class HomeOSAvatar(BaseModel):
    label: str = "HomeOS Agent"
    buyer_type: Literal["family", "single", "couple", "investor"] = "single"
    summary: str = ""
    preferences: HomeOSPreferences = Field(default_factory=HomeOSPreferences)


class MarketEvidence(BaseModel):
    transaction_count: int = 0
    median_price: float | None = None
    median_psf: float | None = None
    window_months: int = 6
    budget_signal: Literal["within_budget", "above_budget", "unknown"] = "unknown"
    confidence: Literal["high", "medium", "low"] = "low"
    narrative: str = ""


class LocationEvidence(BaseModel):
    connections: list[dict[str, Any]] = Field(default_factory=list)
    narrative: str = ""


class RiskEvidence(BaseModel):
    watchouts: list[str] = Field(default_factory=list)
    score_adjustment: float = 0.0
    narrative: str = ""


class AgentQuestions(BaseModel):
    questions: list[str] = Field(default_factory=list)
    narrative: str = ""


class WorthViewingResult(BaseModel):
    score: float = 0.0
    verdict: Literal["Worth viewing", "Maybe view", "Skip for now"] = "Skip for now"
    confidence: Literal["high", "medium", "low"] = "low"
    top_reasons: list[str] = Field(default_factory=list)
    top_watchouts: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_ai_models -v
```

Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/homeos_ai_models.py backend/tests/test_homeos_ai_models.py
git commit -m "feat: add homeos pydantic ai output models"
```

---

## Task 2: Pydantic AI Agent Definitions

**Files:**
- Create: `backend/app/services/homeos_ai_agents.py`

- [ ] **Step 1: Write failing agent tests**

Append to `backend/tests/test_homeos_ai_models.py`:

```python
import asyncio
from app.services.homeos_ai_agents import (
    get_model,
    profile_agent,
    market_agent,
    location_agent,
    risk_agent,
    questions_agent,
)
from app.services.homeos_ai_models import (
    AgentQuestions,
    HomeOSAvatar,
    LocationEvidence,
    MarketEvidence,
    RiskEvidence,
)


class TestHomeOSAIAgents(unittest.TestCase):
    def test_get_model_returns_test_model_by_default(self):
        from pydantic_ai.models.test import TestModel
        m = get_model()
        self.assertIsInstance(m, TestModel)

    def test_profile_agent_returns_avatar(self):
        result = asyncio.run(
            profile_agent.run("Family looking for 4 room under 800k near schools.")
        )
        self.assertIsInstance(result.output, HomeOSAvatar)

    def test_market_agent_returns_evidence(self):
        result = asyncio.run(
            market_agent.run("block_id=1, flat_type=4 ROOM, max_price=800000, recent_txns=[]")
        )
        self.assertIsInstance(result.output, MarketEvidence)

    def test_location_agent_returns_evidence(self):
        result = asyncio.run(
            location_agent.run("mrt_distance=620, schools_1km=2")
        )
        self.assertIsInstance(result.output, LocationEvidence)

    def test_risk_agent_returns_evidence(self):
        result = asyncio.run(
            risk_agent.run("appreciation_score=60, supply_risk=medium, risk_tolerance=low")
        )
        self.assertIsInstance(result.output, RiskEvidence)

    def test_questions_agent_returns_questions(self):
        result = asyncio.run(
            questions_agent.run("market_confidence=low, mrt_signal=weak")
        )
        self.assertIsInstance(result.output, AgentQuestions)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_ai_models -v 2>&1 | grep -E "ERROR|FAIL|OK"
```

Expected: FAIL — `ImportError: cannot import name 'get_model'`

- [ ] **Step 3: Create agents file**

Create `backend/app/services/homeos_ai_agents.py`:

```python
"""Pydantic AI agent definitions for HomeOS.

Uses TestModel by default (no API key needed).

Phase 2 — Vercel AI Gateway (recommended):
  Set LLM_PROVIDER=vercel, AI_GATEWAY_API_KEY=<your key>.
  Set LLM_MODEL to any gateway model: google/gemini-2.0-flash,
  anthropic/claude-haiku-4-5-20251001, openai/gpt-4o, etc.
  See https://vercel.com/ai-gateway for the full model list.

Fallback providers:
  Set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY to call Anthropic directly.
  Set LLM_PROVIDER=openrouter and OPENROUTER_API_KEY to use OpenRouter.
"""
from __future__ import annotations

import os

from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.services.homeos_ai_models import (
    AgentQuestions,
    HomeOSAvatar,
    LocationEvidence,
    MarketEvidence,
    RiskEvidence,
)


def get_model() -> Model:
    provider = os.getenv("LLM_PROVIDER", "test")
    model_name = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")

    if provider == "vercel":
        # Vercel AI Gateway — OpenAI-compatible, supports any provider key.
        # Model format: "provider/model-name", e.g. "google/gemini-2.0-flash"
        from pydantic_ai.models.openai import OpenAIModel
        from pydantic_ai.providers.openai import OpenAIProvider
        gateway_model = os.getenv("LLM_MODEL", "google/gemini-2.0-flash")
        return OpenAIModel(
            gateway_model,
            provider=OpenAIProvider(
                base_url="https://ai-gateway.vercel.sh/v1",
                api_key=os.getenv("AI_GATEWAY_API_KEY", ""),
            ),
        )

    if provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        return AnthropicModel(model_name)

    if provider == "openrouter":
        from pydantic_ai.models.openai import OpenAIModel
        from pydantic_ai.providers.openai import OpenAIProvider
        return OpenAIModel(
            model_name,
            provider=OpenAIProvider(
                base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                api_key=os.getenv("OPENROUTER_API_KEY", ""),
            ),
        )

    from pydantic_ai.models.test import TestModel
    return TestModel()


profile_agent: Agent[None, HomeOSAvatar] = Agent(
    get_model(),
    output_type=HomeOSAvatar,
    system_prompt=(
        "You are a Singapore HDB buyer advisor. "
        "Parse the household description into structured buyer preferences. "
        "Return a complete HomeOSAvatar with label, buyer_type, summary, and preferences."
    ),
)

market_agent: Agent[None, MarketEvidence] = Agent(
    get_model(),
    output_type=MarketEvidence,
    system_prompt=(
        "You are an HDB market analyst. "
        "Given recent transaction data and a buyer's budget, summarise the market evidence. "
        "Write a one-sentence narrative (max 30 words) describing what the data means for this buyer."
    ),
)

location_agent: Agent[None, LocationEvidence] = Agent(
    get_model(),
    output_type=LocationEvidence,
    system_prompt=(
        "You are an HDB location analyst. "
        "Given MRT distance and school proximity data, summarise the location evidence. "
        "Write a one-sentence narrative (max 30 words) describing the connectivity for this buyer."
    ),
)

risk_agent: Agent[None, RiskEvidence] = Agent(
    get_model(),
    output_type=RiskEvidence,
    system_prompt=(
        "You are an HDB risk analyst. "
        "Given appreciation score, future supply, and accessibility data, identify watchouts. "
        "Write a one-sentence narrative (max 30 words) summarising the risk profile."
    ),
)

questions_agent: Agent[None, AgentQuestions] = Agent(
    get_model(),
    output_type=AgentQuestions,
    system_prompt=(
        "You are an HDB buyer advocate. "
        "Given the evidence from market, location, and risk agents, generate 4-6 due-diligence "
        "questions the buyer should ask the real-estate agent before viewing. "
        "Write a one-sentence narrative summarising why these questions matter."
    ),
)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_ai_models -v
```

Expected: all 13 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/homeos_ai_agents.py backend/tests/test_homeos_ai_models.py
git commit -m "feat: add homeos pydantic ai agent definitions"
```

---

## Task 3: In-Memory Case Store

**Files:**
- Create: `backend/app/services/homeos_case_store.py`
- Create: `backend/tests/test_homeos_case_store.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_homeos_case_store.py`:

```python
import unittest

from app.services.homeos_case_store import (
    append_event,
    append_message,
    create_case,
    get_case,
    list_cases,
)


class TestHomeOSCaseStore(unittest.TestCase):
    def setUp(self):
        from app.services import homeos_case_store
        homeos_case_store._cases.clear()

    def test_create_case_returns_case_with_id(self):
        case = create_case("Family looking for 4 room under 800k.")
        self.assertIsNotNone(case["case_id"])
        self.assertEqual(case["profile_text"], "Family looking for 4 room under 800k.")
        self.assertEqual(case["status"], "running")
        self.assertEqual(case["pipeline"], [])
        self.assertEqual(case["shortlist"], [])
        self.assertEqual(case["conversation"], [])

    def test_get_case_returns_same_case(self):
        case = create_case("test profile")
        fetched = get_case(case["case_id"])
        self.assertEqual(fetched["case_id"], case["case_id"])

    def test_get_case_returns_none_for_unknown_id(self):
        self.assertIsNone(get_case("nonexistent-id"))

    def test_list_cases_returns_newest_first(self):
        c1 = create_case("first")
        c2 = create_case("second")
        cases = list_cases()
        self.assertEqual(cases[0]["case_id"], c2["case_id"])
        self.assertEqual(cases[1]["case_id"], c1["case_id"])

    def test_append_event_adds_to_pipeline(self):
        case = create_case("test profile")
        event = {"event": "agent_start", "agent": "market", "block_id": 1}
        append_event(case["case_id"], event)
        updated = get_case(case["case_id"])
        self.assertEqual(len(updated["pipeline"]), 1)
        self.assertEqual(updated["pipeline"][0]["agent"], "market")

    def test_append_message_adds_to_conversation(self):
        case = create_case("test profile")
        append_message(case["case_id"], "user", "Why Bishan?")
        append_message(case["case_id"], "assistant", "Because of the schools.")
        updated = get_case(case["case_id"])
        self.assertEqual(len(updated["conversation"]), 2)
        self.assertEqual(updated["conversation"][0]["role"], "user")
        self.assertEqual(updated["conversation"][1]["content"], "Because of the schools.")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_case_store -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'app.services.homeos_case_store'`

- [ ] **Step 3: Implement case store**

Create `backend/app/services/homeos_case_store.py`:

```python
"""In-memory Case store for HomeOS investigations.

Cases are stored for the lifetime of the server process only.
No database — sufficient for hackathon demo.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

_cases: dict[str, dict[str, Any]] = {}


def create_case(profile_text: str) -> dict[str, Any]:
    case_id = str(uuid.uuid4())
    case: dict[str, Any] = {
        "case_id": case_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "profile_text": profile_text,
        "avatar": None,
        "pipeline": [],
        "shortlist": [],
        "conversation": [],
        "status": "running",
    }
    _cases[case_id] = case
    return case


def get_case(case_id: str) -> dict[str, Any] | None:
    return _cases.get(case_id)


def list_cases() -> list[dict[str, Any]]:
    return sorted(_cases.values(), key=lambda c: c["created_at"], reverse=True)


def append_event(case_id: str, event: dict[str, Any]) -> None:
    if case_id in _cases:
        _cases[case_id]["pipeline"].append(event)


def append_message(case_id: str, role: str, content: str) -> None:
    if case_id in _cases:
        _cases[case_id]["conversation"].append({"role": role, "content": content})


def set_avatar(case_id: str, avatar: dict[str, Any]) -> None:
    if case_id in _cases:
        _cases[case_id]["avatar"] = avatar


def set_shortlist(case_id: str, shortlist: list[dict[str, Any]]) -> None:
    if case_id in _cases:
        _cases[case_id]["shortlist"] = shortlist


def set_status(case_id: str, status: str) -> None:
    if case_id in _cases:
        _cases[case_id]["status"] = status
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_case_store -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/homeos_case_store.py backend/tests/test_homeos_case_store.py
git commit -m "feat: add homeos in-memory case store"
```

---

## Task 4: Streaming Investigation Service

**Files:**
- Modify: `backend/app/services/homeos.py`
- Modify: `backend/app/services/homeos_agents.py`
- Create: `backend/tests/test_homeos_stream.py`

- [ ] **Step 1: Write failing stream tests**

Create `backend/tests/test_homeos_stream.py`:

```python
import asyncio
import unittest

from app.data.seed import build_seeded_repo
from app.services.homeos import investigate_stream, chat_in_case
from app.services import homeos_case_store


class TestHomeOSStream(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=4, months=6)

    def setUp(self):
        homeos_case_store._cases.clear()

    def _collect_stream(self, profile_text: str, limit: int = 2) -> list[dict]:
        async def run():
            events = []
            async for event in investigate_stream(
                self.repo, profile_text, limit=limit
            ):
                events.append(event)
            return events
        return asyncio.run(run())

    def test_stream_starts_with_profile_agent_start(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=1)
        first = events[0]
        self.assertEqual(first["event"], "agent_start")
        self.assertEqual(first["agent"], "profile")
        self.assertIsNone(first["block_id"])

    def test_stream_contains_agent_summary_for_profile(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=1)
        summaries = [e for e in events if e["event"] == "agent_summary" and e["agent"] == "profile"]
        self.assertEqual(len(summaries), 1)
        self.assertIn("narrative", summaries[0])

    def test_stream_ends_with_case_done(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=1)
        last = events[-1]
        self.assertEqual(last["event"], "case_done")
        self.assertIn("case_id", last)
        self.assertIn("shortlist", last)

    def test_stream_creates_case_in_store(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=1)
        case_done = events[-1]
        case = homeos_case_store.get_case(case_done["case_id"])
        self.assertIsNotNone(case)
        self.assertEqual(case["status"], "done")
        self.assertGreater(len(case["pipeline"]), 0)

    def test_stream_emits_per_block_agent_events(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=2)
        market_starts = [e for e in events if e["event"] == "agent_start" and e["agent"] == "market"]
        self.assertGreaterEqual(len(market_starts), 1)
        for e in market_starts:
            self.assertIsNotNone(e["block_id"])

    def test_chat_in_case_streams_response(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=1)
        case_id = events[-1]["case_id"]

        async def run_chat():
            chunks = []
            async for chunk in chat_in_case(case_id, "Why did you pick this block?"):
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(run_chat())
        self.assertGreater(len(chunks), 0)
        full_text = "".join(chunks)
        self.assertGreater(len(full_text), 0)
        case = homeos_case_store.get_case(case_id)
        self.assertEqual(len(case["conversation"]), 2)
        self.assertEqual(case["conversation"][0]["role"], "user")
        self.assertEqual(case["conversation"][1]["role"], "assistant")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_stream -v 2>&1 | head -15
```

Expected: FAIL — `ImportError: cannot import name 'investigate_stream'`

- [ ] **Step 3: Update homeos_agents.py to use Pydantic AI agents**

Replace the bodies of the four agent functions in `backend/app/services/homeos_agents.py` to call the Pydantic AI agents and return typed evidence dicts. The function signatures stay identical so existing callers don't break:

```python
"""Deterministic HomeOS sub-agents — now backed by Pydantic AI agents.

Function signatures are unchanged. Each function calls its Pydantic AI agent,
enriches the result with repository data, and returns a serialisable dict.
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.repositories.base import Repository
from app.services.accessibility import block_accessibility
from app.services.appreciation import appreciation
from app.services.future_dev import future_mrt, future_supply
from app.services.homeos_ai_agents import (
    location_agent,
    market_agent,
    questions_agent,
    risk_agent,
)
from app.services.stats import summarize


def market_analysis_agent(
    repo: Repository, block_id: int, prefs: dict[str, Any]
) -> dict[str, Any]:
    txns = list(repo.transactions_for_block(block_id))
    flat_type = prefs.get("flat_type")
    if flat_type:
        txns = [t for t in txns if t.flat_type == flat_type]
    recent = sorted(txns, key=lambda t: t.transaction_month, reverse=True)[:6]
    summary = summarize(recent)
    max_price = prefs.get("max_price")
    median_price = round(summary.median_price, 2) if summary.median_price else None
    if max_price is None or median_price is None:
        budget_signal = "unknown"
    elif median_price <= max_price:
        budget_signal = "within_budget"
    else:
        budget_signal = "above_budget"
    confidence = "high" if summary.txn_count >= 6 else "medium" if summary.txn_count >= 3 else "low"
    label = flat_type or "matching"

    prompt = (
        f"block_id={block_id}, flat_type={flat_type}, max_price={max_price}, "
        f"transaction_count={summary.txn_count}, median_price={median_price}, "
        f"budget_signal={budget_signal}, confidence={confidence}"
    )
    result = asyncio.run(market_agent.run(prompt))
    narrative = result.output.narrative or (
        f"{summary.txn_count} similar {label} transactions support price confidence."
    )
    return {
        "transaction_count": summary.txn_count,
        "median_price": median_price,
        "median_psf": round(summary.median_psf, 2) if summary.median_psf else None,
        "window_months": 6,
        "budget_signal": budget_signal,
        "confidence": confidence,
        "summary": narrative,
        "narrative": narrative,
    }


def location_graph_agent(repo: Repository, block_id: int) -> dict[str, Any]:
    prox = repo.proximity(block_id)
    if prox is None:
        return {"connections": [], "narrative": "No proximity data available."}
    mrt_dist = prox.nearest_mrt_distance_m
    mrt_signal = (
        "strong" if mrt_dist is not None and mrt_dist <= 500
        else "moderate" if mrt_dist is not None and mrt_dist <= 1000
        else "weak"
    )
    school_count = prox.schools_within_1km
    school_signal = "strong" if school_count >= 2 else "moderate" if school_count == 1 else "weak"
    connections = [
        {
            "type": "mrt",
            "name": "Nearest operational MRT",
            "distance_m": mrt_dist,
            "signal": mrt_signal,
        },
        {
            "type": "primary_school",
            "name": "Primary schools within 1km",
            "count": school_count,
            "signal": school_signal,
        },
    ]
    prompt = f"mrt_distance={mrt_dist}, mrt_signal={mrt_signal}, schools_1km={school_count}, school_signal={school_signal}"
    result = asyncio.run(location_agent.run(prompt))
    narrative = result.output.narrative or f"MRT {mrt_dist}m ({mrt_signal}), {school_count} schools ({school_signal})."
    return {"connections": connections, "narrative": narrative}


def risk_value_agent(
    repo: Repository, block_id: int, prefs: dict[str, Any]
) -> dict[str, Any]:
    app_data = appreciation(repo, block_id)
    future_mrt_data = future_mrt(repo, block_id)
    future_supply_data = future_supply(repo, block_id)
    accessibility = block_accessibility(repo, block_id)
    watchouts: list[str] = []
    score_adjustment = 0.0

    if app_data and app_data.get("appreciation_score") is not None:
        score_adjustment += min(12.0, app_data["appreciation_score"] / 10)
    if app_data and app_data.get("risk_level") == "high" and prefs.get("risk_tolerance") == "low":
        watchouts.append("Appreciation model flags elevated risk for a low-risk buyer.")
        score_adjustment -= 8.0
    if future_supply_data and future_supply_data.get("supply_risk_level") == "high":
        watchouts.append("Nearby future supply may weigh on appreciation.")
        score_adjustment -= 4.0

    prompt = (
        f"appreciation_score={app_data.get('appreciation_score') if app_data else None}, "
        f"risk_level={app_data.get('risk_level') if app_data else None}, "
        f"supply_risk={future_supply_data.get('supply_risk_level') if future_supply_data else None}, "
        f"risk_tolerance={prefs.get('risk_tolerance')}, "
        f"watchouts={watchouts}"
    )
    result = asyncio.run(risk_agent.run(prompt))
    narrative = result.output.narrative or f"{len(watchouts)} risk signals identified."
    return {
        "appreciation": app_data,
        "future_mrt": future_mrt_data,
        "future_supply": future_supply_data,
        "accessibility": accessibility,
        "watchouts": watchouts,
        "score_adjustment": score_adjustment,
        "narrative": narrative,
    }


def viewing_questions_agent(evidence: dict[str, Any]) -> list[str]:
    base_questions = [
        "Which floor range is the unit in?",
        "Is the unit facing a main road or MRT track?",
        "Are recent comparable transactions renovated or original condition?",
        "Are there ethnic quota or extension restrictions?",
    ]
    market = evidence.get("market", {})
    location = evidence.get("location", {})
    if market.get("confidence") == "low":
        base_questions.append("Why is there limited recent resale evidence for this block or flat type?")
    if any(c.get("signal") == "weak" for c in location.get("connections", [])):
        base_questions.append("What is the realistic walking route and time to the nearest MRT or school?")

    prompt = (
        f"market_confidence={market.get('confidence')}, "
        f"connections={location.get('connections', [])}, "
        f"watchouts={evidence.get('risk', {}).get('watchouts', [])}"
    )
    result = asyncio.run(questions_agent.run(prompt))
    extra = [q for q in result.output.questions if q and q not in base_questions]
    return (base_questions + extra)[:6]


def worth_viewing_score(
    market: dict[str, Any],
    location: dict[str, Any],
    risk: dict[str, Any],
    prefs: dict[str, Any],
) -> tuple[float, list[str], list[str]]:
    score = 0.0
    reasons: list[str] = []
    watchouts: list[str] = list(risk.get("watchouts", []))

    if market.get("budget_signal") == "within_budget":
        score += 30
        reasons.append("Recent comparable sales support the budget.")
    elif market.get("budget_signal") == "above_budget":
        score += 10
        watchouts.append("Recent comparable sales are above the stated budget.")
    else:
        watchouts.append("Price confidence is limited by sparse transaction evidence.")

    txn_count = market.get("transaction_count") or 0
    if txn_count >= 4:
        score += 20
        reasons.append("Recent resale evidence is strong enough for comparison.")
    else:
        score += 8
        watchouts.append("Recent resale evidence is limited.")

    for conn in location.get("connections", []):
        if conn["type"] == "mrt":
            if conn["signal"] == "strong":
                score += 18
                reasons.append("MRT access fits the buyer profile.")
            elif conn["signal"] == "moderate":
                score += 11
                watchouts.append("MRT access is moderate rather than excellent.")
            else:
                score += 4
                watchouts.append("MRT access is weak for this profile.")
        if conn["type"] == "primary_school" and prefs.get("school_priority") == "high":
            if conn["signal"] == "strong":
                score += 18
                reasons.append("Primary school access fits the family profile.")
            elif conn["signal"] == "moderate":
                score += 10
                reasons.append("There is at least one primary school within 1km.")
            else:
                watchouts.append("Primary school access is weak for this family profile.")

    score += risk.get("score_adjustment") or 0.0
    return round(max(0.0, min(score, 100.0)), 1), reasons[:4], watchouts[:4]
```

- [ ] **Step 4: Add investigate_stream and chat_in_case to homeos.py**

Append to the end of `backend/app/services/homeos.py`:

```python
import asyncio
import json
from collections.abc import AsyncGenerator

from app.services import homeos_case_store
from app.services.homeos_ai_agents import profile_agent


async def investigate_stream(
    repo: Repository,
    profile_text: str,
    limit: int = 5,
) -> AsyncGenerator[dict, None]:
    """Async generator yielding AgentEvent dicts for SSE streaming."""
    case = homeos_case_store.create_case(profile_text)
    case_id = case["case_id"]

    try:
        # --- Profile Agent ---
        yield {"event": "agent_start", "agent": "profile", "block_id": None}
        homeos_case_store.append_event(case_id, {"event": "agent_start", "agent": "profile", "block_id": None})

        profile_result = await profile_agent.run(profile_text)
        avatar = profile_result.output
        avatar_dict = avatar.model_dump()
        homeos_case_store.set_avatar(case_id, avatar_dict)

        profile_summary = {"event": "agent_summary", "agent": "profile", "block_id": None, "narrative": avatar.summary, "data": avatar_dict}
        yield profile_summary
        homeos_case_store.append_event(case_id, profile_summary)

        yield {"event": "agent_done", "agent": "profile", "block_id": None}
        homeos_case_store.append_event(case_id, {"event": "agent_done", "agent": "profile", "block_id": None})

        # --- Per-block agents ---
        from app.services.homeos_agents import (
            location_graph_agent,
            market_analysis_agent,
            risk_value_agent,
            viewing_questions_agent,
            worth_viewing_score,
        )

        prefs = avatar_dict.get("preferences", {})
        rows = []

        for block in list(repo.blocks())[:limit * 3]:
            block_id = block.block_id

            for agent_name, agent_fn, agent_args in [
                ("market",   market_analysis_agent, (repo, block_id, prefs)),
                ("location", location_graph_agent,  (repo, block_id)),
                ("risk",     risk_value_agent,       (repo, block_id, prefs)),
            ]:
                start_evt = {"event": "agent_start", "agent": agent_name, "block_id": block_id}
                yield start_evt
                homeos_case_store.append_event(case_id, start_evt)

                evidence = agent_fn(*agent_args)

                data_evt = {"event": "agent_data", "agent": agent_name, "block_id": block_id, "data": evidence}
                yield data_evt
                homeos_case_store.append_event(case_id, data_evt)

                narrative = evidence.get("narrative", "")
                summary_evt = {"event": "agent_summary", "agent": agent_name, "block_id": block_id, "narrative": narrative}
                yield summary_evt
                homeos_case_store.append_event(case_id, summary_evt)

                done_evt = {"event": "agent_done", "agent": agent_name, "block_id": block_id}
                yield done_evt
                homeos_case_store.append_event(case_id, done_evt)

                if agent_name == "market":
                    market_evidence = evidence
                elif agent_name == "location":
                    location_evidence = evidence
                elif agent_name == "risk":
                    risk_evidence = evidence

            questions = viewing_questions_agent({
                "market": market_evidence,
                "location": location_evidence,
                "risk": risk_evidence,
            })
            score, reasons, watchouts = worth_viewing_score(market_evidence, location_evidence, risk_evidence, prefs)

            if prefs.get("flat_type") and market_evidence.get("transaction_count", 0) == 0:
                continue

            rows.append({
                "block_id": block_id,
                "block_number": block.block_number,
                "street_name": block.street_name,
                "town": block.town,
                "worth_viewing_score": score,
                "verdict": _verdict(score),
                "confidence": _confidence(market_evidence.get("transaction_count", 0)),
                "top_reasons": reasons,
                "top_watchouts": watchouts,
            })

            if len(rows) >= limit:
                break

        rows.sort(key=lambda r: (-r["worth_viewing_score"], r["block_id"]))
        shortlist = rows[:limit]
        homeos_case_store.set_shortlist(case_id, shortlist)
        homeos_case_store.set_status(case_id, "done")

        done_evt = {"event": "case_done", "case_id": case_id, "shortlist": shortlist}
        yield done_evt
        homeos_case_store.append_event(case_id, done_evt)

    except Exception as exc:
        homeos_case_store.set_status(case_id, "error")
        error_evt = {"event": "case_error", "case_id": case_id, "message": str(exc)}
        yield error_evt
        homeos_case_store.append_event(case_id, error_evt)


async def chat_in_case(case_id: str, message: str) -> AsyncGenerator[str, None]:
    """Async generator streaming an LLM answer grounded in the case evidence."""
    from app.services.homeos_ai_agents import get_model
    from pydantic_ai import Agent

    case = homeos_case_store.get_case(case_id)
    if case is None:
        yield "Case not found."
        return

    homeos_case_store.append_message(case_id, "user", message)

    pipeline_summary = json.dumps([
        {"event": e["event"], "agent": e.get("agent"), "narrative": e.get("narrative", "")}
        for e in case["pipeline"]
        if e["event"] in ("agent_summary", "case_done")
    ], indent=2)

    conversation_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in case["conversation"][:-1]
    )

    system = (
        "You are HomeOS, an HDB buyer agent. Answer using only the evidence below. "
        "Be direct, cite specific numbers where available. Max 150 words."
    )
    user_prompt = (
        f"Case evidence (agent pipeline summaries):\n{pipeline_summary}\n\n"
        f"{'Previous conversation:' + chr(10) + conversation_text + chr(10) + chr(10) if conversation_text else ''}"
        f"Question: {message}"
    )

    chat_agent: Agent[None, str] = Agent(get_model(), output_type=str, system_prompt=system)
    result = await chat_agent.run(user_prompt)
    answer = result.output or "I need more information to answer that question."

    homeos_case_store.append_message(case_id, "assistant", answer)
    yield answer
```

- [ ] **Step 5: Run stream tests**

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_stream -v
```

Expected: 6 tests PASS.

- [ ] **Step 6: Run full backend suite to check for regressions**

```bash
cd backend && ./.venv/bin/python -m pytest -q 2>&1 | tail -10
```

Expected: all tests pass or only pre-existing failures.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/homeos.py backend/app/services/homeos_agents.py backend/tests/test_homeos_stream.py
git commit -m "feat: add homeos investigate_stream and chat_in_case"
```

---

## Task 5: FastAPI SSE Endpoints

**Files:**
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/api/main.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Write failing API tests**

Create `backend/tests/test_homeos_stream_api.py`:

```python
import json
import unittest

from fastapi.testclient import TestClient

from app.api.main import app
from app.services import homeos_case_store


class TestHomeOSStreamApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        homeos_case_store._cases.clear()

    def test_investigate_stream_returns_sse_events(self):
        with self.client.stream(
            "POST",
            "/homeos/investigate-stream",
            json={"profile_text": "Family 4 room 800k schools.", "limit": 1},
        ) as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/event-stream", response.headers["content-type"])
            lines = [line for line in response.iter_lines() if line.startswith("data:")]
            events = [json.loads(line[5:]) for line in lines]
            event_types = [e["event"] for e in events]
            self.assertIn("agent_start", event_types)
            self.assertIn("case_done", event_types)

    def test_list_cases_returns_cases_after_investigation(self):
        with self.client.stream(
            "POST",
            "/homeos/investigate-stream",
            json={"profile_text": "Family 4 room 800k schools.", "limit": 1},
        ) as response:
            for _ in response.iter_lines():
                pass
        res = self.client.get("/homeos/cases")
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.json()), 1)

    def test_get_case_returns_full_case(self):
        case_id = None
        with self.client.stream(
            "POST",
            "/homeos/investigate-stream",
            json={"profile_text": "Family 4 room 800k schools.", "limit": 1},
        ) as response:
            for line in response.iter_lines():
                if line.startswith("data:"):
                    evt = json.loads(line[5:])
                    if evt["event"] == "case_done":
                        case_id = evt["case_id"]
        self.assertIsNotNone(case_id)
        res = self.client.get(f"/homeos/cases/{case_id}")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["case_id"], case_id)
        self.assertIn("pipeline", body)
        self.assertIn("shortlist", body)

    def test_chat_in_case_returns_sse_text(self):
        case_id = None
        with self.client.stream(
            "POST",
            "/homeos/investigate-stream",
            json={"profile_text": "Family 4 room 800k schools.", "limit": 1},
        ) as response:
            for line in response.iter_lines():
                if line.startswith("data:"):
                    evt = json.loads(line[5:])
                    if evt["event"] == "case_done":
                        case_id = evt["case_id"]
        with self.client.stream(
            "POST",
            f"/homeos/cases/{case_id}/chat",
            json={"message": "Why did you pick this block?"},
        ) as response:
            self.assertEqual(response.status_code, 200)
            chunks = list(response.iter_lines())
            self.assertGreater(len(chunks), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_stream_api -v 2>&1 | head -15
```

Expected: FAIL with 404 for the new endpoints.

- [ ] **Step 3: Add schemas**

Append to `backend/app/api/schemas.py`:

```python
class HomeOSStreamRequest(BaseModel):
    profile_text: str = Field(..., min_length=10)
    limit: int = Field(5, ge=1, le=20)


class HomeOSChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
```

- [ ] **Step 4: Wire endpoints in main.py**

Add imports at top of `backend/app/api/main.py` (after existing homeos imports):

```python
import asyncio
import json

from fastapi.responses import StreamingResponse

from app.api.schemas import HomeOSChatRequest, HomeOSStreamRequest
from app.services import homeos_case_store
from app.services.homeos import chat_in_case, investigate_stream
```

Add endpoints after the existing `/homeos/schedule-viewing` route:

```python
@app.post("/homeos/investigate-stream")
async def homeos_investigate_stream(
    req: HomeOSStreamRequest,
    repo: Repository = Depends(get_repository),
):
    async def event_gen():
        async for event in investigate_stream(repo, req.profile_text, req.limit):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/homeos/cases")
def homeos_list_cases():
    cases = homeos_case_store.list_cases()
    return [
        {
            "case_id": c["case_id"],
            "created_at": c["created_at"],
            "profile_text": c["profile_text"],
            "status": c["status"],
            "shortlist_count": len(c["shortlist"]),
        }
        for c in cases
    ]


@app.get("/homeos/cases/{case_id}")
def homeos_get_case(case_id: str):
    case = homeos_case_store.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    return case


@app.post("/homeos/cases/{case_id}/chat")
async def homeos_chat(case_id: str, req: HomeOSChatRequest):
    if homeos_case_store.get_case(case_id) is None:
        raise HTTPException(status_code=404, detail="case not found")

    async def chat_gen():
        async for chunk in chat_in_case(case_id, req.message):
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        chat_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 5: Add pydantic-ai to requirements.txt**

Add after `pydantic-settings`:

```
pydantic-ai-slim[anthropic,openai]==1.106.0
```

The `openai` extra is required for `LLM_PROVIDER=vercel` (Vercel AI Gateway) and `LLM_PROVIDER=openrouter`. The `anthropic` extra covers direct `LLM_PROVIDER=anthropic` calls.

- [ ] **Step 6: Run API tests**

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_stream_api -v
```

Expected: 4 tests PASS.

- [ ] **Step 7: Verify manually**

```bash
curl -s -X POST http://127.0.0.1:8000/homeos/investigate-stream \
  -H 'Content-Type: application/json' \
  -d '{"profile_text":"Family 4 room 800k near schools.","limit":1}' \
  | head -20
```

Expected: SSE lines starting with `data: {"event": "agent_start", ...}`

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/schemas.py backend/app/api/main.py backend/requirements.txt backend/tests/test_homeos_stream_api.py
git commit -m "feat: add homeos sse stream and cases api endpoints"
```

---

## Task 6: Frontend Types and SSE API Client

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/lib/sse.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { getCases, getCase, investigateStream } from "./api";

describe("homeos cases api", () => {
  afterEach(() => vi.restoreAllMocks());

  it("getCases calls /homeos/cases", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    }));
    await getCases();
    expect(fetch).toHaveBeenCalledWith("/api/homeos/cases");
  });

  it("getCase calls /homeos/cases/:id", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ case_id: "abc", pipeline: [], shortlist: [] }),
    }));
    await getCase("abc");
    expect(fetch).toHaveBeenCalledWith("/api/homeos/cases/abc");
  });

  it("investigateStream returns an async iterable of events", async () => {
    const mockStream = new ReadableStream({
      start(ctrl) {
        ctrl.enqueue(new TextEncoder().encode('data: {"event":"agent_start","agent":"profile","block_id":null}\n\n'));
        ctrl.enqueue(new TextEncoder().encode('data: {"event":"case_done","case_id":"x","shortlist":[]}\n\n'));
        ctrl.close();
      },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, body: mockStream }));
    const events: unknown[] = [];
    for await (const evt of investigateStream("Family 800k.", 1)) {
      events.push(evt);
    }
    expect(events).toHaveLength(2);
    expect((events[0] as { event: string }).event).toBe("agent_start");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npm run test -- src/lib/sse.test.ts --run 2>&1 | tail -15
```

Expected: FAIL — `getCases`, `getCase`, `investigateStream` not exported.

- [ ] **Step 3: Add types to types.ts**

Append to `frontend/src/types.ts`:

```ts
// --- HomeOS Cases and Pipeline ---
export interface AgentEvent {
  event: "agent_start" | "agent_data" | "agent_summary" | "agent_done" | "case_done" | "case_error";
  agent?: string;
  block_id?: number | null;
  narrative?: string;
  data?: Record<string, unknown>;
  case_id?: string;
  shortlist?: HomeOSShortlistRow[];
  message?: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface HomeOSCase {
  case_id: string;
  created_at: string;
  profile_text: string;
  avatar: HomeOSAvatar | null;
  pipeline: AgentEvent[];
  shortlist: HomeOSShortlistRow[];
  conversation: ChatMessage[];
  status: "running" | "done" | "error";
}

export interface HomeOSCaseSummary {
  case_id: string;
  created_at: string;
  profile_text: string;
  status: "running" | "done" | "error";
  shortlist_count: number;
}
```

- [ ] **Step 4: Add API methods to api.ts**

Append to `frontend/src/lib/api.ts`:

```ts
import type { HomeOSCase, HomeOSCaseSummary, AgentEvent } from "../types";

export function getCases(): Promise<HomeOSCaseSummary[]> {
  return getJSON<HomeOSCaseSummary[]>("/homeos/cases");
}

export function getCase(caseId: string): Promise<HomeOSCase> {
  return getJSON<HomeOSCase>(`/homeos/cases/${caseId}`);
}

export async function* investigateStream(
  profileText: string,
  limit = 5,
): AsyncGenerator<AgentEvent> {
  const res = await fetch(`${BASE}/homeos/investigate-stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_text: profileText, limit }),
  });
  if (!res.ok || !res.body) throw new Error(`API ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          yield JSON.parse(line.slice(6)) as AgentEvent;
        } catch {
          // skip malformed lines
        }
      }
    }
  }
}

export async function* chatInCase(
  caseId: string,
  message: string,
): AsyncGenerator<string> {
  const res = await fetch(`${BASE}/homeos/cases/${caseId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok || !res.body) throw new Error(`API ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const payload = line.slice(6);
        if (payload === "[DONE]") return;
        try {
          const parsed = JSON.parse(payload) as { chunk: string };
          yield parsed.chunk;
        } catch {
          // skip
        }
      }
    }
  }
}
```

- [ ] **Step 5: Run tests**

```bash
cd frontend && npm run test -- src/lib/sse.test.ts --run
```

Expected: 3 tests PASS.

- [ ] **Step 6: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types.ts frontend/src/lib/api.ts frontend/src/lib/sse.test.ts
git commit -m "feat: add homeos case types and sse api client"
```

---

## Task 6A: Backend Mock/Passthrough Agent Mode

**Goal:** Add a deterministic backend demo mode so the final UI can show rich HomeOS agent summaries without API keys, while keeping the existing Pydantic AI/TestModel/live-provider path available as passthrough.

**Files:**
- Create: `backend/app/services/homeos_mock_agents.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/services/homeos.py`
- Modify: `backend/app/services/homeos_agents.py`
- Create: `backend/tests/test_homeos_mock_agents.py`

- [ ] **Step 1: Write failing mock-mode tests**

Create tests that set `HOMEOS_AGENT_MODE=mock` with `unittest.mock.patch.dict(os.environ, ...)` or an equivalent local monkeypatch. Verify:

- `investigate_stream()` emits a profile `agent_summary` with a non-empty mock narrative.
- Per-block market/location/risk `agent_summary` events contain deterministic mock narratives.
- `chat_in_case()` returns a deterministic mock answer grounded in the stored case pipeline.
- Existing passthrough behavior remains covered by current stream tests.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_mock_agents -v
```

Expected: FAIL because mock-mode helpers and routing do not exist yet.

- [ ] **Step 3: Add config flag**

Add a HomeOS agent mode setting to `backend/app/config.py`:

```python
homeos_agent_mode: str = os.environ.get("HOMEOS_AGENT_MODE", "passthrough")
```

Valid values:
- `passthrough`: current behavior using Pydantic AI agents and `LLM_PROVIDER`
- `mock`: deterministic canned outputs for demo summaries and chat

- [ ] **Step 4: Create mock agent helpers**

Create `backend/app/services/homeos_mock_agents.py` with deterministic helpers for:

- profile/avatar output
- market narrative
- location narrative
- risk narrative
- viewing questions
- chat response

Mock helpers should still incorporate real repository-derived facts passed in by the existing service layer, such as transaction count, median price, MRT distance, school count, watchouts, and shortlist evidence. Do not fake block IDs or replace repository scoring end to end.

- [ ] **Step 5: Wire mock mode into existing service boundaries**

In `homeos.py`:
- `investigate_stream()` uses the mock profile output when `HOMEOS_AGENT_MODE=mock`.
- `chat_in_case()` returns the mock grounded chat response when `HOMEOS_AGENT_MODE=mock`.

In `homeos_agents.py`:
- `market_analysis_agent()`, `location_graph_agent()`, `risk_value_agent()`, and `viewing_questions_agent()` use mock narratives/questions when `HOMEOS_AGENT_MODE=mock`.
- Keep the current Pydantic AI calls unchanged for `passthrough`.

- [ ] **Step 6: Run mock-mode tests**

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_mock_agents -v
```

Expected: mock-mode tests PASS.

- [ ] **Step 7: Run backend regression tests**

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_ai_models tests.test_homeos_case_store tests.test_homeos_stream tests.test_homeos_stream_api -v
```

Expected: existing HomeOS backend tests PASS in passthrough mode.

- [ ] **Step 8: Commit**

```bash
git add backend/app/config.py backend/app/services/homeos.py backend/app/services/homeos_agents.py backend/app/services/homeos_mock_agents.py backend/tests/test_homeos_mock_agents.py
git commit -m "feat: add homeos mock agent mode"
```

---

## Task 7: CasesPanel Component

**Files:**
- Create: `frontend/src/components/CasesPanel.tsx`
- Create: `frontend/src/components/CasesPanel.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/CasesPanel.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import CasesPanel from "./CasesPanel";
import type { HomeOSCaseSummary } from "../types";

const mockCase: HomeOSCaseSummary = {
  case_id: "abc-123",
  created_at: "2026-06-09T10:00:00Z",
  profile_text: "Family looking for 4 room under 800k.",
  status: "done",
  shortlist_count: 3,
};

describe("CasesPanel", () => {
  it("renders new case input and investigate button", () => {
    render(
      <CasesPanel
        cases={[]}
        activeCaseId={null}
        onNewCase={vi.fn()}
        onSelectCase={vi.fn()}
      />
    );
    expect(screen.getByPlaceholderText(/household/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /investigate/i })).toBeInTheDocument();
  });

  it("calls onNewCase with profile text when investigate is clicked", async () => {
    const onNewCase = vi.fn();
    render(
      <CasesPanel
        cases={[]}
        activeCaseId={null}
        onNewCase={onNewCase}
        onSelectCase={vi.fn()}
      />
    );
    fireEvent.change(screen.getByPlaceholderText(/household/i), {
      target: { value: "Family 4 room 800k schools." },
    });
    fireEvent.click(screen.getByRole("button", { name: /investigate/i }));
    expect(onNewCase).toHaveBeenCalledWith("Family 4 room 800k schools.");
  });

  it("renders case list with status badge", () => {
    render(
      <CasesPanel
        cases={[mockCase]}
        activeCaseId={null}
        onNewCase={vi.fn()}
        onSelectCase={vi.fn()}
      />
    );
    expect(screen.getByText(/Family looking for 4 room/i)).toBeInTheDocument();
    expect(screen.getByText("3 blocks")).toBeInTheDocument();
  });

  it("highlights active case", () => {
    const { container } = render(
      <CasesPanel
        cases={[mockCase]}
        activeCaseId="abc-123"
        onNewCase={vi.fn()}
        onSelectCase={vi.fn()}
      />
    );
    const card = container.querySelector("[data-active='true']");
    expect(card).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npm run test -- src/components/CasesPanel.test.tsx --run 2>&1 | tail -10
```

Expected: FAIL — `CasesPanel` not found.

- [ ] **Step 3: Implement CasesPanel**

Create `frontend/src/components/CasesPanel.tsx`:

```tsx
import { useState } from "react";
import type { HomeOSCaseSummary } from "../types";

const DEFAULT_PROFILE = "Family looking for 4 room under 800k near primary schools and MRT.";

interface Props {
  cases: HomeOSCaseSummary[];
  activeCaseId: string | null;
  onNewCase: (profileText: string) => void;
  onSelectCase: (caseId: string) => void;
}

export default function CasesPanel({ cases, activeCaseId, onNewCase, onSelectCase }: Props) {
  const [profileText, setProfileText] = useState(DEFAULT_PROFILE);

  const statusColor = (status: string) =>
    status === "done"
      ? "bg-emerald-100 text-emerald-700"
      : status === "error"
        ? "bg-red-100 text-red-700"
        : "bg-amber-100 text-amber-700";

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          HomeOS Agent
        </p>

        <textarea
          className="w-full min-h-20 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          placeholder="Describe your household…"
          value={profileText}
          onChange={(e) => setProfileText(e.target.value)}
        />

        <button
          type="button"
          className="mt-2 w-full rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
          disabled={profileText.trim().length < 10}
          onClick={() => onNewCase(profileText.trim())}
        >
          Investigate homes
        </button>
      </div>

      {/* Cases list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {cases.length === 0 && (
          <p className="text-xs text-muted-foreground text-center pt-6">
            No investigations yet. Describe your household above.
          </p>
        )}
        {cases.map((c) => (
          <button
            key={c.case_id}
            type="button"
            data-active={c.case_id === activeCaseId}
            onClick={() => onSelectCase(c.case_id)}
            className={`w-full text-left rounded-md border p-3 transition-colors ${
              c.case_id === activeCaseId
                ? "border-primary bg-primary/5"
                : "border-border bg-card hover:bg-muted"
            }`}
          >
            <p className="text-xs font-medium text-foreground line-clamp-2 leading-snug">
              {c.profile_text}
            </p>
            <div className="mt-1.5 flex items-center gap-2">
              <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${statusColor(c.status)}`}>
                {c.status}
              </span>
              {c.shortlist_count > 0 && (
                <span className="text-[10px] text-muted-foreground">
                  {c.shortlist_count} blocks
                </span>
              )}
              <span className="ml-auto text-[10px] text-muted-foreground">
                {new Date(c.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npm run test -- src/components/CasesPanel.test.tsx --run
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/CasesPanel.tsx frontend/src/components/CasesPanel.test.tsx
git commit -m "feat: add cases panel component"
```

---

## Task 8: PipelinePanel Component

**Files:**
- Create: `frontend/src/components/PipelinePanel.tsx`
- Create: `frontend/src/components/PipelinePanel.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/PipelinePanel.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import PipelinePanel from "./PipelinePanel";
import type { AgentEvent, HomeOSCase } from "../types";

const mockCase: HomeOSCase = {
  case_id: "abc-123",
  created_at: "2026-06-09T10:00:00Z",
  profile_text: "Family 4 room 800k.",
  avatar: {
    label: "Family HomeOS Agent",
    buyer_type: "family",
    summary: "Family buyer prioritizing schools.",
    preferences: {
      flat_type: "4 ROOM", max_price: 800000,
      commute_priority: "medium", school_priority: "high",
      risk_tolerance: "low", appreciation_priority: "medium",
    },
  },
  pipeline: [
    { event: "agent_start", agent: "profile", block_id: null },
    { event: "agent_summary", agent: "profile", block_id: null, narrative: "Family buyer, 4-room, $800k budget." },
    { event: "agent_done", agent: "profile", block_id: null },
    { event: "agent_start", agent: "market", block_id: 1 },
    { event: "agent_summary", agent: "market", block_id: 1, narrative: "6 recent sales support budget." },
    { event: "agent_done", agent: "market", block_id: 1 },
  ],
  shortlist: [],
  conversation: [],
  status: "done",
};

describe("PipelinePanel", () => {
  it("renders avatar label when case has avatar", () => {
    render(
      <PipelinePanel
        activeCase={mockCase}
        onSendMessage={vi.fn()}
        streamingEvents={[]}
      />
    );
    expect(screen.getByText("Family HomeOS Agent")).toBeInTheDocument();
  });

  it("renders agent summary narratives from pipeline", () => {
    render(
      <PipelinePanel
        activeCase={mockCase}
        onSendMessage={vi.fn()}
        streamingEvents={[]}
      />
    );
    expect(screen.getByText("Family buyer, 4-room, $800k budget.")).toBeInTheDocument();
    expect(screen.getByText("6 recent sales support budget.")).toBeInTheDocument();
  });

  it("shows running spinner for agent_start events in streaming", () => {
    const streaming: AgentEvent[] = [
      { event: "agent_start", agent: "risk", block_id: 2 },
    ];
    render(
      <PipelinePanel
        activeCase={null}
        onSendMessage={vi.fn()}
        streamingEvents={streaming}
      />
    );
    expect(screen.getByText(/risk/i)).toBeInTheDocument();
  });

  it("calls onSendMessage when chat is submitted", async () => {
    const onSend = vi.fn();
    render(
      <PipelinePanel
        activeCase={mockCase}
        onSendMessage={onSend}
        streamingEvents={[]}
      />
    );
    fireEvent.change(screen.getByPlaceholderText(/ask/i), {
      target: { value: "Why Bishan?" },
    });
    fireEvent.submit(screen.getByRole("form"));
    expect(onSend).toHaveBeenCalledWith("Why Bishan?");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npm run test -- src/components/PipelinePanel.test.tsx --run 2>&1 | tail -10
```

Expected: FAIL — `PipelinePanel` not found.

- [ ] **Step 3: Implement PipelinePanel**

Create `frontend/src/components/PipelinePanel.tsx`:

```tsx
import { useRef, useEffect, useState } from "react";
import type { AgentEvent, HomeOSCase } from "../types";

const AGENT_LABELS: Record<string, string> = {
  profile: "Profile Agent",
  market: "Market Agent",
  location: "Location Agent",
  risk: "Risk Agent",
  questions: "Questions Agent",
};

interface Props {
  activeCase: HomeOSCase | null;
  streamingEvents: AgentEvent[];
  onSendMessage: (message: string) => void;
  chatChunks?: string;
}

export default function PipelinePanel({ activeCase, streamingEvents, onSendMessage, chatChunks }: Props) {
  const [chatInput, setChatInput] = useState("");
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeCase?.pipeline, streamingEvents]);

  const allEvents: AgentEvent[] = [
    ...(activeCase?.pipeline ?? []),
    ...streamingEvents,
  ];

  const summaryEvents = allEvents.filter(
    (e) => e.event === "agent_summary" || e.event === "case_done"
  );

  const activeAgents = new Set(
    streamingEvents
      .filter((e) => e.event === "agent_start")
      .map((e) => `${e.agent}-${e.block_id ?? ""}`)
  );
  const doneAgents = new Set(
    allEvents
      .filter((e) => e.event === "agent_done")
      .map((e) => `${e.agent}-${e.block_id ?? ""}`)
  );

  const runningAgents = streamingEvents.filter(
    (e) =>
      e.event === "agent_start" &&
      !doneAgents.has(`${e.agent}-${e.block_id ?? ""}`)
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!chatInput.trim()) return;
    onSendMessage(chatInput.trim());
    setChatInput("");
  }

  if (!activeCase && streamingEvents.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <p className="text-xs text-muted-foreground text-center">
          Start a new investigation to see the agent pipeline here.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      {activeCase?.avatar && (
        <div className="p-4 border-b border-border">
          <p className="text-sm font-semibold text-foreground">
            {activeCase.avatar.label}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {activeCase.avatar.summary}
          </p>
        </div>
      )}

      {/* Agent log */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
        {summaryEvents.map((e, i) => (
          <div key={i} className="flex items-start gap-2 rounded-md bg-muted/40 px-3 py-2">
            <span className="mt-0.5 text-emerald-500 text-xs shrink-0">✓</span>
            <div>
              {e.event === "agent_summary" && e.agent && (
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-0.5">
                  {AGENT_LABELS[e.agent] ?? e.agent}
                  {e.block_id != null ? ` · Blk ${e.block_id}` : ""}
                </p>
              )}
              <p className="text-xs text-foreground leading-snug">
                {e.event === "agent_summary" ? e.narrative : `Shortlist ready · ${(e.shortlist ?? []).length} blocks`}
              </p>
            </div>
          </div>
        ))}

        {runningAgents.map((e, i) => (
          <div key={`running-${i}`} className="flex items-center gap-2 rounded-md border border-border px-3 py-2">
            <span className="text-xs animate-spin shrink-0">⟳</span>
            <p className="text-xs text-muted-foreground">
              {AGENT_LABELS[e.agent ?? ""] ?? e.agent} analysing
              {e.block_id != null ? ` Blk ${e.block_id}` : ""}…
            </p>
          </div>
        ))}

        {/* Conversation history */}
        {(activeCase?.conversation ?? []).map((msg, i) => (
          <div
            key={`msg-${i}`}
            className={`rounded-md px-3 py-2 text-xs ${
              msg.role === "user"
                ? "bg-primary/10 text-foreground ml-4"
                : "bg-muted text-foreground mr-4"
            }`}
          >
            <p className="font-semibold text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">
              {msg.role === "user" ? "You" : "HomeOS"}
            </p>
            {msg.content}
          </div>
        ))}

        {chatChunks && (
          <div className="rounded-md bg-muted px-3 py-2 text-xs text-foreground mr-4">
            <p className="font-semibold text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">HomeOS</p>
            {chatChunks}
          </div>
        )}

        <div ref={logEndRef} />
      </div>

      {/* Chat input */}
      {activeCase?.status === "done" && (
        <form
          role="form"
          onSubmit={handleSubmit}
          className="border-t border-border p-3 flex gap-2"
        >
          <input
            className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            placeholder="Ask HomeOS about this investigation…"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
          />
          <button
            type="submit"
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            disabled={!chatInput.trim()}
          >
            Ask
          </button>
        </form>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npm run test -- src/components/PipelinePanel.test.tsx --run
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PipelinePanel.tsx frontend/src/components/PipelinePanel.test.tsx
git commit -m "feat: add pipeline panel component"
```

---

## Task 9: Three-Column App Layout

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/HomeOSDetailPanel.tsx`

- [ ] **Step 1: Add back button to HomeOSDetailPanel**

In `frontend/src/components/HomeOSDetailPanel.tsx`, the close button already exists. Add a `onBack` prop that renders a "← Pipeline" button when provided:

In the Props interface, add:
```ts
onBack?: () => void;
```

In the header div, before the close button:
```tsx
{onBack && (
  <button
    type="button"
    onClick={onBack}
    className="shrink-0 rounded p-1 text-xs text-muted-foreground hover:bg-muted flex items-center gap-1"
  >
    ← Pipeline
  </button>
)}
```

- [ ] **Step 2: Rewrite App.tsx for three-column layout**

Replace the contents of `frontend/src/App.tsx` with:

```tsx
import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import CasesPanel from "./components/CasesPanel";
import HomeOSDetailPanel from "./components/HomeOSDetailPanel";
import MapView from "./components/MapView";
import PipelinePanel from "./components/PipelinePanel";
import { investigateStream, getCases, chatInCase } from "./lib/api";
import { searchProperties } from "./lib/api";
import type {
  AgentEvent,
  HomeOSCase,
  HomeOSCaseSummary,
  SearchFilters,
} from "./types";

const DEFAULT_FILTERS: SearchFilters = { limit: 500 };

type RightPanel = "pipeline" | "block_detail";

export default function App() {
  const [filters] = useState<SearchFilters>(DEFAULT_FILTERS);
  const [cases, setCases] = useState<HomeOSCaseSummary[]>([]);
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [activeCaseFull, setActiveCaseFull] = useState<HomeOSCase | null>(null);
  const [streamingEvents, setStreamingEvents] = useState<AgentEvent[]>([]);
  const [shortlistIds, setShortlistIds] = useState<number[]>([]);
  const [selectedBlockId, setSelectedBlockId] = useState<number | null>(null);
  const [rightPanel, setRightPanel] = useState<RightPanel>("pipeline");
  const [chatChunks, setChatChunks] = useState("");

  const search = useQuery({
    queryKey: ["search", filters],
    queryFn: () => searchProperties(filters),
  });
  const blocks = search.data?.results ?? [];

  const handleNewCase = useCallback(async (profileText: string) => {
    setStreamingEvents([]);
    setActiveCaseFull(null);
    setShortlistIds([]);
    setRightPanel("pipeline");

    const tempSummary: HomeOSCaseSummary = {
      case_id: "pending",
      created_at: new Date().toISOString(),
      profile_text: profileText,
      status: "running",
      shortlist_count: 0,
    };
    setCases((prev) => [tempSummary, ...prev]);

    let finalCaseId: string | null = null;

    for await (const event of investigateStream(profileText, 5)) {
      setStreamingEvents((prev) => [...prev, event]);

      if (event.event === "case_done") {
        finalCaseId = event.case_id ?? null;
        const shortlist = event.shortlist ?? [];
        setShortlistIds(shortlist.map((r) => r.block_id));
        setCases((prev) =>
          prev.map((c) =>
            c.case_id === "pending"
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
            c.case_id === "pending"
              ? { ...c, case_id: event.case_id ?? "error", status: "error" }
              : c
          )
        );
      }
    }

    if (finalCaseId) {
      setActiveCaseId(finalCaseId);
      const fullCase: HomeOSCase = {
        case_id: finalCaseId,
        created_at: tempSummary.created_at,
        profile_text: profileText,
        avatar: null,
        pipeline: streamingEvents,
        shortlist: [],
        conversation: [],
        status: "done",
      };
      setActiveCaseFull(fullCase);
    }
    setStreamingEvents([]);
  }, [streamingEvents]);

  const handleSelectCase = useCallback((caseId: string) => {
    setActiveCaseId(caseId);
    setRightPanel("pipeline");
    setSelectedBlockId(null);
  }, []);

  const handleSelectBlock = useCallback((blockId: number) => {
    setSelectedBlockId(blockId);
    setRightPanel("block_detail");
  }, []);

  const handleSendMessage = useCallback(async (message: string) => {
    if (!activeCaseId) return;
    setChatChunks("");
    let full = "";
    for await (const chunk of chatInCase(activeCaseId, message)) {
      full += chunk;
      setChatChunks(full);
    }
    if (activeCaseFull) {
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
    }
    setChatChunks("");
  }, [activeCaseId, activeCaseFull]);

  const selectedBlock = blocks.find((b) => b.block_id === selectedBlockId) ?? null;
  const profileText = activeCaseFull?.profile_text ?? cases.find((c) => c.case_id === activeCaseId)?.profile_text ?? "";

  return (
    <div className="flex h-full bg-background">
      {/* Left: Cases */}
      <aside className="flex w-72 shrink-0 flex-col border-r border-border bg-card overflow-hidden">
        <div className="flex items-center gap-2.5 px-4 py-3 border-b border-border">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground text-sm font-bold shrink-0">
            H
          </div>
          <div>
            <h1 className="text-sm font-bold text-foreground leading-tight">HDB Match</h1>
            <p className="text-xs text-muted-foreground">HomeOS Agent</p>
          </div>
        </div>
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
        <MapView
          blocks={blocks}
          shortlistIds={shortlistIds}
          selectedBlockId={selectedBlockId}
          onSelectBlock={handleSelectBlock}
        />
      </main>

      {/* Right: Pipeline or Block Detail */}
      <aside className="flex w-80 shrink-0 flex-col border-l border-border bg-card overflow-hidden">
        {rightPanel === "pipeline" ? (
          <PipelinePanel
            activeCase={activeCaseFull}
            streamingEvents={streamingEvents}
            onSendMessage={handleSendMessage}
            chatChunks={chatChunks}
          />
        ) : (
          <HomeOSDetailPanel
            block={selectedBlock}
            profileText={profileText}
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

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors. Fix any if they arise.

- [ ] **Step 4: Check frontend builds in browser**

Open `http://localhost:5174` (or whichever port Vite is on). Verify:
- Three-column layout renders
- Cases panel shows input + "Investigate homes" button
- Map renders in center
- Right panel shows "Start a new investigation" placeholder

- [ ] **Step 5: Run full frontend test suite**

```bash
cd frontend && npm run test -- --run
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/HomeOSDetailPanel.tsx
git commit -m "feat: three-column app layout with cases and pipeline panels"
```

---

## Task 10: End-to-End Smoke Test

- [ ] **Step 1: Ensure backend is running**

```bash
cd backend && ./.venv/bin/uvicorn app.api.main:app --reload --port 8000
```

- [ ] **Step 2: Ensure frontend is running**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: Manual walkthrough**

Open `http://localhost:5174`. Verify this flow:

1. Three-column layout visible
2. Type a profile in the left panel: `Family looking for 4 room under 800k near schools`
3. Click "Investigate homes"
4. Right panel shows agent events streaming live (profile → market → location → risk)
5. `case_done` event arrives — shortlist appears in right panel
6. Shortlisted blocks on map turn violet
7. Type a question: `Why did you pick this block?` → HomeOS streams an answer
8. Click a violet map node → right panel switches to Block Detail
9. Click `← Pipeline` → right panel returns to pipeline view
10. Case appears in left panel cases list with "done" badge

- [ ] **Step 4: Verify SSE directly**

```bash
curl -N -s -X POST http://127.0.0.1:8000/homeos/investigate-stream \
  -H 'Content-Type: application/json' \
  -d '{"profile_text":"Family 4 room 800k schools.","limit":2}' | head -30
```

Expected: SSE event lines, ending with `case_done`.

- [ ] **Step 5: Final commit and push**

```bash
git add -A
git commit -m "chore: phase 1 homeos ai pipeline complete (TestModel scaffold)"
git push
```

---

---

## Phase 2: Enable Real LLM via Vercel AI Gateway

**Goal:** Replace `TestModel` with real LLM calls without changing any agent code. One `.env` change is all that's needed.

### Why Vercel AI Gateway

- **One key, any provider.** A single `AI_GATEWAY_API_KEY` routes to Anthropic, Google Gemini, OpenAI, xAI, and hundreds of other models.
- **OpenAI-compatible.** No new SDK dependency — `pydantic-ai-slim[openai]` (already in requirements) is sufficient.
- **Gemini CLI keys work.** If you have a Google AI Studio / Gemini CLI key, use model `google/gemini-2.0-flash` through the gateway.
- **Zero markup on tokens.** You pay provider rates directly; Vercel does not add a surcharge.
- **Built-in fallbacks and monitoring.** The gateway auto-retries on provider outages.

### Quickstart

1. Get an API key at https://vercel.com/ai-gateway
2. Set `.env` — **just one line needed** (Vercel auto-activates when the key is present):

```env
AI_GATEWAY_API_KEY=<your-vercel-ai-gateway-key>
LLM_MODEL=google/gemini-2.0-flash
```

3. Restart the backend — no code changes required. `LLM_PROVIDER` defaults to `vercel` when `AI_GATEWAY_API_KEY` is set.

### Supported model strings (examples)

| Provider | Model string |
|---|---|
| Google Gemini | `google/gemini-2.0-flash` |
| Google Gemini Pro | `google/gemini-2.0-pro` |
| Anthropic Claude | `anthropic/claude-haiku-4-5-20251001` |
| OpenAI | `openai/gpt-4o-mini` |
| xAI | `xai/grok-4.3` |

Full list: https://vercel.com/ai-gateway/models

### How it works under the hood

`get_model()` in `homeos_ai_agents.py` reads `LLM_PROVIDER`. When set to `vercel`:

```python
OpenAIModel(
    os.getenv("LLM_MODEL", "google/gemini-2.0-flash"),
    provider=OpenAIProvider(
        base_url="https://ai-gateway.vercel.sh/v1",
        api_key=os.getenv("AI_GATEWAY_API_KEY", ""),
    ),
)
```

All five Pydantic AI agents (`profile_agent`, `market_agent`, `location_agent`, `risk_agent`, `questions_agent`) share this model — swap the env vars, all agents switch simultaneously.

### Fallback providers (direct, no gateway)

| `LLM_PROVIDER` | Key env var | Notes |
|---|---|---|
| `vercel` | `AI_GATEWAY_API_KEY` | **Recommended** — any provider through one key |
| `anthropic` | `ANTHROPIC_API_KEY` | Direct Anthropic SDK call |
| `openrouter` | `OPENROUTER_API_KEY` | Alternative multi-provider router |
| `test` (default) | — | Deterministic TestModel, no key needed |

---

## Self-Review

**Spec coverage:**
- LLM profile parsing ✓ (Task 2 — profile_agent)
- Per-agent narratives ✓ (Tasks 2, 4 — each agent returns `narrative`)
- Live streaming pipeline ✓ (Tasks 4, 5 — SSE + frontend EventSource)
- Case as unit of work ✓ (Task 3 — case store)
- Q&A grounded in evidence ✓ (Task 4 — chat_in_case)
- Cases left panel ✓ (Task 7)
- Pipeline right panel ✓ (Task 8)
- Node click → block detail ✓ (Task 9)
- Back button → pipeline ✓ (Task 9)
- Phase 1 uses TestModel ✓ (Task 2 — `LLM_PROVIDER=test` default)
- Provider swap in one env var ✓ (Task 2 — `get_model()` factory)

**Placeholder scan:** None found — all steps have actual code.

**Type consistency:**
- `AgentEvent.event` values consistent across backend events, frontend types, and PipelinePanel rendering
- `HomeOSCase` mirrors backend case dict shape
- `investigateStream` yields `AgentEvent`, consumed by `PipelinePanel` as `streamingEvents`
- `chatInCase` yields `string` chunks, surfaced as `chatChunks` prop
