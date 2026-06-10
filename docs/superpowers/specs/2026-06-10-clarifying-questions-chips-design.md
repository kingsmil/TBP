# Clarifying Questions: One-at-a-Time + Quick-Reply Chips

**Date:** 2026-06-10  
**Status:** Approved

## Problem

The `_preference_review` gate in `pipeline.py` asks ALL missing preferences in a single message as a bullet-point wall (up to 6 bullets). This is overwhelming and requires the user to type a long free-form answer covering multiple dimensions.

The existing `_clarifying_question` function already asks ONE question at a time. `_preference_review` should follow the same pattern.

## Solution

1. **Backend:** Refactor `_preference_review` to return ONE question per call (first missing dimension), using a `question` field on `PrefDimension`. Remove the `"preference_review"` catch-all field — each dim tracks itself.

2. **Frontend:** Add inline quick-reply chips below the last unanswered clarifying question. Per-field chip options let users answer with one tap instead of typing.

## Backend Changes

### `framework/spec.py` — Add `question` field to `PrefDimension`

```python
@dataclass
class PrefDimension:
    field: str
    prompt: str          # kept for backwards-compat (used nowhere after this change)
    question: str = ""   # full question string for _preference_review to emit
    query_key: str | None = None
    default: Any | None = None
```

`question` is optional with empty-string default so existing callers that don't set it don't break. `_preference_review` falls back to `prompt` when `question` is empty.

### Tool/agent files — Populate `question=` on each `PrefDimension`

| File | Field | `question` string |
|---|---|---|
| `tools/proximity.py` | `commute_priority` | `"How important is being close to an MRT? (High = within 600 m, Medium = within 1.2 km)"` |
| `tools/proximity.py` | `school_priority` | `"Do you need primary schools nearby? (High = 2+ within 1 km, Medium = 1+)"` |
| `tools/search.py` | `flat_type` | `"What type of flat are you looking for? (2-room, 3-room, 4-room, 5-room, or Executive)"` |
| `tools/search.py` | `max_price` | `"What is your maximum budget? (e.g. $500k, $700k, $1M)"` |
| `tools/search.py` | `town` | `"Is there a town or estate you prefer? (e.g. Tampines, Bishan, Toa Payoh)"` |
| `tools/commute.py` | `work_locations` | `"Where do you (and your partner) work? — unlocks commute-time analysis"` |
| `tools/bus_routes.py` | `bus_reliance` | `"Do you rely on buses, or do you have a car? — unlocks bus network analysis"` |
| `agents/risk.py` | `risk_tolerance` | `"How comfortable are you with investment risk? (Low = penalise higher-risk blocks harder)"` |

### `pipeline.py` — Refactor `_preference_review`

**Current behaviour:** Collects all missing dims into `bullets`, builds one big message, returns `(question, "preference_review")`.

**New behaviour:** Find first missing dim → return `(formatted_question, dim.field)`. Return `(None, None)` when no dims are missing.

```python
def _preference_review(query_dict, prefs, count, pipeline=None):
    asked = {e["field"] for e in (pipeline or []) if e.get("event") == "clarifying_question" and e.get("field")}
    # NOTE: "preference_review" guard removed — per-field tracking handles dedup

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
        question = f"{preamble} {q_text}"
        return (question, dim.field)

    return (None, None)
```

The existing refine loop in `investigate_stream` and `refine_stream` already calls `_preference_review` once per turn and loops back if the user answers — no loop changes needed.

## Frontend Changes

### `types.ts` — Add `field` to `clarifying_question` event

The `AgentEvent` union type for `clarifying_question` events must include `field?: string`. Confirm this is present; add if missing.

### `CasesPanel.tsx` — `ChatMessage` interface

Add `field?: string` to the `ChatMessage` interface.

### `CasesPanel.tsx` — `buildChatHistory`

When creating a `question` ChatMessage from a `clarifying_question` event, pass `field: e.field`.

```ts
messages.push({ role: "assistant", content: e.question, type: "question", field: e.field });
```

### `CasesPanel.tsx` — `CHIP_OPTIONS` constant

Define above the component:

```ts
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
// Fields not listed here (work_locations, town, max_price, open_ended) → no chips, user types
```

### `CasesPanel.tsx` — Render chips

Determine the last unanswered question using `isRefining` and `chatHistory`:

```ts
const lastQuestion = isRefining
  ? [...chatHistory].reverse().find((m) => m.type === "question")
  : null;
const activeChips = lastQuestion?.field ? CHIP_OPTIONS[lastQuestion.field] ?? null : null;
```

Render chips in the chat scroll area, after the messages list and before `isRunning` spinner. Chip click calls `onRefine(chip.value)`:

```tsx
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
```

Chips appear below the last question bubble and disappear once the user answers (status leaves `"refining"`).

## Out of Scope

- Changing `_clarifying_question` — it already asks one at a time and has its own question strings.
- Changing how answers are parsed — the profile LLM handles natural-language answers; chip values are natural-language strings ("high", "not important").
- Adding a "Proceed" chip — user can type "proceed" to skip remaining questions.
- Changing chip styling beyond what matches the existing design system.

## Test Impact

- The `test_homeos_stream` clarifying-question integration tests will need updating: the 3 known baseline failures on `main` test the OLD multi-bullet `_preference_review` message format — they should be updated to expect one question at a time.
- No new test files needed; existing integration test structure covers this.
