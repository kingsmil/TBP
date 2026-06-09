# HomeOS Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build HomeOS Agent, an AI home-buying agent that turns a natural-language household profile into evidence-backed HDB viewing recommendations and a scheduling-agent handoff.

**Architecture:** Add a backend HomeOS service that parses a household profile, investigates existing HDB blocks using current transaction/proximity/scoring services, ranks which homes are worth viewing, generates agent questions, and creates a scheduling handoff. Expose FastAPI endpoints for investigation, case-file inspection, and viewing scheduling; add a frontend panel that demonstrates the full loop from vague buyer goals to a viewing request.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, existing repository/service layer, React, TypeScript, TanStack Query, Vitest, pytest/unittest.

---

## Product Design

### Product Name

**HomeOS Agent**

### One-Line Pitch

> An AI home-buying agent that turns a family’s housing goals into evidence-backed HDB viewings.

### Demo Narrative

HomeOS Agent is not a generic real-estate chatbot. It is an action-oriented buyer agent:

1. User opens **AI Mode** in the left panel and describes their household in natural language.
2. HomeOS creates a buyer avatar/profile.
3. HomeOS investigates HDB blocks using real evidence.
4. HomeOS recommends which homes are worth viewing and why.
5. User hovers map nodes to preview summaries.
6. User clicks a node or `More` to open a right-side house detail panel.
7. User selects a home for viewing from the detail panel.
8. Scheduling agent collects availability and prepares the agent message.

This keeps scheduling as a first-class demo moment, while the due-diligence layer keeps the product credible.

### MVP Boundary

The MVP simulates the scheduling agent with a visible handoff/outbox message. It does not send WhatsApp, email, Telegram, or SMS. That makes the demo complete without external integration risk.

Natural-language parsing is deterministic in this version. It extracts practical buyer constraints:

- buyer type: family, couple, single, investor
- flat type
- max budget
- commute priority
- school priority
- risk tolerance
- appreciation priority

### What Makes This Hackathon-Worthy

The demo should show a complete agent loop:

```text
profile -> investigate -> shortlist -> case file -> select for viewing -> scheduling handoff
```

That is stronger than a RAG bot because the system does not only explain. It helps the buyer decide and then acts.

---

## UI Product Requirements

### AI Mode In Left Panel

The current left panel is a filter-first dashboard. HomeOS requires a distinct **AI Mode** at the top of the same panel so the agentic workflow is visible immediately.

**Requirement:** Add a left-panel mode switch:

```text
[AI Mode] [Explore]
```

**AI Mode contains:**

- natural-language household prompt
- example prompt text
- `Investigate homes` action
- HomeOS buyer-avatar summary
- viewing shortlist cards
- compact case-file preview for the selected recommendation
- `Schedule viewing` entry point

**Explore contains existing UI:**

- flat type filter
- max PSF
- max walk to MRT
- min schools within 1km
- stats cards
- PSF trend
- estate comparison

**Default behavior:** The app should open in AI Mode for the hackathon/demo flow. Explore remains available for manual analysis.

**Rationale:** If HomeOS is inserted as a small widget above filters, it will read as an add-on. AI Mode makes the agent the primary surface while preserving the existing analytics product.

### Map Node Hover And Click Behavior

The map should become part of the agent workflow, not just a passive result display.

**Hover behavior:**

- Hovering over a house/block node displays a lightweight summary.
- The summary should be short enough to scan without covering too much of the map.
- Summary content:
  - block address
  - town
  - median PSF
  - median price
  - MRT distance
  - schools within 1km
  - HomeOS verdict if available

**Click behavior:**

- Clicking a node opens a right-side detail panel.
- Clicking `More` in the hover/summary popup opens the same right-side detail panel.
- The right panel should not replace the map. It overlays or docks to the right so the user keeps spatial context.

**Right-side detail panel contains:**

- block address and town
- key stats
- recent sales evidence
- MRT/school connection evidence
- risk/watchout section
- questions to ask the real-estate agent
- `Select for viewing`
- availability form after selection
- scheduling outbox after submission

**Map marker states:**

- normal search result: existing marker style
- HomeOS shortlist result: highlighted marker
- selected detail-panel block: larger marker or outlined marker
- hover state: temporary emphasis

**Rationale:** This creates a clear interaction model:

```text
AI Mode finds homes -> map highlights homes -> hover previews -> click opens detail -> schedule viewing
```

### Right Panel Layout

The right panel should be a compact inspector, not another full dashboard.

```text
RIGHT PANEL
┌─────────────────────────────┐
│ Blk 129 Jurong West St 4     │
│ Worth viewing · High conf.   │
├─────────────────────────────┤
│ Key Numbers                  │
│ Median price / PSF / MRT     │
├─────────────────────────────┤
│ Why HomeOS picked this       │
│ Recent sales / schools / MRT │
├─────────────────────────────┤
│ Watchouts                    │
├─────────────────────────────┤
│ Questions for agent          │
├─────────────────────────────┤
│ [Select for viewing]         │
└─────────────────────────────┘
```

On smaller screens, the right panel can become a bottom sheet.

---

## File Structure

Backend:

- Create `backend/app/services/homeos.py`
  - Parses household profile text.
  - Creates HomeOS buyer avatar preferences.
  - Orchestrates the HomeOS sub-agents.
  - Creates scheduling-agent handoff payload.
- Create `backend/app/services/homeos_agents.py`
  - Implements the Market Analysis Agent, Location Graph Agent, Risk/Value Agent, Viewing Questions Agent, and Scheduling Agent as deterministic service units.
  - Each agent accepts a `Repository` plus typed context and returns a serializable evidence payload.
- Create `backend/tests/test_homeos_service.py`
  - Tests parser, case-file evidence, shortlist ranking, generated questions, and scheduling handoff.
- Create `backend/tests/test_homeos_agents.py`
  - Tests each sub-agent independently, including how it reads repository data and how it handles sparse evidence.
- Modify `backend/app/api/schemas.py`
  - Adds Pydantic request models for HomeOS investigation, case-file lookup, and viewing scheduling.
- Modify `backend/app/api/main.py`
  - Adds `POST /homeos/investigate`, `POST /homeos/case-file/{block_id}`, and `POST /homeos/schedule-viewing`.

Frontend:

- Modify `frontend/src/types.ts`
  - Adds HomeOS avatar, shortlist, evidence, case-file, and scheduling response types.
- Modify `frontend/src/lib/api.ts`
  - Adds typed API methods for the HomeOS endpoints.
- Create `frontend/src/components/HomeOSAgentPanel.tsx`
  - Owns AI Mode in the left panel: natural-language profile input, shortlist cards, selected block preview, and scheduling entry point.
- Create `frontend/src/components/HomeOSDetailPanel.tsx`
  - Owns the right-side detail inspector: selected block evidence, questions, availability form, and scheduling outbox.
- Create `frontend/src/components/HomeOSAgentPanel.test.tsx`
  - Component tests for investigation and scheduling flow.
- Create `frontend/src/components/HomeOSDetailPanel.test.tsx`
  - Component tests for selected block detail, `More`/click behavior, and scheduling outbox display.
- Modify `frontend/src/components/MapView.tsx`
  - Adds hover summary support, `More` action, selected marker state, and HomeOS shortlist marker state.
- Modify `frontend/src/App.tsx`
  - Owns active mode, selected block, right-panel open state, HomeOS shortlist state, and passes map interaction callbacks.

Documentation:

- Modify `README.md`
  - Adds the three HomeOS endpoints to the API reference.

---

## Agent Implementation Architecture

HomeOS should be implemented as an orchestrated set of small deterministic agents, not one large prompt-like function. Each agent is a normal Python class or function in `backend/app/services/homeos_agents.py`. The orchestrator in `backend/app/services/homeos.py` calls them and combines their evidence into a case file.

### Agent Data Access Rule

Use the existing `Repository` interface first. That keeps mock mode, tests, and PostGIS mode aligned.

```text
Preferred path:
HomeOS agent -> Repository interface -> memory repo or PostGIS repo
```

Only add direct SQL when the query cannot be expressed through the current repository without pulling too much data into Python. Direct SQL should live behind a small helper with a repository fallback so mock mode still works.

```text
Optimized production path:
HomeOS agent -> optional PostGIS/SQL helper -> materialized views / indexed tables

Test/mock path:
HomeOS agent -> Repository fallback -> in-memory generated data
```

The frontend should call the HomeOS API endpoints, not individual internal agents.

```text
React -> /api/homeos/investigate
React -> /api/homeos/case-file/{block_id}
React -> /api/homeos/schedule-viewing
```

### Market Analysis Agent

**Purpose:** Decide whether the block has enough resale evidence and whether recent comparable sales support the buyer's budget.

**Primary inputs:**

- `repo.transactions_for_block(block_id)`
- `repo.block(block_id)`
- parsed profile preferences: `flat_type`, `max_price`

**Mock/repository implementation:**

```python
def market_analysis_agent(repo: Repository, block_id: int, prefs: dict) -> dict:
    txns = list(repo.transactions_for_block(block_id))
    if prefs["flat_type"]:
        txns = [txn for txn in txns if txn.flat_type == prefs["flat_type"]]
    recent = sorted(txns, key=lambda txn: txn.transaction_month, reverse=True)[:6]
    summary = summarize(recent)
    return {
        "transaction_count": summary.txn_count,
        "median_price": summary.median_price,
        "median_psf": summary.median_psf,
        "budget_signal": "within_budget" | "above_budget" | "unknown",
        "confidence": "high" | "medium" | "low",
        "summary": "...",
    }
```

**PostGIS optimization path:**

If real transaction volume is large, add an optional helper such as `recent_comparable_sales_sql(engine, block_id, flat_type, months=6)` that queries:

```sql
SELECT
  count(*) AS transaction_count,
  percentile_cont(0.5) WITHIN GROUP (ORDER BY resale_price) AS median_price,
  percentile_cont(0.5) WITHIN GROUP (ORDER BY psf) AS median_psf
FROM hdb_transactions
WHERE block_id = :block_id
  AND (:flat_type IS NULL OR flat_type = :flat_type)
  AND transaction_month >= current_date - interval '6 months';
```

This SQL path is a later optimization. The MVP should use the repository path so tests and mock mode work.

### Location Graph Agent

**Purpose:** Show graph-like connections from the selected HDB block to nearby MRT and primary-school evidence.

**Primary inputs:**

- `repo.proximity(block_id)`
- `repo.mrt_stations("operational")`
- `repo.schools()`
- `repo.block(block_id)`

**Mock/repository implementation:**

```python
def location_graph_agent(repo: Repository, block_id: int) -> dict:
    prox = repo.proximity(block_id)
    return {
        "connections": [
            {
                "type": "mrt",
                "name": "Nearest operational MRT",
                "distance_m": prox.nearest_mrt_distance_m,
                "signal": "strong" | "moderate" | "weak",
            },
            {
                "type": "primary_school",
                "name": "Primary schools within 1km",
                "count": prox.schools_within_1km,
                "signal": "strong" | "moderate" | "weak",
            },
        ]
    }
```

**PostGIS optimization path:**

For a richer graph, direct SQL can join `hdb_blocks`, `mrt_stations`, and `schools` using `ST_DWithin` and `geom_svy21`. That should be exposed through a helper, not called from the frontend directly.

```sql
SELECT station_name, ST_Distance(b.geom_svy21, m.geom_svy21) AS distance_m
FROM hdb_blocks b
JOIN mrt_stations m ON m.status = 'operational'
WHERE b.block_id = :block_id
ORDER BY b.geom_svy21 <-> m.geom_svy21
LIMIT 3;
```

### Risk And Value Agent

**Purpose:** Combine lease, appreciation, future MRT, future supply, and accessibility signals into watchouts and score modifiers.

**Primary inputs:**

- `app.services.appreciation.appreciation(repo, block_id)`
- `app.services.future_dev.future_mrt(repo, block_id)`
- `app.services.future_dev.future_supply(repo, block_id)`
- `app.services.accessibility.block_accessibility(repo, block_id)`

**Implementation path:**

This agent should call existing service functions, not duplicate their calculations.

```python
def risk_value_agent(repo: Repository, block_id: int, prefs: dict) -> dict:
    app = appreciation(repo, block_id)
    mrt = future_mrt(repo, block_id)
    supply = future_supply(repo, block_id)
    access = block_accessibility(repo, block_id)
    return {
        "appreciation": app,
        "future_mrt": mrt,
        "future_supply": supply,
        "accessibility": access,
        "watchouts": [...],
        "score_adjustment": 0.0,
    }
```

### Viewing Questions Agent

**Purpose:** Turn evidence and watchouts into concrete questions the buyer should ask the real-estate agent before viewing.

**Primary inputs:**

- Market Analysis Agent output
- Location Graph Agent output
- Risk And Value Agent output
- selected block metadata

**Implementation path:**

Use deterministic rule templates. Do not call an LLM in the MVP.

```python
def viewing_questions_agent(evidence: dict) -> list[str]:
    questions = [
        "Which floor range is the unit in?",
        "Is the unit facing a main road or MRT track?",
        "Are recent comparable transactions renovated or original condition?",
        "Are there ethnic quota or extension restrictions?",
    ]
    if evidence["market"]["confidence"] == "low":
        questions.append("Why is there limited recent resale evidence for this block or flat type?")
    if any(c.get("signal") == "weak" for c in evidence["location"]["connections"]):
        questions.append("What is the realistic walking route and time to the nearest MRT or school?")
    return questions
```

### Scheduling Agent

**Purpose:** Convert a selected case file and user availability into a visible outbox message that looks like an agent action.

**Primary inputs:**

- selected block
- parsed avatar summary
- case-file questions
- user availability
- user contact name and note

**Implementation path:**

The MVP should produce an outbox object. It should not send external messages.

```python
def scheduling_agent(repo: Repository, profile_text: str, block_id: int, availability: list[str], contact_name: str, contact_note: str | None) -> dict:
    case_file = build_homeos_case_file(repo, profile_text, block_id)
    message = "Hi, {contact_name} would like to view ..."
    return {
        "status": "ready_for_agent",
        "confirmation": "...",
        "outbox": {
            "recipient_type": "real_estate_agent",
            "message": message,
            "availability": availability,
        },
    }
```

**Future integration path:**

The outbox object is the boundary for a real integration. Later adapters can consume the same payload:

- `EmailSchedulingAdapter`
- `WhatsAppSchedulingAdapter`
- `TelegramSchedulingAdapter`
- `CRMLeadAdapter`

Do not add these adapters in the MVP.

### Agent Orchestration

`backend/app/services/homeos.py` owns orchestration:

```python
def build_homeos_case_file(repo: Repository, profile_text: str, block_id: int) -> dict:
    avatar = parse_homeos_profile(profile_text)
    market = market_analysis_agent(repo, block_id, avatar["preferences"])
    location = location_graph_agent(repo, block_id)
    risk = risk_value_agent(repo, block_id, avatar["preferences"])
    questions = viewing_questions_agent({
        "market": market,
        "location": location,
        "risk": risk,
    })
    score = worth_viewing_score(market, location, risk, avatar["preferences"])
    return {
        "avatar": avatar,
        "block_id": block_id,
        "worth_viewing_score": score,
        "evidence": {
            "market": market,
            "location": location,
            "risk": risk,
            "agent_questions": questions,
        },
    }
```

This gives the hackathon demo a true multi-agent story while keeping implementation deterministic, testable, and grounded in current project data.

---

## Backend Contracts

### `POST /homeos/investigate`

Request:

```json
{
  "profile_text": "We are a young family, budget 750k, need 4-room, care about primary schools, one parent works in Raffles Place, low risk tolerance.",
  "limit": 5
}
```

Response:

```json
{
  "avatar": {
    "label": "Family HomeOS Agent",
    "buyer_type": "family",
    "summary": "Family buyer prioritizing schools, budget fit, and lower-risk viewing choices.",
    "preferences": {
      "flat_type": "4 ROOM",
      "max_price": 750000.0,
      "commute_priority": "medium",
      "school_priority": "high",
      "risk_tolerance": "low",
      "appreciation_priority": "medium"
    }
  },
  "shortlist": [
    {
      "block_id": 12,
      "block_number": "112",
      "street_name": "TAMPINES ST 1",
      "town": "TAMPINES",
      "worth_viewing_score": 86.5,
      "verdict": "Worth viewing",
      "confidence": "high",
      "top_reasons": [
        "Recent comparable sales support the budget.",
        "Primary school access fits the family profile.",
        "Accessibility risk is acceptable."
      ],
      "top_watchouts": [
        "MRT access is moderate rather than excellent."
      ]
    }
  ]
}
```

### `POST /homeos/case-file/{block_id}`

Request:

```json
{
  "profile_text": "We are a young family, budget 750k, need 4-room, care about primary schools, low risk tolerance."
}
```

Response:

```json
{
  "block_id": 12,
  "block_number": "112",
  "street_name": "TAMPINES ST 1",
  "town": "TAMPINES",
  "verdict": "Worth viewing",
  "worth_viewing_score": 86.5,
  "confidence": "high",
  "top_reasons": [
    "Recent comparable sales support the budget.",
    "Primary school access fits the family profile."
  ],
  "top_watchouts": [
    "MRT access is moderate rather than excellent."
  ],
  "evidence": {
    "recent_sales": {
      "transaction_count": 8,
      "median_price": 715000.0,
      "median_psf": 650.0,
      "window_months": 6,
      "summary": "8 similar 4 ROOM transactions support price confidence."
    },
    "connections": [
      {
        "type": "mrt",
        "name": "Nearest operational MRT",
        "distance_m": 620.0,
        "signal": "moderate"
      },
      {
        "type": "primary_school",
        "name": "Primary schools within 1km",
        "count": 2,
        "signal": "strong"
      }
    ],
    "risks": [
      "MRT access is moderate rather than excellent."
    ],
    "future_signals": {
      "future_mrt": {},
      "future_supply": {}
    },
    "agent_questions": [
      "Which floor range is the unit in?",
      "Is the unit facing a main road or MRT track?",
      "Are recent comparable transactions renovated or original condition?",
      "Are there ethnic quota or extension restrictions?"
    ]
  }
}
```

### `POST /homeos/schedule-viewing`

Request:

```json
{
  "profile_text": "We are a young family, budget 750k, need 4-room, care about primary schools.",
  "block_id": 12,
  "availability": [
    "2026-06-13 10:00-12:00",
    "2026-06-14 15:00-17:00"
  ],
  "contact_name": "Moe",
  "contact_note": "Prefer WhatsApp follow-up."
}
```

Response:

```json
{
  "status": "ready_for_agent",
  "confirmation": "Blk 112 TAMPINES ST 1 is selected for viewing. HomeOS prepared the scheduling handoff with 2 availability windows.",
  "outbox": {
    "block_id": 12,
    "recipient_type": "real_estate_agent",
    "message": "Hi, Moe would like to view Blk 112 TAMPINES ST 1. Availability: 2026-06-13 10:00-12:00; 2026-06-14 15:00-17:00. Buyer profile: Family buyer prioritizing schools, budget fit, and lower-risk viewing choices. Due-diligence questions: Which floor range is the unit in? Is the unit facing a main road or MRT track? Note: Prefer WhatsApp follow-up.",
    "availability": [
      "2026-06-13 10:00-12:00",
      "2026-06-14 15:00-17:00"
    ]
  }
}
```

---

## Implementation Tasks

### Task 1: Backend HomeOS Profile Parser

**Files:**
- Create: `backend/app/services/homeos.py`
- Test: `backend/tests/test_homeos_service.py`

- [ ] **Step 1: Write failing parser tests**

Create `backend/tests/test_homeos_service.py`:

```python
import unittest

from app.services.homeos import parse_homeos_profile


class TestHomeOSService(unittest.TestCase):
    def test_parse_family_profile(self):
        avatar = parse_homeos_profile(
            "We are a young family, budget 750k, need 4-room, care about primary schools, "
            "one parent works in Raffles Place, low risk tolerance."
        )

        self.assertEqual(avatar["label"], "Family HomeOS Agent")
        self.assertEqual(avatar["buyer_type"], "family")
        self.assertEqual(avatar["preferences"]["flat_type"], "4 ROOM")
        self.assertEqual(avatar["preferences"]["max_price"], 750000.0)
        self.assertEqual(avatar["preferences"]["school_priority"], "high")
        self.assertEqual(avatar["preferences"]["risk_tolerance"], "low")
        self.assertEqual(avatar["preferences"]["commute_priority"], "medium")

    def test_parse_commute_first_profile(self):
        avatar = parse_homeos_profile(
            "Single professional looking for executive flat below 1.1m, must be close to MRT, "
            "okay with some appreciation risk."
        )

        self.assertEqual(avatar["label"], "Commute HomeOS Agent")
        self.assertEqual(avatar["buyer_type"], "single")
        self.assertEqual(avatar["preferences"]["flat_type"], "EXECUTIVE")
        self.assertEqual(avatar["preferences"]["max_price"], 1100000.0)
        self.assertEqual(avatar["preferences"]["commute_priority"], "high")
        self.assertEqual(avatar["preferences"]["risk_tolerance"], "medium")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run parser tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_service -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.homeos'`.

- [ ] **Step 3: Implement parser**

Create `backend/app/services/homeos.py`:

```python
"""HomeOS Agent: profile parsing, HDB investigation, and viewing handoff."""
from __future__ import annotations

import re
from typing import Any


FLAT_TYPES = ("2 ROOM", "3 ROOM", "4 ROOM", "5 ROOM", "EXECUTIVE")


def _normalise(text: str) -> str:
    return " ".join(text.upper().replace("-", " ").split())


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in words)


def _extract_flat_type(text: str) -> str | None:
    norm = _normalise(text)
    compact = norm.replace(" ", "")
    for flat_type in FLAT_TYPES:
        if flat_type in norm:
            return flat_type
    if "2ROOM" in compact:
        return "2 ROOM"
    if "3ROOM" in compact:
        return "3 ROOM"
    if "4ROOM" in compact:
        return "4 ROOM"
    if "5ROOM" in compact:
        return "5 ROOM"
    if "EXEC" in compact:
        return "EXECUTIVE"
    return None


def _extract_budget(text: str) -> float | None:
    lowered = text.lower().replace(",", "")
    patterns = [
        r"(?:under|below|up to|max|maximum|budget)\s*\$?\s*(\d+(?:\.\d+)?)\s*(m|mil|million|k)?",
        r"\$?\s*(\d+(?:\.\d+)?)\s*(m|mil|million|k)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        value = float(match.group(1))
        suffix = match.group(2)
        if suffix in {"m", "mil", "million"}:
            return value * 1_000_000
        if suffix == "k":
            return value * 1_000
        if value < 10_000:
            return value * 1_000
        return value
    return None


def parse_homeos_profile(profile_text: str) -> dict[str, Any]:
    """Parse natural-language household goals into HomeOS buyer preferences."""
    buyer_type = "family" if _has_any(profile_text, ("family", "kids", "children", "child", "primary school", "schools")) else "single"
    commute_priority = "high" if _has_any(profile_text, ("must be close to mrt", "near mrt", "close to mrt", "commute")) else "medium"
    school_priority = "high" if _has_any(profile_text, ("primary school", "schools", "kids", "children", "family")) else "low"
    risk_tolerance = "medium" if _has_any(profile_text, ("some risk", "appreciation risk", "growth", "invest")) else "low"
    appreciation_priority = "high" if _has_any(profile_text, ("growth", "appreciation", "investment", "undervalued")) else "medium"

    if buyer_type == "family":
        label = "Family HomeOS Agent"
        summary = "Family buyer prioritizing schools, budget fit, and lower-risk viewing choices."
    elif commute_priority == "high":
        label = "Commute HomeOS Agent"
        summary = "Commute-focused buyer prioritizing MRT access and practical viewing choices."
    else:
        label = "Careful HomeOS Agent"
        summary = "Careful buyer balancing affordability, accessibility, and resale evidence."

    return {
        "label": label,
        "buyer_type": buyer_type,
        "summary": summary,
        "preferences": {
            "flat_type": _extract_flat_type(profile_text),
            "max_price": _extract_budget(profile_text),
            "commute_priority": commute_priority,
            "school_priority": school_priority,
            "risk_tolerance": risk_tolerance,
            "appreciation_priority": appreciation_priority,
        },
    }
```

- [ ] **Step 4: Run parser tests to verify they pass**

Run:

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_service -v
```

Expected: PASS both tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/homeos.py backend/tests/test_homeos_service.py
git commit -m "feat: add homeos profile parser"
```

---

### Task 2: Backend Agent Units And Investigation Case Files

**Files:**
- Create: `backend/app/services/homeos_agents.py`
- Create: `backend/tests/test_homeos_agents.py`
- Modify: `backend/app/services/homeos.py`
- Modify: `backend/tests/test_homeos_service.py`

- [ ] **Step 1: Write failing sub-agent tests**

Create `backend/tests/test_homeos_agents.py`:

```python
import unittest

from app.data.seed import build_seeded_repo
from app.services.homeos import parse_homeos_profile
from app.services.homeos_agents import (
    location_graph_agent,
    market_analysis_agent,
    risk_value_agent,
    viewing_questions_agent,
    worth_viewing_score,
)


class TestHomeOSAgents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=6, months=12)
        cls.avatar = parse_homeos_profile(
            "Family looking for 4 room under 800k near primary schools and MRT."
        )

    def test_market_analysis_agent_uses_repository_transactions(self):
        evidence = market_analysis_agent(self.repo, 1, self.avatar["preferences"])

        self.assertIn("transaction_count", evidence)
        self.assertIn("median_price", evidence)
        self.assertIn("median_psf", evidence)
        self.assertIn(evidence["budget_signal"], {"within_budget", "above_budget", "unknown"})
        self.assertIn(evidence["confidence"], {"high", "medium", "low"})

    def test_location_graph_agent_uses_repository_proximity(self):
        evidence = location_graph_agent(self.repo, 1)

        self.assertIn("connections", evidence)
        self.assertGreaterEqual(len(evidence["connections"]), 2)
        self.assertEqual(evidence["connections"][0]["type"], "mrt")
        self.assertEqual(evidence["connections"][1]["type"], "primary_school")

    def test_risk_value_agent_uses_existing_services(self):
        evidence = risk_value_agent(self.repo, 1, self.avatar["preferences"])

        self.assertIn("appreciation", evidence)
        self.assertIn("future_mrt", evidence)
        self.assertIn("future_supply", evidence)
        self.assertIn("watchouts", evidence)
        self.assertIn("score_adjustment", evidence)

    def test_viewing_questions_agent_uses_evidence(self):
        questions = viewing_questions_agent({
            "market": {"confidence": "low"},
            "location": {"connections": [{"type": "mrt", "signal": "weak"}]},
            "risk": {"watchouts": ["Future supply risk is elevated."]},
        })

        self.assertGreaterEqual(len(questions), 4)
        self.assertTrue(any("limited recent resale evidence" in q.lower() for q in questions))
        self.assertTrue(any("walking route" in q.lower() for q in questions))

    def test_worth_viewing_score_is_bounded(self):
        score, reasons, watchouts = worth_viewing_score(
            market={"budget_signal": "within_budget", "transaction_count": 6},
            location={"connections": [
                {"type": "mrt", "signal": "moderate"},
                {"type": "primary_school", "signal": "strong"},
            ]},
            risk={"score_adjustment": 8, "watchouts": []},
            prefs=self.avatar["preferences"],
        )

        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        self.assertTrue(reasons)
        self.assertIsInstance(watchouts, list)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run sub-agent tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_agents -v
```

Expected: FAIL because `app.services.homeos_agents` is missing.

- [ ] **Step 3: Implement sub-agent units**

Create `backend/app/services/homeos_agents.py`:

```python
"""Deterministic HomeOS sub-agents.

These are normal service units, not autonomous networked agents. Each one reads
through the Repository interface so mock mode and PostGIS mode share behavior.
"""
from __future__ import annotations

from typing import Any

from app.repositories.base import Repository
from app.services.accessibility import block_accessibility
from app.services.appreciation import appreciation
from app.services.future_dev import future_mrt, future_supply
from app.services.stats import summarize


def market_analysis_agent(repo: Repository, block_id: int, prefs: dict[str, Any]) -> dict[str, Any]:
    txns = list(repo.transactions_for_block(block_id))
    flat_type = prefs.get("flat_type")
    if flat_type:
        txns = [txn for txn in txns if txn.flat_type == flat_type]
    recent = sorted(txns, key=lambda txn: txn.transaction_month, reverse=True)[:6]
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
    return {
        "transaction_count": summary.txn_count,
        "median_price": median_price,
        "median_psf": round(summary.median_psf, 2) if summary.median_psf else None,
        "window_months": 6,
        "budget_signal": budget_signal,
        "confidence": confidence,
        "summary": f"{summary.txn_count} similar {label} transactions support price confidence.",
        "data_source": "repository.transactions_for_block",
    }


def location_graph_agent(repo: Repository, block_id: int) -> dict[str, Any]:
    prox = repo.proximity(block_id)
    if prox is None:
        return {"connections": [], "data_source": "repository.proximity"}
    mrt_distance = prox.nearest_mrt_distance_m
    mrt_signal = "strong" if mrt_distance is not None and mrt_distance <= 500 else "moderate" if mrt_distance is not None and mrt_distance <= 1000 else "weak"
    school_signal = "strong" if prox.schools_within_1km >= 2 else "moderate" if prox.schools_within_1km == 1 else "weak"
    return {
        "connections": [
            {
                "type": "mrt",
                "name": "Nearest operational MRT",
                "distance_m": mrt_distance,
                "signal": mrt_signal,
            },
            {
                "type": "primary_school",
                "name": "Primary schools within 1km",
                "count": prox.schools_within_1km,
                "signal": school_signal,
            },
        ],
        "data_source": "repository.proximity",
    }


def risk_value_agent(repo: Repository, block_id: int, prefs: dict[str, Any]) -> dict[str, Any]:
    app = appreciation(repo, block_id)
    future_mrt_data = future_mrt(repo, block_id)
    future_supply_data = future_supply(repo, block_id)
    accessibility = block_accessibility(repo, block_id)
    watchouts: list[str] = []
    score_adjustment = 0.0
    if app and app.get("appreciation_score") is not None:
        score_adjustment += min(12.0, app["appreciation_score"] / 10)
    if app and app.get("risk_level") == "high" and prefs.get("risk_tolerance") == "low":
        watchouts.append("Appreciation model flags elevated risk for a low-risk buyer.")
        score_adjustment -= 8.0
    if future_supply_data and future_supply_data.get("supply_risk") == "high":
        watchouts.append("Nearby future supply may weigh on appreciation.")
        score_adjustment -= 4.0
    return {
        "appreciation": app,
        "future_mrt": future_mrt_data,
        "future_supply": future_supply_data,
        "accessibility": accessibility,
        "watchouts": watchouts,
        "score_adjustment": score_adjustment,
        "data_source": "services.appreciation/future_dev/accessibility",
    }


def viewing_questions_agent(evidence: dict[str, Any]) -> list[str]:
    questions = [
        "Which floor range is the unit in?",
        "Is the unit facing a main road or MRT track?",
        "Are recent comparable transactions renovated or original condition?",
        "Are there ethnic quota or extension restrictions?",
    ]
    market = evidence.get("market", {})
    location = evidence.get("location", {})
    if market.get("confidence") == "low":
        questions.append("Why is there limited recent resale evidence for this block or flat type?")
    if any(conn.get("signal") == "weak" for conn in location.get("connections", [])):
        questions.append("What is the realistic walking route and time to the nearest MRT or school?")
    return questions


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

- [ ] **Step 4: Run sub-agent tests to verify they pass**

Run:

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_agents -v
```

Expected: PASS.

- [ ] **Step 5: Add failing orchestration tests**

Append to `backend/tests/test_homeos_service.py`:

```python
from app.data.seed import build_seeded_repo
from app.services.homeos import build_homeos_case_file, investigate_homeos_profile


class TestHomeOSInvestigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_seeded_repo(seed=42, blocks_per_area=6, months=12)

    def test_build_case_file_contains_evidence_and_questions(self):
        case_file = build_homeos_case_file(
            self.repo,
            profile_text="Family looking for 4 room under 800k near primary schools and MRT.",
            block_id=1,
        )

        self.assertEqual(case_file["block_id"], 1)
        self.assertIn(case_file["verdict"], {"Worth viewing", "Maybe view", "Skip for now"})
        self.assertIn("recent_sales", case_file["evidence"])
        self.assertIn("connections", case_file["evidence"])
        self.assertIn("risks", case_file["evidence"])
        self.assertIn("agent_questions", case_file["evidence"])
        self.assertGreaterEqual(len(case_file["evidence"]["agent_questions"]), 3)

    def test_investigate_homeos_profile_returns_sorted_shortlist(self):
        result = investigate_homeos_profile(
            self.repo,
            profile_text="Family looking for 4 room under 800k near primary schools and MRT.",
            limit=5,
        )

        self.assertIn("avatar", result)
        self.assertIn("shortlist", result)
        self.assertLessEqual(len(result["shortlist"]), 5)
        self.assertTrue(result["shortlist"])
        scores = [row["worth_viewing_score"] for row in result["shortlist"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertIn("top_reasons", result["shortlist"][0])
        self.assertIn("top_watchouts", result["shortlist"][0])
```

- [ ] **Step 6: Run orchestration tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_service -v
```

Expected: FAIL because `build_homeos_case_file` and `investigate_homeos_profile` are missing.

- [ ] **Step 7: Implement case files and shortlist investigation using sub-agents**

Append to `backend/app/services/homeos.py`:

```python
from app.repositories.base import Repository
from app.services.homeos_agents import (
    location_graph_agent,
    market_analysis_agent,
    risk_value_agent,
    viewing_questions_agent,
    worth_viewing_score,
)


def _verdict(score: float) -> str:
    if score >= 75:
        return "Worth viewing"
    if score >= 50:
        return "Maybe view"
    return "Skip for now"


def _confidence(recent_sales: dict[str, Any]) -> str:
    if recent_sales["transaction_count"] >= 6:
        return "high"
    if recent_sales["transaction_count"] >= 3:
        return "medium"
    return "low"


def _agent_questions(watchouts: list[str]) -> list[str]:
    questions = [
        "Which floor range is the unit in?",
        "Is the unit facing a main road or MRT track?",
        "Are recent comparable transactions renovated or original condition?",
        "Are there ethnic quota or extension restrictions?",
    ]
    if any("MRT" in watchout for watchout in watchouts):
        questions.append("What is the realistic walking route and time to the nearest MRT?")
    if any("school" in watchout.lower() for watchout in watchouts):
        questions.append("Which primary schools are realistically within 1km by address?")
    return questions


def build_homeos_case_file(repo: Repository, profile_text: str, block_id: int) -> dict[str, Any]:
    block = repo.block(block_id)
    if block is None:
        raise ValueError("block not found")
    avatar = parse_homeos_profile(profile_text)
    market = market_analysis_agent(repo, block_id, avatar["preferences"])
    location = location_graph_agent(repo, block_id)
    risk = risk_value_agent(repo, block_id, avatar["preferences"])
    score, reasons, watchouts = worth_viewing_score(market, location, risk, avatar["preferences"])
    questions = viewing_questions_agent({
        "market": market,
        "location": location,
        "risk": risk,
    })
    return {
        "block_id": block_id,
        "block_number": block.block_number,
        "street_name": block.street_name,
        "town": block.town,
        "verdict": _verdict(score),
        "worth_viewing_score": score,
        "confidence": _confidence(recent_sales),
        "top_reasons": reasons,
        "top_watchouts": watchouts,
        "evidence": {
            "recent_sales": market,
            "connections": location["connections"],
            "risks": watchouts,
            "future_signals": {
                "future_mrt": risk["future_mrt"],
                "future_supply": risk["future_supply"],
            },
            "agent_questions": questions,
            "agent_outputs": {
                "market": market,
                "location": location,
                "risk": risk,
            },
        },
    }


def investigate_homeos_profile(repo: Repository, profile_text: str, limit: int = 5) -> dict[str, Any]:
    avatar = parse_homeos_profile(profile_text)
    rows = []
    for block in repo.blocks():
        case_file = build_homeos_case_file(repo, profile_text, block.block_id)
        if avatar["preferences"]["flat_type"] and case_file["evidence"]["recent_sales"]["transaction_count"] == 0:
            continue
        rows.append({
            "block_id": case_file["block_id"],
            "block_number": case_file["block_number"],
            "street_name": case_file["street_name"],
            "town": case_file["town"],
            "worth_viewing_score": case_file["worth_viewing_score"],
            "verdict": case_file["verdict"],
            "confidence": case_file["confidence"],
            "top_reasons": case_file["top_reasons"],
            "top_watchouts": case_file["top_watchouts"],
        })
    rows.sort(key=lambda row: (-row["worth_viewing_score"], row["block_id"]))
    return {"avatar": avatar, "shortlist": rows[:limit]}
```

- [ ] **Step 8: Run HomeOS backend tests**

Run:

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_agents tests.test_homeos_service -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/homeos.py backend/app/services/homeos_agents.py backend/tests/test_homeos_agents.py backend/tests/test_homeos_service.py
git commit -m "feat: add homeos hdb investigation"
```

---

### Task 3: Scheduling-Agent Handoff

**Files:**
- Modify: `backend/app/services/homeos.py`
- Modify: `backend/tests/test_homeos_service.py`

- [ ] **Step 1: Add failing scheduling tests**

Append to `TestHomeOSInvestigation` in `backend/tests/test_homeos_service.py`:

```python
    def test_schedule_viewing_creates_visible_outbox_message(self):
        from app.services.homeos import schedule_homeos_viewing

        response = schedule_homeos_viewing(
            self.repo,
            profile_text="Family looking for 4 room under 800k near primary schools.",
            block_id=1,
            availability=["2026-06-13 10:00-12:00"],
            contact_name="Moe",
            contact_note="Prefer WhatsApp follow-up.",
        )

        self.assertEqual(response["status"], "ready_for_agent")
        self.assertIn("HomeOS prepared the scheduling handoff", response["confirmation"])
        self.assertEqual(response["outbox"]["recipient_type"], "real_estate_agent")
        self.assertIn("Moe would like to view", response["outbox"]["message"])
        self.assertIn("Due-diligence questions:", response["outbox"]["message"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_service -v
```

Expected: FAIL because `schedule_homeos_viewing` is missing.

- [ ] **Step 3: Implement scheduling handoff**

Append to `backend/app/services/homeos.py`:

```python
def schedule_homeos_viewing(
    repo: Repository,
    profile_text: str,
    block_id: int,
    availability: list[str],
    contact_name: str,
    contact_note: str | None = None,
) -> dict[str, Any]:
    block = repo.block(block_id)
    if block is None:
        raise ValueError("block not found")
    clean_availability = [slot.strip() for slot in availability if slot.strip()]
    if not clean_availability:
        raise ValueError("at least one availability slot is required")

    avatar = parse_homeos_profile(profile_text)
    case_file = build_homeos_case_file(repo, profile_text, block_id)
    address = f"Blk {block.block_number} {block.street_name}"
    availability_text = "; ".join(clean_availability)
    question_text = " ".join(case_file["evidence"]["agent_questions"][:2])
    note = f" Note: {contact_note.strip()}" if contact_note and contact_note.strip() else ""
    message = (
        f"Hi, {contact_name.strip()} would like to view {address}. "
        f"Availability: {availability_text}. "
        f"Buyer profile: {avatar['summary']} "
        f"Due-diligence questions: {question_text}{note}"
    )
    return {
        "status": "ready_for_agent",
        "confirmation": (
            f"{address} is selected for viewing. HomeOS prepared the scheduling handoff with "
            f"{len(clean_availability)} availability window"
            f"{'' if len(clean_availability) == 1 else 's'}."
        ),
        "outbox": {
            "block_id": block_id,
            "recipient_type": "real_estate_agent",
            "message": message,
            "availability": clean_availability,
        },
    }
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_service -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/homeos.py backend/tests/test_homeos_service.py
git commit -m "feat: add homeos scheduling handoff"
```

---

### Task 4: FastAPI HomeOS Endpoints

**Files:**
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/api/main.py`
- Test: `backend/tests/test_homeos_api.py`

- [ ] **Step 1: Write failing API tests**

Create `backend/tests/test_homeos_api.py`:

```python
import unittest

from fastapi.testclient import TestClient

from app.api.main import app


class TestHomeOSApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_investigate_endpoint(self):
        res = self.client.post(
            "/homeos/investigate",
            json={
                "profile_text": "Family looking for 4 room under 800k near primary schools and MRT.",
                "limit": 3,
            },
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("avatar", body)
        self.assertIn("shortlist", body)
        self.assertLessEqual(len(body["shortlist"]), 3)

    def test_case_file_endpoint(self):
        res = self.client.post(
            "/homeos/case-file/1",
            json={"profile_text": "Family looking for 4 room under 800k near primary schools."},
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["block_id"], 1)
        self.assertIn("agent_questions", body["evidence"])

    def test_schedule_viewing_endpoint(self):
        res = self.client.post(
            "/homeos/schedule-viewing",
            json={
                "profile_text": "Family looking for 4 room under 800k near primary schools.",
                "block_id": 1,
                "availability": ["2026-06-13 10:00-12:00"],
                "contact_name": "Moe",
                "contact_note": "Prefer WhatsApp follow-up.",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ready_for_agent")
        self.assertIn("outbox", res.json())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m unittest tests.test_homeos_api -v
```

Expected: FAIL with 404 for the new endpoints.

- [ ] **Step 3: Add schemas**

Append to `backend/app/api/schemas.py`:

```python
class HomeOSInvestigationRequest(BaseModel):
    profile_text: str = Field(..., min_length=10)
    limit: int = Field(5, ge=1, le=20)


class HomeOSCaseFileRequest(BaseModel):
    profile_text: str = Field(..., min_length=10)


class HomeOSScheduleViewingRequest(BaseModel):
    profile_text: str = Field(..., min_length=10)
    block_id: int
    availability: list[str] = Field(..., min_length=1)
    contact_name: str = Field(..., min_length=1)
    contact_note: str | None = None
```

- [ ] **Step 4: Wire endpoints**

Modify `backend/app/api/main.py` imports:

```python
from app.api.schemas import (
    CommuteRequest,
    CoupleRequest,
    DreamHomeRequest,
    HomeOSCaseFileRequest,
    HomeOSInvestigationRequest,
    HomeOSScheduleViewingRequest,
    LifestyleRequest,
    RecommendationRequest,
)
from app.services.homeos import (
    build_homeos_case_file,
    investigate_homeos_profile,
    schedule_homeos_viewing,
)
```

Add after `/comparison/estates`:

```python
@app.post("/homeos/investigate")
def homeos_investigate(req: HomeOSInvestigationRequest,
                       repo: Repository = Depends(get_repository)):
    return investigate_homeos_profile(repo, req.profile_text, req.limit)


@app.post("/homeos/case-file/{block_id}")
def homeos_case_file(block_id: int, req: HomeOSCaseFileRequest,
                     repo: Repository = Depends(get_repository)):
    try:
        return build_homeos_case_file(repo, req.profile_text, block_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/homeos/schedule-viewing")
def homeos_schedule_viewing(req: HomeOSScheduleViewingRequest,
                            repo: Repository = Depends(get_repository)):
    try:
        return schedule_homeos_viewing(
            repo,
            profile_text=req.profile_text,
            block_id=req.block_id,
            availability=req.availability,
            contact_name=req.contact_name,
            contact_note=req.contact_note,
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "block not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc))
```

- [ ] **Step 5: Run backend tests**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest -q
```

Expected: all backend tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/schemas.py backend/app/api/main.py backend/tests/test_homeos_api.py
git commit -m "feat: expose homeos agent api"
```

---

### Task 5: Frontend Types And API Client

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Test: `frontend/src/lib/api.test.ts`

- [ ] **Step 1: Write failing API client tests**

Create `frontend/src/lib/api.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { getHomeOSCaseFile, investigateHomeOSProfile, scheduleHomeOSViewing } from "./api";

describe("homeos api client", () => {
  afterEach(() => vi.restoreAllMocks());

  it("posts profile text to investigate endpoint", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ avatar: {}, shortlist: [] }) }));
    await investigateHomeOSProfile("Family looking for 4 room under 800k.", 4);
    expect(fetch).toHaveBeenCalledWith("/api/homeos/investigate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_text: "Family looking for 4 room under 800k.", limit: 4 }),
    });
  });

  it("posts profile text to case-file endpoint", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ block_id: 1, evidence: {} }) }));
    await getHomeOSCaseFile(1, "Family looking for 4 room under 800k.");
    expect(fetch).toHaveBeenCalledWith("/api/homeos/case-file/1", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_text: "Family looking for 4 room under 800k." }),
    });
  });

  it("posts scheduling request", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "ready_for_agent" }) }));
    await scheduleHomeOSViewing({
      profile_text: "Family looking for 4 room under 800k.",
      block_id: 1,
      availability: ["2026-06-13 10:00-12:00"],
      contact_name: "Moe",
      contact_note: "Prefer WhatsApp.",
    });
    expect(fetch).toHaveBeenCalledWith("/api/homeos/schedule-viewing", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile_text: "Family looking for 4 room under 800k.",
        block_id: 1,
        availability: ["2026-06-13 10:00-12:00"],
        contact_name: "Moe",
        contact_note: "Prefer WhatsApp.",
      }),
    });
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd frontend && npm run test -- src/lib/api.test.ts --run
```

Expected: FAIL because the new API methods are not exported.

- [ ] **Step 3: Add types**

Append to `frontend/src/types.ts`:

```ts
export interface HomeOSPreferences {
  flat_type: string | null;
  max_price: number | null;
  commute_priority: "low" | "medium" | "high";
  school_priority: "low" | "medium" | "high";
  risk_tolerance: "low" | "medium";
  appreciation_priority: "medium" | "high";
}

export interface HomeOSAvatar {
  label: string;
  buyer_type: string;
  summary: string;
  preferences: HomeOSPreferences;
}

export interface HomeOSShortlistRow {
  block_id: number;
  block_number: string;
  street_name: string;
  town: string;
  worth_viewing_score: number;
  verdict: "Worth viewing" | "Maybe view" | "Skip for now";
  confidence: "low" | "medium" | "high";
  top_reasons: string[];
  top_watchouts: string[];
}

export interface HomeOSInvestigationResponse {
  avatar: HomeOSAvatar;
  shortlist: HomeOSShortlistRow[];
}

export interface HomeOSCaseFile {
  block_id: number;
  block_number: string;
  street_name: string;
  town: string;
  verdict: string;
  worth_viewing_score: number;
  confidence: "low" | "medium" | "high";
  top_reasons: string[];
  top_watchouts: string[];
  evidence: {
    recent_sales: {
      transaction_count: number;
      median_price: number | null;
      median_psf: number | null;
      window_months: number;
      summary: string;
    };
    connections: Record<string, unknown>[];
    risks: string[];
    future_signals: Record<string, unknown>;
    agent_questions: string[];
  };
}

export interface HomeOSScheduleViewingBody {
  profile_text: string;
  block_id: number;
  availability: string[];
  contact_name: string;
  contact_note?: string;
}

export interface HomeOSScheduleViewingResponse {
  status: "ready_for_agent";
  confirmation: string;
  outbox: {
    block_id: number;
    recipient_type: "real_estate_agent";
    message: string;
    availability: string[];
  };
}
```

- [ ] **Step 4: Add API methods**

Modify `frontend/src/lib/api.ts` type imports to include:

```ts
  HomeOSCaseFile,
  HomeOSInvestigationResponse,
  HomeOSScheduleViewingBody,
  HomeOSScheduleViewingResponse,
```

Append after `getEstateComparison`:

```ts
export function investigateHomeOSProfile(
  profileText: string,
  limit = 5,
): Promise<HomeOSInvestigationResponse> {
  return postJSON<HomeOSInvestigationResponse>("/homeos/investigate", {
    profile_text: profileText,
    limit,
  });
}

export function getHomeOSCaseFile(
  blockId: number,
  profileText: string,
): Promise<HomeOSCaseFile> {
  return postJSON<HomeOSCaseFile>(`/homeos/case-file/${blockId}`, {
    profile_text: profileText,
  });
}

export function scheduleHomeOSViewing(
  body: HomeOSScheduleViewingBody,
): Promise<HomeOSScheduleViewingResponse> {
  return postJSON<HomeOSScheduleViewingResponse>("/homeos/schedule-viewing", body);
}
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd frontend && npm run test -- src/lib/api.test.ts --run
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types.ts frontend/src/lib/api.ts frontend/src/lib/api.test.ts
git commit -m "feat: add homeos api client"
```

---

### Task 6: AI Mode Left Panel

**Files:**
- Create: `frontend/src/components/HomeOSAgentPanel.tsx`
- Test: `frontend/src/components/HomeOSAgentPanel.test.tsx`
- Modify: `frontend/src/App.tsx`

**PRD Requirement:**

The left panel must support an explicit **AI Mode**. AI Mode is the default demo surface and lets the user prompt HomeOS in natural language.

```text
Left panel modes:
[AI Mode] [Explore]
```

AI Mode should include:

- `Household profile` natural-language prompt input
- sample prompt
- `Investigate homes` CTA
- HomeOS buyer avatar summary
- viewing shortlist
- selected recommendation preview
- entry point to open the right-side case-file panel

Explore mode should preserve the current filter/dashboard experience:

- flat type
- max PSF
- max walk to MRT
- min schools within 1km
- stats cards
- PSF trend
- estate comparison

Acceptance criteria:

- App defaults to AI Mode.
- User can switch between AI Mode and Explore without losing map state.
- Running `Investigate homes` updates the shortlist and highlights matching map nodes.
- Existing filters remain usable in Explore mode.
- The AI Mode panel does not become a generic chat feed; it is a structured agent workflow.

- [ ] **Step 1: Write failing component tests**

Create `frontend/src/components/HomeOSAgentPanel.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import HomeOSAgentPanel from "./HomeOSAgentPanel";
import * as api from "../lib/api";

describe("HomeOSAgentPanel", () => {
  it("shows shortlist, case file evidence, and scheduling outbox", async () => {
    vi.spyOn(api, "investigateHomeOSProfile").mockResolvedValue({
      avatar: {
        label: "Family HomeOS Agent",
        buyer_type: "family",
        summary: "Family buyer prioritizing schools, budget fit, and lower-risk viewing choices.",
        preferences: {
          flat_type: "4 ROOM",
          max_price: 800000,
          commute_priority: "medium",
          school_priority: "high",
          risk_tolerance: "low",
          appreciation_priority: "medium",
        },
      },
      shortlist: [{
        block_id: 1,
        block_number: "101",
        street_name: "TAMPINES ST 1",
        town: "TAMPINES",
        worth_viewing_score: 88,
        verdict: "Worth viewing",
        confidence: "high",
        top_reasons: ["Recent comparable sales support the budget."],
        top_watchouts: ["MRT access is moderate rather than excellent."],
      }],
    });
    vi.spyOn(api, "getHomeOSCaseFile").mockResolvedValue({
      block_id: 1,
      block_number: "101",
      street_name: "TAMPINES ST 1",
      town: "TAMPINES",
      verdict: "Worth viewing",
      worth_viewing_score: 88,
      confidence: "high",
      top_reasons: ["Recent comparable sales support the budget."],
      top_watchouts: ["MRT access is moderate rather than excellent."],
      evidence: {
        recent_sales: {
          transaction_count: 6,
          median_price: 710000,
          median_psf: 650,
          window_months: 6,
          summary: "6 similar 4 ROOM transactions support price confidence.",
        },
        connections: [],
        risks: ["MRT access is moderate rather than excellent."],
        future_signals: {},
        agent_questions: ["Which floor range is the unit in?"],
      },
    });
    vi.spyOn(api, "scheduleHomeOSViewing").mockResolvedValue({
      status: "ready_for_agent",
      confirmation: "Blk 101 TAMPINES ST 1 is selected for viewing.",
      outbox: {
        block_id: 1,
        recipient_type: "real_estate_agent",
        message: "Hi, Moe would like to view Blk 101 TAMPINES ST 1.",
        availability: ["2026-06-13 10:00-12:00"],
      },
    });

    render(<HomeOSAgentPanel />);
    fireEvent.change(screen.getByLabelText("Household profile"), {
      target: { value: "Family looking for 4 room under 800k near primary schools." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Investigate homes" }));

    await screen.findByText("Family HomeOS Agent");
    fireEvent.click(screen.getByRole("button", { name: "Open case file" }));

    await screen.findByText("6 similar 4 ROOM transactions support price confidence.");
    fireEvent.change(screen.getByLabelText("Your name"), { target: { value: "Moe" } });
    fireEvent.change(screen.getByLabelText("Availability"), { target: { value: "2026-06-13 10:00-12:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Schedule viewing" }));

    await waitFor(() => {
      expect(screen.getByText("Scheduling outbox")).toBeInTheDocument();
    });
    expect(screen.getByText("Hi, Moe would like to view Blk 101 TAMPINES ST 1.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run component test to verify it fails**

Run:

```bash
cd frontend && npm run test -- src/components/HomeOSAgentPanel.test.tsx --run
```

Expected: FAIL because `HomeOSAgentPanel.tsx` is missing.

- [ ] **Step 3: Implement HomeOSAgentPanel**

Create `frontend/src/components/HomeOSAgentPanel.tsx`:

```tsx
import { useState } from "react";
import { getHomeOSCaseFile, investigateHomeOSProfile, scheduleHomeOSViewing } from "../lib/api";
import { formatPsf, formatSGD } from "../lib/format";
import type {
  HomeOSCaseFile,
  HomeOSInvestigationResponse,
  HomeOSScheduleViewingResponse,
  HomeOSShortlistRow,
} from "../types";

const DEFAULT_PROFILE =
  "Family looking for 4 room under 800k near primary schools and MRT.";

export default function HomeOSAgentPanel() {
  const [profileText, setProfileText] = useState(DEFAULT_PROFILE);
  const [investigation, setInvestigation] = useState<HomeOSInvestigationResponse | null>(null);
  const [caseFile, setCaseFile] = useState<HomeOSCaseFile | null>(null);
  const [selected, setSelected] = useState<HomeOSShortlistRow | null>(null);
  const [contactName, setContactName] = useState("");
  const [availability, setAvailability] = useState("");
  const [outbox, setOutbox] = useState<HomeOSScheduleViewingResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function investigate() {
    setLoading(true);
    setOutbox(null);
    const next = await investigateHomeOSProfile(profileText, 5);
    setInvestigation(next);
    setCaseFile(null);
    setSelected(null);
    setLoading(false);
  }

  async function openCaseFile(row: HomeOSShortlistRow) {
    setSelected(row);
    setLoading(true);
    const next = await getHomeOSCaseFile(row.block_id, profileText);
    setCaseFile(next);
    setLoading(false);
  }

  async function scheduleViewing() {
    if (!selected) return;
    const slots = availability.split(/\n|,/).map((slot) => slot.trim()).filter(Boolean);
    setLoading(true);
    const next = await scheduleHomeOSViewing({
      profile_text: profileText,
      block_id: selected.block_id,
      availability: slots,
      contact_name: contactName,
    });
    setOutbox(next);
    setLoading(false);
  }

  return (
    <section className="border-b border-gray-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-gray-900">HomeOS Agent</h2>
      <p className="mt-1 text-xs text-gray-500">From household goals to evidence-backed viewings.</p>

      <label className="mt-3 block">
        <span className="text-xs text-gray-500">Household profile</span>
        <textarea
          className="mt-1 min-h-24 w-full resize-none rounded border border-gray-300 p-2 text-sm"
          value={profileText}
          onChange={(event) => setProfileText(event.target.value)}
        />
      </label>

      <button
        type="button"
        className="mt-2 w-full rounded bg-gray-900 px-3 py-2 text-sm font-medium text-white disabled:bg-gray-400"
        disabled={loading || profileText.trim().length < 10}
        onClick={investigate}
      >
        {loading ? "Working..." : "Investigate homes"}
      </button>

      {investigation ? (
        <div className="mt-3 rounded border border-gray-200 bg-gray-50 p-3">
          <div className="text-sm font-semibold text-gray-900">{investigation.avatar.label}</div>
          <div className="mt-1 text-xs text-gray-600">{investigation.avatar.summary}</div>
        </div>
      ) : null}

      <div className="mt-3 space-y-2">
        {investigation?.shortlist.map((row) => (
          <div key={row.block_id} className="rounded border border-gray-200 bg-white p-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-sm font-semibold text-gray-900">
                  Blk {row.block_number} {row.street_name}
                </div>
                <div className="text-xs text-gray-500">{row.town} · {row.verdict}</div>
              </div>
              <div className="rounded bg-green-100 px-2 py-1 text-xs font-semibold text-green-700">
                {row.worth_viewing_score}%
              </div>
            </div>
            <ul className="mt-2 space-y-1 text-xs text-gray-600">
              {row.top_reasons.map((reason) => <li key={reason}>{reason}</li>)}
            </ul>
            {row.top_watchouts[0] ? (
              <div className="mt-2 text-xs text-amber-700">{row.top_watchouts[0]}</div>
            ) : null}
            <button
              type="button"
              className="mt-3 w-full rounded border border-gray-300 px-3 py-2 text-xs font-medium text-gray-800"
              onClick={() => openCaseFile(row)}
            >
              Open case file
            </button>
          </div>
        ))}
      </div>

      {caseFile ? (
        <div className="mt-3 rounded border border-gray-200 bg-gray-50 p-3">
          <div className="text-sm font-semibold text-gray-900">
            Case file: Blk {caseFile.block_number} {caseFile.street_name}
          </div>
          <div className="mt-2 text-xs text-gray-600">{caseFile.evidence.recent_sales.summary}</div>
          <div className="mt-1 text-xs text-gray-500">
            {formatSGD(caseFile.evidence.recent_sales.median_price)} · {formatPsf(caseFile.evidence.recent_sales.median_psf)}
          </div>
          <div className="mt-3 text-xs font-semibold uppercase text-gray-500">Questions for agent</div>
          <ul className="mt-1 space-y-1 text-xs text-gray-600">
            {caseFile.evidence.agent_questions.map((question) => <li key={question}>{question}</li>)}
          </ul>
          <label className="mt-3 block">
            <span className="text-xs text-gray-500">Your name</span>
            <input className="mt-1 w-full rounded border border-gray-300 p-2 text-sm" value={contactName} onChange={(event) => setContactName(event.target.value)} />
          </label>
          <label className="mt-3 block">
            <span className="text-xs text-gray-500">Availability</span>
            <textarea className="mt-1 min-h-16 w-full resize-none rounded border border-gray-300 p-2 text-sm" value={availability} onChange={(event) => setAvailability(event.target.value)} />
          </label>
          <button
            type="button"
            className="mt-3 w-full rounded bg-gray-900 px-3 py-2 text-sm font-medium text-white disabled:bg-gray-400"
            disabled={loading || !contactName.trim() || !availability.trim()}
            onClick={scheduleViewing}
          >
            Schedule viewing
          </button>
        </div>
      ) : null}

      {outbox ? (
        <div className="mt-3 rounded border border-green-200 bg-green-50 p-3">
          <div className="text-sm font-semibold text-green-800">Scheduling outbox</div>
          <div className="mt-2 text-xs text-green-700">{outbox.outbox.message}</div>
        </div>
      ) : null}
    </section>
  );
}
```

- [ ] **Step 4: Integrate in App**

Modify `frontend/src/App.tsx`:

```tsx
import HomeOSAgentPanel from "./components/HomeOSAgentPanel";
```

Render above `FilterPanel`:

```tsx
        <HomeOSAgentPanel />
        <FilterPanel filters={filters} onChange={setFilters} />
```

- [ ] **Step 5: Run component tests**

Run:

```bash
cd frontend && npm run test -- src/components/HomeOSAgentPanel.test.tsx --run
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/HomeOSAgentPanel.tsx frontend/src/components/HomeOSAgentPanel.test.tsx frontend/src/App.tsx
git commit -m "feat: add homeos ai mode panel"
```

---

### Task 7: Map Node Hover And Right-Side House Detail Panel

**Files:**
- Create: `frontend/src/components/HomeOSDetailPanel.tsx`
- Test: `frontend/src/components/HomeOSDetailPanel.test.tsx`
- Modify: `frontend/src/components/MapView.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/types.ts`

**PRD Requirement:**

Map nodes should support a lightweight preview on hover and a deeper right-side detail panel on click.

Hover behavior:

- Hovering a node shows a compact summary.
- Summary includes block address, town, median PSF, median price, MRT distance, schools within 1km, and HomeOS verdict when available.
- Summary includes a `More` action.

Click behavior:

- Clicking the node opens the right-side detail panel.
- Clicking `More` opens the same right-side detail panel.
- The selected map marker becomes visually distinct.
- The map remains visible behind/next to the panel.

Right-side panel content:

- block address and town
- key numbers
- recent sales evidence
- MRT/school connection evidence
- risks/watchouts
- questions for the real-estate agent
- `Select for viewing`
- availability input
- visible scheduling outbox after submission

Acceptance criteria:

- Hover preview appears without requiring a click.
- Node click and `More` open the same right-side panel.
- Closing the panel clears the selected block but keeps the shortlist.
- HomeOS shortlisted blocks are visually distinct from ordinary result markers.
- Selected block is visually distinct from both ordinary and shortlisted markers.
- Right panel can be implemented as a docked panel on desktop and bottom sheet on mobile.

Implementation note:

This ticket should lift selected block state into `App.tsx` so both `MapView` and `HomeOSDetailPanel` share the same selected block. `MapView` should remain a rendering component and should receive callbacks such as `onBlockHover`, `onBlockSelect`, and shortlist/selected IDs as props.

- [ ] **Step 1: Write detail-panel and map interaction tests**

Run:

```bash
cd frontend && npm run test -- src/components/HomeOSDetailPanel.test.tsx --run
```

Expected: FAIL because the detail panel and map interaction props do not exist yet.

- [ ] **Step 2: Implement right-side panel state and rendering**

Implement `HomeOSDetailPanel` and wire selected block state through `App.tsx`.

- [ ] **Step 3: Implement map hover/click callbacks**

Update `MapView` so markers can show hover summaries and open the right-side detail panel.

- [ ] **Step 4: Run frontend tests**

Run:

```bash
cd frontend && npm run test -- src/components/HomeOSDetailPanel.test.tsx --run
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/HomeOSDetailPanel.tsx frontend/src/components/HomeOSDetailPanel.test.tsx frontend/src/components/MapView.tsx frontend/src/App.tsx frontend/src/types.ts
git commit -m "feat: add homeos map detail panel"
```

---

### Task 8: Documentation And Manual Demo Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update API reference**

Add these rows to the API reference table in `README.md`:

```markdown
| `POST /homeos/investigate` | Parse household goals and return evidence-backed HDB viewing shortlist |
| `POST /homeos/case-file/{block_id}` | Build a HomeOS case file for a selected HDB block |
| `POST /homeos/schedule-viewing` | Create a visible scheduling-agent outbox message for a selected viewing |
```

- [ ] **Step 2: Run backend suite**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest -q
```

Expected: all backend tests pass.

- [ ] **Step 3: Run frontend suite**

Run:

```bash
cd frontend && npm run test -- --run
```

Expected: all frontend tests pass.

- [ ] **Step 4: Verify API manually**

Run:

```bash
curl -s -X POST http://127.0.0.1:8000/homeos/investigate \
  -H 'Content-Type: application/json' \
  -d '{"profile_text":"Family looking for 4 room under 800k near primary schools and MRT.","limit":3}'
```

Expected: response includes `avatar` and `shortlist`.

- [ ] **Step 5: Verify frontend manually**

Open:

```text
http://127.0.0.1:5173/
```

Expected flow:

1. Sidebar opens in `AI Mode`.
2. User enters household profile.
3. Click `Investigate homes`.
4. Shortlist appears with verdict, score, reasons, and watchouts.
5. Map highlights HomeOS shortlisted nodes.
6. Hovering a node shows a compact summary.
7. Clicking a node or `More` opens the right-side detail panel.
8. Detail panel shows recent sales evidence and questions for the agent.
9. User enters name and availability.
10. Click `Schedule viewing`.
11. `Scheduling outbox` appears with the generated message.

- [ ] **Step 6: Commit docs**

```bash
git add README.md
git commit -m "docs: document homeos agent api"
```

---

## Self-Review

Spec coverage:

- Natural-language household profile input is covered in Tasks 1, 4, 5, and 6.
- Buyer avatar creation is covered in Tasks 1 and 6.
- Evidence-backed shortlist is covered in Tasks 2, 4, 5, and 6.
- Case-file investigation is covered in Tasks 2, 4, 5, and 6.
- Recent sales evidence is covered in Task 2.
- MRT and primary-school evidence is covered in Task 2.
- Agent questions are covered in Tasks 2, 3, and 6.
- AI Mode in the left panel is covered in Task 6.
- Map hover summaries and right-side detail panel are covered in Task 7.
- Scheduling is a first-class demo step in Tasks 3, 4, 5, 6, and 7.
- External messaging is intentionally out of scope and represented by the visible outbox.

Placeholder scan:

- No external integration is promised.
- No LLM integration is promised.
- The scheduling agent is explicitly scoped as a visible outbox/handoff.

Type consistency:

- Backend endpoints use `/homeos/*`.
- Backend request fields use snake_case.
- Frontend request body types mirror backend snake_case.
- `worth_viewing_score`, `case_file`, `agent_questions`, and `outbox.message` are consistent across contracts, tests, and implementation steps.
