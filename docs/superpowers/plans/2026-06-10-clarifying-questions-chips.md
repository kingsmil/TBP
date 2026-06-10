# Clarifying Questions: One-at-a-Time + Quick-Reply Chips — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the multi-bullet `_preference_review` wall-of-text with one question per turn, and add inline quick-reply chips to the chat UI so users can answer with one tap.

**Architecture:** Backend `_preference_review` returns the first unanswered `PrefDimension` question each call (instead of all missing dims as bullets). The frontend detects the active question's `field` and renders tappable chips; chip clicks call `onRefine(value)` like typed answers. The existing refine loop already handles multi-turn questions — no loop changes needed.

**Tech Stack:** Python (dataclasses, asyncio), React + TypeScript, Tailwind CSS.

---

## File Map

| File | Change |
|---|---|
| `backend/app/homeos/framework/spec.py` | Add `question: str = ""` to `PrefDimension` |
| `backend/app/homeos/tools/proximity.py` | Add `question=` to `commute_priority` and `school_priority` dims |
| `backend/app/homeos/tools/search.py` | Add `question=` to `flat_type`, `max_price`, `town` dims |
| `backend/app/homeos/tools/commute.py` | Add `question=` to `work_locations` dim |
| `backend/app/homeos/tools/bus_routes.py` | Add `question=` to `bus_reliance` dim |
| `backend/app/homeos/agents/risk.py` | Add `question=` to `risk_tolerance` dim |
| `backend/app/homeos/pipeline.py` | Refactor `_preference_review` — one question at a time |
| `backend/tests/test_preference_review.py` | Replace old tests with new behaviour tests |
| `backend/tests/test_homeos_stream.py` | Update 3 tests that check `field == "preference_review"` |
| `backend/tests/e2e/test_preference_review_live.py` | Update live test for one-at-a-time behaviour |
| `frontend/src/types.ts` | Add `field?: string` to `AgentEvent` |
| `frontend/src/components/CasesPanel.tsx` | `ChatMessage.field`, `buildChatHistory`, `CHIP_OPTIONS`, chips render |

---

## Task 1: Add `question` field to `PrefDimension`

**Files:**
- Modify: `backend/app/homeos/framework/spec.py:20-23`
- Test: `backend/tests/test_preference_review.py`

- [ ] **Step 1: Write a failing test for `PrefDimension.question`**

Add to the bottom of `TestCatalogueDimensions` in `backend/tests/test_preference_review.py`:

```python
def test_pref_dimension_has_question_field(self):
    from app.homeos.framework.spec import PrefDimension
    # with explicit question
    d = PrefDimension(field="x", prompt="p", question="Is this right?")
    self.assertEqual(d.question, "Is this right?")
    # default is empty string
    d2 = PrefDimension(field="x", prompt="p")
    self.assertEqual(d2.question, "")
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd backend && .venv/bin/python -m pytest tests/test_preference_review.py::TestCatalogueDimensions::test_pref_dimension_has_question_field -v
```

Expected: `FAILED` with `TypeError: PrefDimension.__init__() got an unexpected keyword argument 'question'`

- [ ] **Step 3: Add `question: str = ""` to `PrefDimension`**

In `backend/app/homeos/framework/spec.py`, replace:
```python
    field: str
    prompt: str
    query_key: str | None = None
    default: Any | None = None
```
with:
```python
    field: str
    prompt: str
    question: str = ""
    query_key: str | None = None
    default: Any | None = None
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
cd backend && .venv/bin/python -m pytest tests/test_preference_review.py::TestCatalogueDimensions::test_pref_dimension_has_question_field -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/app/homeos/framework/spec.py backend/tests/test_preference_review.py
git commit -m "feat(homeos): add question field to PrefDimension"
```

---

## Task 2: Populate `question=` on all 8 `PrefDimension` instances

**Files:**
- Modify: `backend/app/homeos/tools/proximity.py:40-45`
- Modify: `backend/app/homeos/tools/search.py:108-116`
- Modify: `backend/app/homeos/tools/commute.py:59-63`
- Modify: `backend/app/homeos/tools/bus_routes.py:46-50`
- Modify: `backend/app/homeos/agents/risk.py:21-23`
- Test: `backend/tests/test_preference_review.py`

- [ ] **Step 1: Write a failing test asserting all dims have non-empty `question`**

Add to `TestCatalogueDimensions` in `backend/tests/test_preference_review.py`:

```python
def test_all_dims_have_question_strings(self):
    dims = {d.field: d for d in self.tr.review_dimensions()}
    for field, dim in dims.items():
        self.assertNotEqual(
            dim.question, "",
            f"PrefDimension '{field}' has no question string — add question= to its declaration",
        )
```

- [ ] **Step 2: Run to confirm it fails**

```bash
cd backend && .venv/bin/python -m pytest tests/test_preference_review.py::TestCatalogueDimensions::test_all_dims_have_question_strings -v
```

Expected: `FAILED` listing dims with empty question strings.

- [ ] **Step 3: Add `question=` to `proximity.py`**

In `backend/app/homeos/tools/proximity.py`, replace the `activating_prefs` block:
```python
        activating_prefs=[
            PrefDimension(field="commute_priority",
                          prompt="MRT importance (high = within 600 m, medium = within 1.2 km)",
                          query_key="max_mrt_distance_m"),
            PrefDimension(field="school_priority",
                          prompt="Primary schools nearby (high = 2+ within 1 km, medium = 1+)",
                          query_key="min_schools_within_1km"),
        ],
```
with:
```python
        activating_prefs=[
            PrefDimension(field="commute_priority",
                          prompt="MRT importance (high = within 600 m, medium = within 1.2 km)",
                          question="How important is being close to an MRT? (High = within 600 m, Medium = within 1.2 km)",
                          query_key="max_mrt_distance_m"),
            PrefDimension(field="school_priority",
                          prompt="Primary schools nearby (high = 2+ within 1 km, medium = 1+)",
                          question="Do you need primary schools nearby? (High = 2+ within 1 km, Medium = 1+)",
                          query_key="min_schools_within_1km"),
        ],
```

- [ ] **Step 4: Add `question=` to `search.py`**

In `backend/app/homeos/tools/search.py`, replace the `activating_prefs` block:
```python
        activating_prefs=[
            PrefDimension(field="flat_type",
                          prompt="Flat type (2/3/4/5-room or Executive)",
                          query_key="flat_type"),
            PrefDimension(field="max_price",
                          prompt="Your budget ceiling — drives the budget-fit verdict",
                          query_key="max_price"),
            PrefDimension(field="town",
                          prompt="A preferred town or estate (optional)",
                          query_key="town"),
        ],
```
with:
```python
        activating_prefs=[
            PrefDimension(field="flat_type",
                          prompt="Flat type (2/3/4/5-room or Executive)",
                          question="What type of flat are you looking for? (2-room, 3-room, 4-room, 5-room, or Executive)",
                          query_key="flat_type"),
            PrefDimension(field="max_price",
                          prompt="Your budget ceiling — drives the budget-fit verdict",
                          question="What is your maximum budget? (e.g. $500k, $700k, $1M)",
                          query_key="max_price"),
            PrefDimension(field="town",
                          prompt="A preferred town or estate (optional)",
                          question="Is there a town or estate you prefer? (e.g. Tampines, Bishan, Toa Payoh)",
                          query_key="town"),
        ],
```

- [ ] **Step 5: Add `question=` to `commute.py`**

In `backend/app/homeos/tools/commute.py`, replace:
```python
        activating_prefs=[PrefDimension(
            field="work_locations",
            prompt="Where do you (and your partner) work? - unlocks commute analysis",
            default=[],
        )],
```
with:
```python
        activating_prefs=[PrefDimension(
            field="work_locations",
            prompt="Where do you (and your partner) work? - unlocks commute analysis",
            question="Where do you (and your partner) work? — unlocks commute-time analysis",
            default=[],
        )],
```

- [ ] **Step 6: Add `question=` to `bus_routes.py`**

In `backend/app/homeos/tools/bus_routes.py`, replace:
```python
        activating_prefs=[PrefDimension(
            field="bus_reliance",
            prompt="Do you rely on buses / no car? - unlocks bus network analysis",
            default="low",
        )],
```
with:
```python
        activating_prefs=[PrefDimension(
            field="bus_reliance",
            prompt="Do you rely on buses / no car? - unlocks bus network analysis",
            question="Do you rely on buses, or do you have a car? — unlocks bus network analysis",
            default="low",
        )],
```

- [ ] **Step 7: Add `question=` to `agents/risk.py`**

In `backend/app/homeos/agents/risk.py`, replace:
```python
        PrefDimension(field="risk_tolerance",
                      prompt="Risk tolerance (low = penalise high-risk blocks harder)",
                      default="low"),
```
with:
```python
        PrefDimension(field="risk_tolerance",
                      prompt="Risk tolerance (low = penalise high-risk blocks harder)",
                      question="How comfortable are you with investment risk? (Low = penalise higher-risk blocks harder)",
                      default="low"),
```

- [ ] **Step 8: Run the test to confirm all dims now have question strings**

```bash
cd backend && .venv/bin/python -m pytest tests/test_preference_review.py::TestCatalogueDimensions -v
```

Expected: all `TestCatalogueDimensions` tests `PASSED`

- [ ] **Step 9: Commit**

```bash
git add backend/app/homeos/tools/proximity.py backend/app/homeos/tools/search.py \
        backend/app/homeos/tools/commute.py backend/app/homeos/tools/bus_routes.py \
        backend/app/homeos/agents/risk.py backend/tests/test_preference_review.py
git commit -m "feat(homeos): add question strings to all PrefDimension declarations"
```

---

## Task 3: Refactor `_preference_review` — one question at a time

**Files:**
- Modify: `backend/app/homeos/pipeline.py:491-534`
- Modify: `backend/tests/test_preference_review.py` (replace `TestPreferenceReview`)

- [ ] **Step 1: Replace `TestPreferenceReview` with new behaviour tests**

Replace the entire `TestPreferenceReview` class in `backend/tests/test_preference_review.py` with:

```python
class TestPreferenceReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.homeos.wiring import setup
        setup()

    def _review(self, query_dict, prefs, count=3, pipeline=None):
        from app.homeos.pipeline import _preference_review
        return _preference_review(query_dict, prefs, count, pipeline or [])

    def test_all_set_returns_none(self):
        query_dict = {
            "flat_type": "4 ROOM", "max_price": 400000.0, "town": "TAMPINES",
            "max_mrt_distance_m": 600.0, "min_schools_within_1km": 2,
        }
        q, field = self._review(
            query_dict,
            {"risk_tolerance": "medium", "work_locations": ["Raffles Place"], "bus_reliance": "high"},
        )
        self.assertIsNone(q)
        self.assertIsNone(field)

    def test_returns_one_question_with_specific_dim_field(self):
        q, field = self._review({"flat_type": "4 ROOM", "max_price": 400000.0}, {})
        # Returns a single question for one specific dim (not the old "preference_review" catch-all)
        self.assertIsNotNone(q)
        self.assertIsNotNone(field)
        self.assertNotEqual(field, "preference_review")
        self.assertIn(field, {"commute_priority", "school_priority", "town",
                               "work_locations", "bus_reliance", "risk_tolerance"})
        # No bullet list
        self.assertNotIn("•", q)
        self.assertNotIn("haven't told me", q)
        self.assertNotIn("Answer any of these", q)

    def test_question_uses_dim_question_string(self):
        # Only risk_tolerance missing
        query_dict = {
            "flat_type": "4 ROOM", "max_price": 400000.0, "town": "TAMPINES",
            "max_mrt_distance_m": 600.0, "min_schools_within_1km": 2,
        }
        q, field = self._review(
            query_dict,
            {"work_locations": ["Raffles Place"], "bus_reliance": "high"},
        )
        self.assertEqual(field, "risk_tolerance")
        self.assertIn("investment risk", q)

    def test_preamble_uses_count_low(self):
        query_dict = {
            "flat_type": "4 ROOM", "max_price": 400000.0, "town": "TAMPINES",
            "max_mrt_distance_m": 600.0, "min_schools_within_1km": 2,
        }
        q, _ = self._review(query_dict, {"work_locations": ["Raffles Place"], "bus_reliance": "high"}, count=3)
        self.assertIn("3 blocks", q)

    def test_preamble_uses_still_for_high_count(self):
        query_dict = {
            "flat_type": "4 ROOM", "max_price": 400000.0, "town": "TAMPINES",
            "max_mrt_distance_m": 600.0, "min_schools_within_1km": 2,
        }
        q, _ = self._review(query_dict, {"work_locations": ["Raffles Place"], "bus_reliance": "high"}, count=15)
        self.assertIn("15 options", q)

    def test_asked_dims_are_skipped(self):
        pipeline = [_q("commute_priority"), _q("school_priority"), _q("town")]
        q, field = self._review({"flat_type": "4 ROOM", "max_price": 400000.0}, {},
                                pipeline=pipeline)
        self.assertIsNotNone(q)
        self.assertNotEqual(field, "preference_review")
        self.assertIn(field, {"work_locations", "bus_reliance", "risk_tolerance"})

    def test_all_dims_asked_returns_none(self):
        all_fields = ["flat_type", "max_price", "town", "commute_priority",
                      "school_priority", "risk_tolerance", "work_locations", "bus_reliance"]
        pipeline = [_q(f) for f in all_fields]
        q, field = self._review({}, {}, pipeline=pipeline)
        self.assertIsNone(q)
        self.assertIsNone(field)

    def test_query_key_in_dict_skips_dim(self):
        # max_mrt_distance_m in query_dict → commute_priority skipped
        q, field = self._review(
            {"flat_type": "4 ROOM", "max_price": 400000.0, "max_mrt_distance_m": 600.0}, {}
        )
        self.assertNotEqual(field, "commute_priority")
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
cd backend && .venv/bin/python -m pytest tests/test_preference_review.py::TestPreferenceReview -v
```

Expected: most tests `FAILED` because the function still returns `"preference_review"` and multi-bullet text.

- [ ] **Step 3: Replace `_preference_review` in `pipeline.py`**

In `backend/app/homeos/pipeline.py`, replace the entire `_preference_review` function (lines 491–534):

```python
def _preference_review(
    query_dict: dict, prefs: dict, count: int, pipeline: list[dict] | None = None
) -> tuple[str | None, str | None]:
    """Ask one missing preference dimension at a time before deep analysis.

    Replaces the old multi-bullet consolidated gate. Each dimension tracks its
    own field in the pipeline asked-set, so no "preference_review" sentinel is needed.
    """
    from app.homeos.wiring import tool_repository

    asked: set[str] = {
        e["field"]
        for e in (pipeline or [])
        if e.get("event") == "clarifying_question" and e.get("field")
    }

    for dim in tool_repository.review_dimensions():
        if dim.field in asked:
            continue
        if dim.query_key is not None:
            if dim.query_key in query_dict:
                continue
        elif dim.default is not None:
            if prefs.get(dim.field, dim.default) != dim.default:
                continue

        q_text = dim.question or dim.prompt
        preamble = f"I've narrowed it to {count} blocks." if count <= 10 else f"Still {count} options."
        return (f"{preamble} {q_text}", dim.field)

    return (None, None)
```

- [ ] **Step 4: Run new tests to confirm they pass**

```bash
cd backend && .venv/bin/python -m pytest tests/test_preference_review.py::TestPreferenceReview -v
```

Expected: all `PASSED`

- [ ] **Step 5: Run full test_preference_review.py**

```bash
cd backend && .venv/bin/python -m pytest tests/test_preference_review.py -v
```

Expected: all `PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/app/homeos/pipeline.py backend/tests/test_preference_review.py
git commit -m "feat(homeos): refactor _preference_review to ask one dim at a time"
```

---

## Task 4: Update `test_homeos_stream.py` for new per-field behaviour

**Files:**
- Modify: `backend/tests/test_homeos_stream.py:100-136`

These 3 tests check `field == "preference_review"` which no longer exists.

- [ ] **Step 1: Replace the 3 affected tests**

In `backend/tests/test_homeos_stream.py`, replace lines 100–136:

```python
    def test_stream_asks_pref_dims_before_analysis(self):
        events = self._collect_stream("Family 4 room 800k schools.", limit=1)
        q_events = [e for e in events if e["event"] == "clarifying_question"]
        self.assertTrue(q_events, "expected at least one clarifying question before deep analysis")
        for q in q_events:
            self.assertNotEqual(
                q.get("field"), "preference_review",
                "preference_review catch-all field must no longer be used",
            )
            self.assertIsNotNone(q.get("field"))
        last_q_idx = max(events.index(q) for q in q_events)
        deep_idx = [i for i, e in enumerate(events)
                    if e.get("agent") in ("market", "location", "risk")]
        if deep_idx:
            self.assertLess(last_q_idx, min(deep_idx))

    def test_fully_specified_profile_skips_set_dims(self):
        events = self._collect_stream(
            "4 room in TAMPINES max 800k near MRT 2 primary schools.", limit=1)
        q_fields = [e.get("field") for e in events if e["event"] == "clarifying_question"]
        self.assertNotIn("flat_type", q_fields)
        self.assertNotIn("max_price", q_fields)
        self.assertNotIn("town", q_fields)
        self.assertNotIn("commute_priority", q_fields)
        self.assertNotIn("school_priority", q_fields)

    def test_profile_with_work_and_no_car_skips_those_dims(self):
        events = self._collect_stream(
            "4 room in TAMPINES max 800k near MRT 2 primary schools. "
            "I work at Raffles Place and have no car.",
            limit=1,
        )
        q_fields = [e.get("field") for e in events if e["event"] == "clarifying_question"]
        self.assertNotIn("work_locations", q_fields)
        self.assertNotIn("bus_reliance", q_fields)
```

- [ ] **Step 2: Run the updated tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_homeos_stream.py -v
```

Expected: all `PASSED` (note: the 3 known baseline failures on main are `test_parse_family_profile` + others in `test_homeos_service.py`, not these tests)

- [ ] **Step 3: Run the full backend unit+integration suite**

```bash
cd backend && .venv/bin/python -m pytest tests/ -q --ignore=tests/e2e
```

Expected: passes (same baseline failure count as before this branch — `test_parse_family_profile` may still fail, that's pre-existing)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_homeos_stream.py
git commit -m "test(homeos): update stream tests for per-field clarifying question behaviour"
```

---

## Task 5: Update live E2E test for one-at-a-time behaviour

**Files:**
- Modify: `backend/tests/e2e/test_preference_review_live.py:54-67`

- [ ] **Step 1: Update the live preference review test**

In `backend/tests/e2e/test_preference_review_live.py`, replace lines 54–73:

```python
        # THE feature: questions fire one at a time with specific dim fields
        q_events = [e for e in events if e["event"] == "clarifying_question"]
        self.assertTrue(q_events, "expected at least one clarifying question before deep analysis")
        for q in q_events:
            self.assertNotEqual(
                q.get("field"), "preference_review",
                "preference_review catch-all field must no longer be used — got: "
                f"{[e.get('field') for e in events if e['event'] == 'clarifying_question']}",
            )
            self.assertIsNotNone(q.get("field"))
        last_q_idx = max(events.index(q) for q in q_events)
        deep_idx = [i for i, e in enumerate(events)
                    if e.get("agent") in ("market", "location", "risk")]
        self.assertTrue(deep_idx, "journey must reach deep analysis after answering questions")
        self.assertLess(last_q_idx, min(deep_idx))

        print(f"\n  clarifying questions asked: {[e.get('field') for e in q_events]}")
        print(f"  first question: {q_events[0]['question']}")
```

Also update the `run()` inner function to allow more rounds (dims can fire up to 8 questions):

Replace:
```python
            # answer at most 2 questions (review + safety margin), then expect done
            for _ in range(2):
```
with:
```python
            # answer each dim question with 'proceed' (up to 10 rounds)
            for _ in range(10):
```

- [ ] **Step 2: Commit**

```bash
git add backend/tests/e2e/test_preference_review_live.py
git commit -m "test(homeos): update live e2e test for one-at-a-time preference questions"
```

---

## Task 6: Frontend — add `field` to `AgentEvent` and `ChatMessage`

**Files:**
- Modify: `frontend/src/types.ts:344`
- Modify: `frontend/src/components/CasesPanel.tsx:5-8` (ChatMessage interface) and `CasesPanel.tsx:50-51` (buildChatHistory)

- [ ] **Step 1: Add `field?: string` to `AgentEvent` in `types.ts`**

In `frontend/src/types.ts`, replace:
```typescript
  question?: string;
}
```
with:
```typescript
  question?: string;
  field?: string;
}
```

- [ ] **Step 2: Add `field?: string` to `ChatMessage` interface in `CasesPanel.tsx`**

In `frontend/src/components/CasesPanel.tsx`, replace:
```typescript
interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  type?: "profile" | "search" | "question" | "result" | "chat";
}
```
with:
```typescript
interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  type?: "profile" | "search" | "question" | "result" | "chat";
  field?: string;
}
```

- [ ] **Step 3: Pass `field` in `buildChatHistory`**

In `frontend/src/components/CasesPanel.tsx`, in the `buildChatHistory` function, replace:
```typescript
      messages.push({ role: "assistant", content: e.question, type: "question" });
```
with:
```typescript
      messages.push({ role: "assistant", content: e.question, type: "question", field: e.field });
```

- [ ] **Step 4: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types.ts frontend/src/components/CasesPanel.tsx
git commit -m "feat(frontend): thread clarifying question field through ChatMessage"
```

---

## Task 7: Frontend — `CHIP_OPTIONS` constant and chip render

**Files:**
- Modify: `frontend/src/components/CasesPanel.tsx`

- [ ] **Step 1: Add `CHIP_OPTIONS` constant above the component**

In `frontend/src/components/CasesPanel.tsx`, add this block immediately before `const DEFAULT_PROFILE =` (line 139):

```typescript
const CHIP_OPTIONS: Record<string, { label: string; value: string }[]> = {
  commute_priority: [
    { label: "High (<600 m)", value: "high" },
    { label: "Medium (<1.2 km)", value: "medium" },
    { label: "Not important", value: "not important" },
  ],
  school_priority: [
    { label: "2+ schools", value: "high" },
    { label: "1+ school", value: "medium" },
    { label: "Not needed", value: "not important" },
  ],
  risk_tolerance: [
    { label: "Low risk", value: "low" },
    { label: "Medium", value: "medium" },
    { label: "High risk ok", value: "high" },
  ],
  bus_reliance: [
    { label: "Yes, no car", value: "high" },
    { label: "Have a car", value: "low" },
  ],
  flat_type: [
    { label: "2-room", value: "2 room" },
    { label: "3-room", value: "3 room" },
    { label: "4-room", value: "4 room" },
    { label: "5-room", value: "5 room" },
    { label: "Executive", value: "executive" },
  ],
};
```

- [ ] **Step 2: Derive `activeChips` from `chatHistory` and `isRefining`**

In the `CasesPanel` component body, add these two lines after the `chatHistory` const is computed (after line ~181):

```typescript
  const lastQuestion = isRefining
    ? [...chatHistory].reverse().find((m) => m.type === "question")
    : null;
  const activeChips = lastQuestion?.field ? (CHIP_OPTIONS[lastQuestion.field] ?? null) : null;
```

- [ ] **Step 3: Render chips in the chat scroll area**

In `frontend/src/components/CasesPanel.tsx`, in the chat history `<div className="space-y-2">` block, add the chips render immediately after the `{chatHistory.map(...)}` block and before the `{isRunning && ...}` spinner. Replace:

```tsx
          <div className="space-y-2">
            {chatHistory.map((msg, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: stable chat order
              <ChatBubble key={i} msg={msg} />
            ))}
            {isRunning && (
```

with:

```tsx
          <div className="space-y-2">
            {chatHistory.map((msg, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: stable chat order
              <ChatBubble key={i} msg={msg} />
            ))}
            {activeChips && (
              <div className="flex flex-wrap gap-1.5 px-1 pb-1">
                {activeChips.map((chip) => (
                  <button
                    key={chip.value}
                    type="button"
                    onClick={() => { onRefine(chip.value); }}
                    className="rounded-full border border-border bg-background px-3 py-1 text-xs hover:bg-muted"
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            )}
            {isRunning && (
```

- [ ] **Step 4: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 5: Run the app and test manually**

```bash
# Terminal 1 — backend
cd backend && HOMEOS_AGENT_MODE=mock .venv/bin/python -m uvicorn app.api.main:app --reload --port 8010

# Terminal 2 — frontend
cd frontend && npm run dev
```

Open http://localhost:5173. Type "I want a 4 room flat under $400k". Verify:
- HomeOS asks one question at a time (not a bullet wall)
- For `commute_priority`, `school_priority`, `bus_reliance`, `risk_tolerance`, `flat_type` — chips appear below the question
- Clicking a chip submits the answer and the next question appears with new chips
- For `work_locations` and `town` — no chips, input field is used
- After all questions are answered (or "proceed" typed), deep analysis runs

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/CasesPanel.tsx
git commit -m "feat(frontend): add quick-reply chips for clarifying question fields"
```
