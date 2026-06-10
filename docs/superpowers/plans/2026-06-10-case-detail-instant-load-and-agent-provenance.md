# Case Detail: Instant Load + Per-Line Agent Provenance + Agent Trace — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make clicking a HomeOS recommendation open instantly by reading the already-computed case evidence from the in-memory case store instead of recomputing it, while adding per-line agent provenance chips and an agent-trace (tool calls) view.

**Architecture:** The streaming pipeline already stores per-block evidence, tool calls, and narratives in `case["pipeline"]`. A new read-side assembler reconstructs the case-file response (plus a `trace` field) from those stored events — no DB recompute, no LLM. `worth_viewing_score` is changed to emit attributed `{text, source}` items so each reason/watchout can show the agent that produced it. The existing recompute path stays as a graceful fallback for explore-mode/non-shortlisted blocks.

**Tech Stack:** Backend — Python, FastAPI, in-memory case store, `unittest`/`pytest`. Frontend — React + TypeScript, Vite, Vitest + Testing Library.

**Branch:** `feat/case-detail-instant-load`

**Reference spec:** `docs/superpowers/specs/2026-06-10-case-detail-instant-load-and-agent-provenance-design.md`

---

## File Structure

**Backend (active path is `app/homeos/*`; `app/services/homeos.py` is unused legacy — do NOT touch it):**
- `backend/app/homeos/scoring.py` — modify `worth_viewing_score` to return attributed items; add `EvidenceItem`, `item_texts`.
- `backend/app/homeos/sync_agents.py` — extract deterministic `base_viewing_questions`; `viewing_questions_agent` reuses it.
- `backend/app/homeos/pipeline.py` — `build_homeos_case_file`: keep `evidence.risks` as `list[str]` via `item_texts`, add `trace: []`.
- `backend/app/homeos/case_assembler.py` — **new**: `assemble_case_file_from_case(case_id, block_id)`.
- `backend/app/api/schemas.py` — add optional `case_id` to `HomeOSCaseFileRequest`.
- `backend/app/api/main.py` — endpoint tries assembler when `case_id` present, falls back to recompute.

**Frontend:**
- `frontend/src/types.ts` — `EvidenceItem`, `AgentTrace`; change `top_reasons`/`top_watchouts` to `EvidenceItem[]`; add `trace?` to `HomeOSCaseFile`.
- `frontend/src/lib/api.ts` — `getHomeOSCaseFile` accepts optional `caseId`.
- `frontend/src/components/AgentChip.tsx` — **new**: source → label/colour chip.
- `frontend/src/components/AgentTraceSection.tsx` — **new**: collapsed per-agent expanders with tool calls.
- `frontend/src/components/HomeOSDetailPanel.tsx` — render chips, pass `caseId`, label questions, render trace.

**Tests:**
- `backend/tests/test_homeos_commute_bus_tools.py` — update watchout assertions to `w["text"]`.
- `backend/tests/test_homeos_scoring_attribution.py` — **new**.
- `backend/tests/test_homeos_case_assembler.py` — **new**.
- `backend/tests/test_homeos_case_file_api.py` — **new**.
- `frontend/src/components/HomeOSDetailPanel.test.tsx` — update to `EvidenceItem[]`.
- `frontend/src/components/AgentChip.test.tsx` — **new**.
- `frontend/src/components/AgentTraceSection.test.tsx` — **new**.

**Commands:**
- Backend tests: `cd backend && .venv/bin/pytest <path> -v`
- Frontend tests: `cd frontend && npx vitest run <path>`

---

## Task 1: Attribute reasons/watchouts in `worth_viewing_score`

**Files:**
- Modify: `backend/app/homeos/scoring.py:20-79`
- Test: `backend/tests/test_homeos_scoring_attribution.py` (create)
- Modify (fix existing): `backend/tests/test_homeos_commute_bus_tools.py:238-248`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_homeos_scoring_attribution.py`:

```python
import unittest

from app.homeos.scoring import worth_viewing_score, item_texts

_MARKET_WITHIN = {"budget_signal": "within_budget", "transaction_count": 6}
_LOCATION_MRT = {"connections": [{"type": "mrt", "signal": "strong"}]}
_RISK = {"watchouts": ["Lease decay risk noted."], "score_adjustment": 0.0}


class TestScoringAttribution(unittest.TestCase):
    def test_reasons_and_watchouts_are_attributed_items(self):
        score, reasons, watchouts = worth_viewing_score(
            _MARKET_WITHIN, _LOCATION_MRT, _RISK, {}
        )
        # every item is a {text, source} dict
        for item in reasons + watchouts:
            self.assertIn("text", item)
            self.assertIn("source", item)
            self.assertIn(item["source"], {"market", "location", "risk"})

    def test_budget_reason_from_market(self):
        _, reasons, _ = worth_viewing_score(_MARKET_WITHIN, _LOCATION_MRT, _RISK, {})
        budget = next(r for r in reasons if "budget" in r["text"].lower())
        self.assertEqual(budget["source"], "market")

    def test_mrt_reason_from_location(self):
        _, reasons, _ = worth_viewing_score(_MARKET_WITHIN, _LOCATION_MRT, _RISK, {})
        mrt = next(r for r in reasons if "MRT" in r["text"])
        self.assertEqual(mrt["source"], "location")

    def test_seed_watchout_from_risk(self):
        _, _, watchouts = worth_viewing_score(_MARKET_WITHIN, _LOCATION_MRT, _RISK, {})
        seeded = next(w for w in watchouts if "Lease decay" in w["text"])
        self.assertEqual(seeded["source"], "risk")

    def test_item_texts_extracts_plain_strings(self):
        _, reasons, _ = worth_viewing_score(_MARKET_WITHIN, _LOCATION_MRT, _RISK, {})
        texts = item_texts(reasons)
        self.assertTrue(all(isinstance(t, str) for t in texts))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_homeos_scoring_attribution.py -v`
Expected: FAIL — `ImportError: cannot import name 'item_texts'` and/or items are plain strings.

- [ ] **Step 3: Implement attributed scoring**

In `backend/app/homeos/scoring.py`, add near the top (after imports):

```python
from typing import Any, Literal, TypedDict


class EvidenceItem(TypedDict):
    text: str
    source: Literal["market", "location", "risk"]


def _item(text: str, source: str) -> EvidenceItem:
    return {"text": text, "source": source}


def item_texts(items: list[EvidenceItem]) -> list[str]:
    """Extract plain-text strings from attributed evidence items."""
    return [it["text"] for it in items]
```

Change the signature and body of `worth_viewing_score`. Replace `scoring.py:20-79` so that:
- the seed becomes `watchouts: list[EvidenceItem] = [_item(w, "risk") for w in risk.get("watchouts", [])]`
- every `reasons.append("…")` becomes `reasons.append(_item("…", "market"|"location"))` per its branch
- every `watchouts.append("…")` becomes `watchouts.append(_item("…", "market"|"location"))` per its branch
- the return type is `tuple[float, list[EvidenceItem], list[EvidenceItem]]`

Full replacement:

```python
def worth_viewing_score(
    market: dict,
    location: dict,
    risk: dict,
    prefs: dict,
) -> tuple[float, list[EvidenceItem], list[EvidenceItem]]:
    score = 0.0
    reasons: list[EvidenceItem] = []
    watchouts: list[EvidenceItem] = [_item(w, "risk") for w in risk.get("watchouts", [])]

    if market.get("budget_signal") == "within_budget":
        score += 30
        reasons.append(_item("Recent comparable sales support the budget.", "market"))
    elif market.get("budget_signal") == "above_budget":
        score += 10
        watchouts.append(_item("Recent comparable sales are above the stated budget.", "market"))
    else:
        watchouts.append(_item("Price confidence is limited by sparse transaction evidence.", "market"))

    txn_count = market.get("transaction_count") or 0
    if txn_count >= 4:
        score += 20
        reasons.append(_item("Recent resale evidence is strong enough for comparison.", "market"))
    else:
        score += 8
        watchouts.append(_item("Recent resale evidence is limited.", "market"))

    for conn in location.get("connections", []):
        if conn["type"] == "mrt":
            if conn["signal"] == "strong":
                score += 18
                reasons.append(_item("MRT access fits the buyer profile.", "location"))
            elif conn["signal"] == "moderate":
                score += 11
                watchouts.append(_item("MRT access is moderate rather than excellent.", "location"))
            else:
                score += 4
                watchouts.append(_item("MRT access is weak for this profile.", "location"))
        if conn["type"] == "primary_school" and prefs.get("school_priority") == "high":
            if conn["signal"] == "strong":
                score += 18
                reasons.append(_item("Primary school access fits the family profile.", "location"))
            elif conn["signal"] == "moderate":
                score += 10
                reasons.append(_item("There is at least one primary school within 1km.", "location"))
            else:
                watchouts.append(_item("Primary school access is weak for this family profile.", "location"))

    commute = location.get("commute") or {}
    worst = commute.get("worst_commute_min")
    if commute.get("available") and worst is not None and worst > 60:
        resolved = [
            d for d in commute.get("destinations", [])
            if d.get("resolved") and d.get("travel_min") is not None
        ]
        if resolved:
            worst_dest = max(resolved, key=lambda d: d["travel_min"])
            watchouts.append(_item(
                f"Long commute to {worst_dest['name']} (~{worst_dest['travel_min']:.0f} min).",
                "location",
            ))

    score += risk.get("score_adjustment") or 0.0
    return round(max(0.0, min(score, 100.0)), 1), reasons[:4], watchouts[:4]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_homeos_scoring_attribution.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Fix the existing commute test that assumed strings**

In `backend/tests/test_homeos_commute_bus_tools.py`, update the three assertions at lines 238-248 to read `w["text"]`:

```python
        _, _, watchouts = worth_viewing_score(_MARKET, self._location(75.0), _RISK, {})
        self.assertTrue(any("Long commute to Raffles Place" in w["text"] for w in watchouts))

        _, _, watchouts = worth_viewing_score(_MARKET, self._location(60.0), _RISK, {})
        self.assertFalse(any("Long commute" in w["text"] for w in watchouts))

        _, _, watchouts = worth_viewing_score(
            _MARKET, self._location(75.0, available=False), _RISK, {}
        )
        self.assertFalse(any("Long commute" in w["text"] for w in watchouts))
```

(Match the exact surrounding call lines already in the file — only the `in w` → `in w["text"]` part changes.)

- [ ] **Step 6: Run the commute test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_homeos_commute_bus_tools.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/homeos/scoring.py backend/tests/test_homeos_scoring_attribution.py backend/tests/test_homeos_commute_bus_tools.py
git commit -m "feat(homeos): attribute reasons/watchouts to source agent in worth_viewing_score"
```

---

## Task 2: Extract deterministic `base_viewing_questions`

Needed so the assembler can produce questions without an LLM call (AI-mode `viewing_questions_agent` calls an LLM; the stream does not store questions).

**Files:**
- Modify: `backend/app/homeos/sync_agents.py:159-183`
- Test: `backend/tests/test_homeos_base_questions.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_homeos_base_questions.py`:

```python
import unittest

from app.homeos.sync_agents import base_viewing_questions


class TestBaseViewingQuestions(unittest.TestCase):
    def test_returns_base_questions_without_llm(self):
        qs = base_viewing_questions({"market": {}, "location": {}, "risk": {}})
        self.assertIn("Which floor range is the unit in?", qs)
        self.assertTrue(all(isinstance(q, str) for q in qs))

    def test_low_market_confidence_adds_question(self):
        qs = base_viewing_questions({"market": {"confidence": "low"}, "location": {}})
        self.assertTrue(any("limited recent resale evidence" in q for q in qs))

    def test_weak_connection_adds_question(self):
        qs = base_viewing_questions(
            {"market": {}, "location": {"connections": [{"signal": "weak"}]}}
        )
        self.assertTrue(any("realistic walking route" in q for q in qs))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_homeos_base_questions.py -v`
Expected: FAIL — `cannot import name 'base_viewing_questions'`.

- [ ] **Step 3: Implement the extraction**

In `backend/app/homeos/sync_agents.py`, add a new function and have `viewing_questions_agent` call it. Replace the body of `viewing_questions_agent` (lines 159-183) with:

```python
def base_viewing_questions(evidence: dict[str, Any]) -> list[str]:
    """Deterministic due-diligence questions — no LLM, no mock dependency."""
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
    if any(c.get("signal") == "weak" for c in location.get("connections", [])):
        questions.append("What is the realistic walking route and time to the nearest MRT or school?")
    return questions


def viewing_questions_agent(evidence: dict[str, Any]) -> list[str]:
    base_questions = base_viewing_questions(evidence)
    if is_mock_mode():
        extra = [q for q in mock_questions(evidence) if q and q not in base_questions]
    else:
        _, _, questions_agent, _ = _get_ai_agents()
        market = evidence.get("market", {})
        location = evidence.get("location", {})
        prompt = (
            f"market_confidence={market.get('confidence')}, "
            f"connections={location.get('connections', [])}, "
            f"watchouts={evidence.get('risk', {}).get('watchouts', [])}"
        )
        result = asyncio.run(questions_agent.run(prompt))
        extra = [q for q in result.output.questions if q and q not in base_questions]
    return (base_questions + extra)[:6]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_homeos_base_questions.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/homeos/sync_agents.py backend/tests/test_homeos_base_questions.py
git commit -m "refactor(homeos): extract deterministic base_viewing_questions"
```

---

## Task 3: Keep recompute path's `evidence.risks` as strings + add empty `trace`

`build_homeos_case_file` currently sets `evidence.risks = watchouts`; now that watchouts are items, coerce to strings and add an empty `trace` so the recompute fallback matches the assembler's shape.

**Files:**
- Modify: `backend/app/homeos/pipeline.py:940-963`
- Test: `backend/tests/test_homeos_case_file_shape.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_homeos_case_file_shape.py`:

```python
import unittest

from app.data.seed import seed_repository  # in-memory seeded repo helper
from app.homeos.pipeline import build_homeos_case_file


class TestCaseFileShape(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = seed_repository()
        cls.block_id = cls.repo.blocks()[0].block_id

    def test_risks_are_strings_and_trace_present(self):
        cf = build_homeos_case_file(
            self.repo, "family with kids budget 500k near mrt", self.block_id
        )
        self.assertTrue(all(isinstance(r, str) for r in cf["evidence"]["risks"]))
        self.assertIn("trace", cf)
        self.assertEqual(cf["trace"], [])
        # reasons/watchouts are attributed items
        for item in cf["top_reasons"] + cf["top_watchouts"]:
            self.assertIn("source", item)


if __name__ == "__main__":
    unittest.main()
```

> If `app.data.seed.seed_repository` is not the correct in-memory repo factory, replace the import with the project's standard test repo fixture (check `backend/tests/fixtures/` and how `test_homeos_commute_bus_tools.py` builds a repo). The assertions are unchanged.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_homeos_case_file_shape.py -v`
Expected: FAIL — `KeyError: 'trace'` (and/or risks are dicts).

- [ ] **Step 3: Implement the shape fix**

In `backend/app/homeos/pipeline.py`, update the import at line 23 and the `build_homeos_case_file` return. Change the import:

```python
from app.homeos.scoring import worth_viewing_score, _verdict, _confidence, item_texts
```

In the returned dict (`pipeline.py:943-963`), change `evidence.risks` and add `trace`:

```python
        "evidence": {
            "recent_sales": market,
            "connections": location["connections"],
            "risks": item_texts(watchouts),
            "future_signals": {
                "future_mrt": risk["future_mrt"],
                "future_supply": risk["future_supply"],
            },
            "agent_questions": questions,
        },
        "trace": [],
    }
```

(Add `"trace": []` as a top-level key of the returned dict, alongside `"evidence"`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_homeos_case_file_shape.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/homeos/pipeline.py backend/tests/test_homeos_case_file_shape.py
git commit -m "feat(homeos): recompute case file keeps string risks and empty trace"
```

---

## Task 4: `assemble_case_file_from_case`

**Files:**
- Create: `backend/app/homeos/case_assembler.py`
- Test: `backend/tests/test_homeos_case_assembler.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_homeos_case_assembler.py`:

```python
import unittest

from app.homeos import case_store
from app.homeos.case_assembler import assemble_case_file_from_case


def _seed_case() -> str:
    case = case_store.create_case("family with kids budget 500k near mrt")
    cid = case["case_id"]
    bid = 812
    case_store.append_event(cid, {
        "event": "agent_data", "agent": "market", "block_id": bid,
        "data": {"transaction_count": 8, "median_price": 397500.0,
                 "median_psf": 416.0, "window_months": 6,
                 "summary": "8 sales support price confidence.",
                 "narrative": "8 sales support price confidence.",
                 "confidence": "high"},
    })
    case_store.append_event(cid, {
        "event": "tool_calls", "agent": "market", "block_id": bid,
        "tool_calls": [{"tool_name": "recent_transactions",
                        "args": {"block_id": bid}, "result": {"count": 8}}],
    })
    case_store.append_event(cid, {
        "event": "agent_summary", "agent": "market", "block_id": bid,
        "narrative": "Market looks solid.",
    })
    case_store.append_event(cid, {
        "event": "agent_data", "agent": "location", "block_id": bid,
        "data": {"connections": [{"type": "mrt", "signal": "moderate"}]},
    })
    case_store.append_event(cid, {
        "event": "agent_data", "agent": "risk", "block_id": bid,
        "data": {"future_mrt": None, "future_supply": "1 BTO in 2027",
                 "watchouts": ["One BTO in 2027 may soften resale."]},
    })
    case_store.set_shortlist(cid, [{
        "block_id": bid, "block_number": "8", "street_name": "MARSILING DR",
        "town": "WOODLANDS", "worth_viewing_score": 53.8, "verdict": "Maybe view",
        "confidence": "high",
        "top_reasons": [{"text": "Recent comparable sales support the budget.", "source": "market"}],
        "top_watchouts": [{"text": "One BTO in 2027 may soften resale.", "source": "risk"}],
    }])
    return cid, bid


class TestCaseAssembler(unittest.TestCase):
    def test_assembles_case_file_from_stored_events(self):
        cid, bid = _seed_case()
        cf = assemble_case_file_from_case(cid, bid)
        self.assertIsNotNone(cf)
        self.assertEqual(cf["block_id"], bid)
        self.assertEqual(cf["verdict"], "Maybe view")
        self.assertEqual(cf["worth_viewing_score"], 53.8)
        self.assertEqual(cf["top_reasons"][0]["source"], "market")
        self.assertEqual(cf["evidence"]["recent_sales"]["transaction_count"], 8)
        self.assertEqual(cf["evidence"]["recent_sales"]["summary"],
                         "8 sales support price confidence.")
        self.assertTrue(all(isinstance(r, str) for r in cf["evidence"]["risks"]))
        self.assertTrue(len(cf["evidence"]["agent_questions"]) > 0)

    def test_trace_contains_tool_calls(self):
        cid, bid = _seed_case()
        cf = assemble_case_file_from_case(cid, bid)
        market_trace = next(t for t in cf["trace"] if t["agent"] == "market")
        self.assertEqual(market_trace["tool_calls"][0]["tool_name"], "recent_transactions")
        self.assertEqual(market_trace["narrative"], "Market looks solid.")

    def test_returns_none_for_unknown_case(self):
        self.assertIsNone(assemble_case_file_from_case("no-such-case", 1))

    def test_returns_none_for_block_not_in_case(self):
        cid, _ = _seed_case()
        self.assertIsNone(assemble_case_file_from_case(cid, 999999))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_homeos_case_assembler.py -v`
Expected: FAIL — `ModuleNotFoundError: app.homeos.case_assembler`.

- [ ] **Step 3: Implement the assembler**

Create `backend/app/homeos/case_assembler.py`:

```python
"""Assemble a case-file response from already-stored case events (no recompute)."""
from typing import Any

from app.homeos import case_store
from app.homeos.scoring import item_texts
from app.homeos.sync_agents import base_viewing_questions

_AGENTS = ("market", "location", "risk")


def assemble_case_file_from_case(case_id: str, block_id: int) -> dict[str, Any] | None:
    case = case_store.get_case(case_id)
    if case is None:
        return None

    events = [e for e in case.get("pipeline", []) if e.get("block_id") == block_id]
    if not events:
        return None

    evidence_by_agent: dict[str, dict] = {}
    tool_calls_by_agent: dict[str, list] = {}
    narrative_by_agent: dict[str, str] = {}
    for e in events:
        agent = e.get("agent")
        if agent not in _AGENTS:
            continue
        if e.get("event") == "agent_data":
            evidence_by_agent[agent] = e.get("data", {})
        elif e.get("event") == "tool_calls":
            tool_calls_by_agent.setdefault(agent, []).extend(e.get("tool_calls", []))
        elif e.get("event") == "agent_summary":
            narrative_by_agent[agent] = e.get("narrative", "")

    market = evidence_by_agent.get("market")
    if market is None:
        return None  # block was never analysed in this case

    location = evidence_by_agent.get("location", {})
    risk = evidence_by_agent.get("risk", {})

    row = next((r for r in case.get("shortlist", []) if r["block_id"] == block_id), None)
    if row is None:
        return None

    watchouts = row.get("top_watchouts", [])
    questions = base_viewing_questions(
        {"market": market, "location": location, "risk": risk}
    )

    trace = [
        {
            "agent": agent,
            "narrative": narrative_by_agent.get(agent, ""),
            "tool_calls": tool_calls_by_agent.get(agent, []),
        }
        for agent in _AGENTS
        if agent in evidence_by_agent
    ]

    return {
        "block_id": block_id,
        "block_number": row["block_number"],
        "street_name": row["street_name"],
        "town": row["town"],
        "verdict": row["verdict"],
        "worth_viewing_score": row["worth_viewing_score"],
        "confidence": row["confidence"],
        "top_reasons": row.get("top_reasons", []),
        "top_watchouts": watchouts,
        "evidence": {
            "recent_sales": {
                "transaction_count": market.get("transaction_count", 0),
                "median_price": market.get("median_price"),
                "median_psf": market.get("median_psf"),
                "window_months": market.get("window_months", 6),
                "summary": market.get("summary") or market.get("narrative", ""),
            },
            "connections": location.get("connections", []),
            "risks": item_texts(watchouts),
            "future_signals": {
                "future_mrt": risk.get("future_mrt"),
                "future_supply": risk.get("future_supply"),
            },
            "agent_questions": questions,
        },
        "trace": trace,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_homeos_case_assembler.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/homeos/case_assembler.py backend/tests/test_homeos_case_assembler.py
git commit -m "feat(homeos): assemble case file from stored case events"
```

---

## Task 5: Endpoint — optional `case_id` with recompute fallback

**Files:**
- Modify: `backend/app/api/schemas.py:87-89`
- Modify: `backend/app/api/main.py:259-265`
- Test: `backend/tests/test_homeos_case_file_api.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_homeos_case_file_api.py`:

```python
import unittest

from fastapi.testclient import TestClient

from app.api.main import app
from app.homeos import case_store

client = TestClient(app)


class TestCaseFileApi(unittest.TestCase):
    def test_uses_assembler_when_case_id_present(self):
        case = case_store.create_case("family with kids budget 500k near mrt")
        cid = case["case_id"]
        bid = 4242
        case_store.append_event(cid, {
            "event": "agent_data", "agent": "market", "block_id": bid,
            "data": {"transaction_count": 5, "median_price": 400000.0,
                     "median_psf": 410.0, "window_months": 6, "summary": "ok"},
        })
        case_store.append_event(cid, {
            "event": "agent_data", "agent": "risk", "block_id": bid,
            "data": {"watchouts": []},
        })
        case_store.set_shortlist(cid, [{
            "block_id": bid, "block_number": "1", "street_name": "TEST ST",
            "town": "WOODLANDS", "worth_viewing_score": 50.0, "verdict": "Maybe view",
            "confidence": "medium", "top_reasons": [], "top_watchouts": [],
        }])
        resp = client.post(
            f"/homeos/case-file/{bid}",
            json={"profile_text": "family with kids budget 500k near mrt", "case_id": cid},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["block_id"], bid)
        self.assertIn("trace", body)
        self.assertEqual(body["evidence"]["recent_sales"]["transaction_count"], 5)

    def test_falls_back_to_recompute_when_block_not_in_case(self):
        case = case_store.create_case("family with kids budget 500k near mrt")
        cid = case["case_id"]
        # No events for this block -> assembler returns None -> recompute path runs.
        resp = client.post(
            "/homeos/case-file/999999",
            json={"profile_text": "family with kids budget 500k near mrt", "case_id": cid},
        )
        # recompute raises ValueError("block not found") -> 404
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_homeos_case_file_api.py -v`
Expected: FAIL — assembler not wired in; `case_id` rejected or ignored.

- [ ] **Step 3: Add `case_id` to the request schema**

In `backend/app/api/schemas.py`, update `HomeOSCaseFileRequest` (line 87):

```python
class HomeOSCaseFileRequest(BaseModel):
    profile_text: str = Field(..., min_length=10)
    case_id: str | None = None
```

- [ ] **Step 4: Wire the assembler into the endpoint**

In `backend/app/api/main.py`, add the import alongside the existing homeos imports (near line 42):

```python
from app.homeos.case_assembler import assemble_case_file_from_case
```

Replace the handler body (`main.py:259-265`):

```python
@app.post("/homeos/case-file/{block_id}")
def homeos_case_file(block_id: int, req: HomeOSCaseFileRequest,
                     repo: Repository = Depends(get_repository)):
    if req.case_id:
        assembled = assemble_case_file_from_case(req.case_id, block_id)
        if assembled is not None:
            return assembled
    try:
        return build_homeos_case_file(repo, req.profile_text, block_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_homeos_case_file_api.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Run the full homeos backend suite (regression guard)**

Run: `cd backend && .venv/bin/pytest tests/ -k homeos -v`
Expected: PASS (pre-existing unrelated failures, if any, noted in memory are NOT introduced by this change — confirm no NEW failures reference reasons/watchouts/case-file).

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/schemas.py backend/app/api/main.py backend/tests/test_homeos_case_file_api.py
git commit -m "feat(api): case-file endpoint reuses stored case via case_id with recompute fallback"
```

---

## Task 6: Frontend types

**Files:**
- Modify: `frontend/src/types.ts:273-313`

- [ ] **Step 1: Update the types**

In `frontend/src/types.ts`, add above `HomeOSShortlistRow` (line 273):

```ts
export type AgentSource = "market" | "location" | "risk";

export interface EvidenceItem {
  text: string;
  source: AgentSource;
}

export interface TraceToolCall {
  tool_name: string;
  args: unknown;
  result?: unknown;
}

export interface AgentTrace {
  agent: AgentSource;
  narrative: string;
  tool_calls: TraceToolCall[];
}
```

Change `top_reasons` / `top_watchouts` in `HomeOSShortlistRow` (lines 281-282):

```ts
  top_reasons: EvidenceItem[];
  top_watchouts: EvidenceItem[];
```

Change `top_reasons` / `top_watchouts` in `HomeOSCaseFile` (lines 298-299) and add `trace`:

```ts
  top_reasons: EvidenceItem[];
  top_watchouts: EvidenceItem[];
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
  trace?: AgentTrace[];
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: errors ONLY in `HomeOSDetailPanel.tsx` (consumers of the changed fields) — fixed in Task 8. No errors in `types.ts` itself.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types.ts
git commit -m "feat(types): attributed evidence items and agent trace"
```

---

## Task 7: API client passes `caseId`

**Files:**
- Modify: `frontend/src/lib/api.ts:225-232`

- [ ] **Step 1: Update `getHomeOSCaseFile`**

In `frontend/src/lib/api.ts`, replace lines 225-232:

```ts
export function getHomeOSCaseFile(
  blockId: number,
  profileText: string,
  caseId?: string,
): Promise<HomeOSCaseFile> {
  return postJSON<HomeOSCaseFile>(`/homeos/case-file/${blockId}`, {
    profile_text: profileText,
    ...(caseId ? { case_id: caseId } : {}),
  });
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors from this file.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(api-client): getHomeOSCaseFile forwards caseId"
```

---

## Task 8: Agent chips + per-line provenance in the detail panel

**Files:**
- Create: `frontend/src/components/AgentChip.tsx`
- Test: `frontend/src/components/AgentChip.test.tsx` (create)
- Modify: `frontend/src/components/HomeOSDetailPanel.tsx`
- Modify: `frontend/src/components/HomeOSDetailPanel.test.tsx:15-16,78-79`

- [ ] **Step 1: Write the failing chip test**

Create `frontend/src/components/AgentChip.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import AgentChip from "./AgentChip";

describe("AgentChip", () => {
  it("renders 'Market' for market source", () => {
    render(<AgentChip source="market" />);
    expect(screen.getByText("Market")).toBeInTheDocument();
  });

  it("renders 'Lifestyle' for location source", () => {
    render(<AgentChip source="location" />);
    expect(screen.getByText("Lifestyle")).toBeInTheDocument();
  });

  it("renders 'Risk' for risk source", () => {
    render(<AgentChip source="risk" />);
    expect(screen.getByText("Risk")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/AgentChip.test.tsx`
Expected: FAIL — cannot find module `./AgentChip`.

- [ ] **Step 3: Implement `AgentChip`**

Create `frontend/src/components/AgentChip.tsx`:

```tsx
import type { AgentSource } from "../types";

const LABELS: Record<AgentSource, string> = {
  market: "Market",
  location: "Lifestyle",
  risk: "Risk",
};

const COLORS: Record<AgentSource, string> = {
  market: "bg-emerald-100 text-emerald-700",
  location: "bg-sky-100 text-sky-700",
  risk: "bg-amber-100 text-amber-700",
};

export default function AgentChip({ source }: { source: AgentSource }) {
  return (
    <span
      className={`ml-1 inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${COLORS[source]}`}
    >
      {LABELS[source]}
    </span>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/AgentChip.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Render chips + pass `caseId` + label questions in the panel**

In `frontend/src/components/HomeOSDetailPanel.tsx`:

(a) Add import at the top:

```tsx
import AgentChip from "./AgentChip";
```

(b) Pass `caseId` to the fetch — update the `useEffect` call (line 34):

```tsx
    getHomeOSCaseFile(block.block_id, profileText, caseId)
```

(c) Render reasons with chips — replace the reasons block (lines 162-169):

```tsx
              {displayedReasons.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-emerald-700">Why it fits</p>
                  {displayedReasons.map((r) => (
                    <p key={r.text} className="text-xs text-muted-foreground">
                      ✓ {r.text}
                      <AgentChip source={r.source} />
                    </p>
                  ))}
                </div>
              )}
```

(d) Render watchouts with chips — replace the watchouts block (lines 171-178):

```tsx
              {displayedWatchouts.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-amber-600">Watchouts</p>
                  {displayedWatchouts.map((w) => (
                    <p key={w.text} className="text-xs text-muted-foreground">
                      ⚠ {w.text}
                      <AgentChip source={w.source} />
                    </p>
                  ))}
                </div>
              )}
```

(e) Label the questions section as synthesised — update the "Questions for agent" header (line 181-183):

```tsx
                <p className="text-xs font-medium text-muted-foreground mb-1">
                  Questions for agent
                  <span className="ml-1 text-[10px] font-normal text-muted-foreground/70">
                    · synthesised from all agents
                  </span>
                </p>
```

> Note: `displayedReasons`/`displayedWatchouts` (lines 76-77) are now `EvidenceItem[]`; `displayedVerdict`/`displayedScore` are unchanged. No other edits needed to those derivations.

- [ ] **Step 6: Update the existing panel test to use attributed items**

In `frontend/src/components/HomeOSDetailPanel.test.tsx`, update the mock data:

Line 15-16:
```tsx
    top_reasons: [{ text: "Recent comparable sales support the budget.", source: "market" }],
    top_watchouts: [],
```

Lines 78-79 (inside the `recommendation` object):
```tsx
          top_reasons: [{ text: "Matches the refined requirements.", source: "market" }],
          top_watchouts: [],
```

- [ ] **Step 7: Run the panel tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/HomeOSDetailPanel.test.tsx src/components/AgentChip.test.tsx`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/AgentChip.tsx frontend/src/components/AgentChip.test.tsx frontend/src/components/HomeOSDetailPanel.tsx frontend/src/components/HomeOSDetailPanel.test.tsx
git commit -m "feat(panel): per-line agent provenance chips and synthesised-questions label"
```

---

## Task 9: Agent trace section

**Files:**
- Create: `frontend/src/components/AgentTraceSection.tsx`
- Test: `frontend/src/components/AgentTraceSection.test.tsx` (create)
- Modify: `frontend/src/components/HomeOSDetailPanel.tsx`

- [ ] **Step 1: Write the failing trace test**

Create `frontend/src/components/AgentTraceSection.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import AgentTraceSection from "./AgentTraceSection";
import type { AgentTrace } from "../types";

const TRACE: AgentTrace[] = [
  {
    agent: "market",
    narrative: "Market looks solid.",
    tool_calls: [
      { tool_name: "recent_transactions", args: { block_id: 812 }, result: { count: 8 } },
    ],
  },
];

describe("AgentTraceSection", () => {
  it("renders nothing when trace is empty", () => {
    const { container } = render(<AgentTraceSection trace={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when trace is undefined", () => {
    const { container } = render(<AgentTraceSection trace={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows per-agent header and reveals tool calls on expand", () => {
    render(<AgentTraceSection trace={TRACE} />);
    // agent header visible (collapsed by default)
    expect(screen.getByText(/Market/)).toBeInTheDocument();
    // tool name hidden until expanded
    expect(screen.queryByText("recent_transactions")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(/Market/));
    expect(screen.getByText("recent_transactions")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/AgentTraceSection.test.tsx`
Expected: FAIL — cannot find module `./AgentTraceSection`.

- [ ] **Step 3: Implement `AgentTraceSection`**

Create `frontend/src/components/AgentTraceSection.tsx`:

```tsx
import { useState } from "react";
import type { AgentTrace, AgentSource, TraceToolCall } from "../types";

const LABELS: Record<AgentSource, string> = {
  market: "Market",
  location: "Lifestyle",
  risk: "Risk",
};

function summarize(result: unknown): string {
  if (result == null) return "—";
  if (Array.isArray(result)) return `${result.length} items`;
  if (typeof result === "object") {
    const keys = Object.keys(result as Record<string, unknown>);
    return keys.slice(0, 3).join(", ") || "{}";
  }
  return String(result);
}

function ToolCallRow({ call }: { call: TraceToolCall }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-t border-border/50 py-1">
      <p className="text-xs font-medium text-foreground">{call.tool_name}</p>
      <p className="text-[10px] text-muted-foreground break-all">
        args: {JSON.stringify(call.args)}
      </p>
      <button
        type="button"
        className="text-[10px] text-sky-700 hover:underline"
        onClick={() => setOpen((v) => !v)}
      >
        result: {summarize(call.result)} {open ? "▲" : "⤢"}
      </button>
      {open && (
        <pre className="mt-1 max-h-40 overflow-auto rounded bg-muted p-1 text-[10px] text-muted-foreground">
          {JSON.stringify(call.result, null, 2)}
        </pre>
      )}
    </div>
  );
}

function AgentTraceRow({ trace }: { trace: AgentTrace }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded border border-border">
      <button
        type="button"
        className="flex w-full items-center justify-between px-2 py-1 text-xs"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="font-medium text-foreground">
          {open ? "▾" : "▸"} {LABELS[trace.agent]}
        </span>
        <span className="text-[10px] text-muted-foreground">
          {trace.tool_calls.length} tools
        </span>
      </button>
      {open && (
        <div className="px-2 pb-2">
          {trace.tool_calls.map((c, i) => (
            <ToolCallRow key={`${c.tool_name}-${i}`} call={c} />
          ))}
          {trace.narrative && (
            <p className="mt-1 text-[10px] italic text-muted-foreground">
              {trace.narrative}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function AgentTraceSection({ trace }: { trace?: AgentTrace[] }) {
  const withCalls = (trace ?? []).filter((t) => t.tool_calls.length > 0);
  if (withCalls.length === 0) return null;
  return (
    <div className="p-4 border-b border-border space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Agent trace
      </p>
      {withCalls.map((t) => (
        <AgentTraceRow key={t.agent} trace={t} />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/AgentTraceSection.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Integrate into the panel**

In `frontend/src/components/HomeOSDetailPanel.tsx`:

(a) Add import:

```tsx
import AgentTraceSection from "./AgentTraceSection";
```

(b) Render it directly after the closing `</div>` of the HomeOS evidence block (after line 198, before the "Schedule viewing" block at line 201):

```tsx
      {profileText && caseFile && <AgentTraceSection trace={caseFile.trace} />}
```

- [ ] **Step 6: Type-check + run panel tests**

Run: `cd frontend && npx tsc --noEmit && npx vitest run src/components/HomeOSDetailPanel.test.tsx src/components/AgentTraceSection.test.tsx src/components/AgentChip.test.tsx`
Expected: PASS, no type errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/AgentTraceSection.tsx frontend/src/components/AgentTraceSection.test.tsx frontend/src/components/HomeOSDetailPanel.tsx
git commit -m "feat(panel): collapsible agent-trace section with tool calls"
```

---

## Task 10: Full regression + manual verification

**Files:** none (verification only)

- [ ] **Step 1: Backend — full homeos suite**

Run: `cd backend && .venv/bin/pytest tests/ -k homeos -v`
Expected: no NEW failures introduced by this change.

- [ ] **Step 2: Frontend — full suite + type-check**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: PASS.

- [ ] **Step 3: Manual check (AI mode)**

Start servers (`backend`: `.venv/bin/python -m app.run_server`; `frontend`: `npm run dev`). Run an AI-mode investigation, click a recommendation:
- Detail panel opens **without the multi-second delay**.
- Reasons/watchouts show **Market / Lifestyle / Risk** chips.
- **Agent trace** section appears with collapsible per-agent tool calls; expanding a result shows raw JSON.
- Questions show the "· synthesised from all agents" label.

- [ ] **Step 4: Manual check (mock mode)**

Run a mock-mode investigation, click a recommendation:
- Opens instantly, chips render.
- **Agent trace section is absent** (no tool calls recorded).

- [ ] **Step 5: Commit (if any verification tweaks were needed)**

```bash
git add -A
git commit -m "test(homeos): verify instant case detail across AI and mock modes"
```

---

## Self-Review

- **Spec coverage:** instant load (Tasks 4-5), no-LLM questions (Task 2), per-line provenance with Market/Lifestyle/Risk labels (Tasks 1, 6, 8), questions unchipped + labelled (Task 8), agent trace collapsed + summarised-with-expand + hidden in mock (Task 9), recompute fallback (Tasks 3, 5), graceful mock-mode degradation (Task 9 + Task 10 Step 4). All covered.
- **Placeholder scan:** every code step shows full code; the only conditional is Task 3 Step 1's repo-fixture note, which gives a concrete alternative path. No TBD/TODO.
- **Type consistency:** `EvidenceItem {text, source}`, `AgentSource`, `AgentTrace {agent, narrative, tool_calls}`, `TraceToolCall {tool_name, args, result?}` are defined once (Task 6) and used identically in Tasks 8-9; backend `EvidenceItem`/`item_texts`/`base_viewing_questions`/`assemble_case_file_from_case` names match across Tasks 1-5.
```
