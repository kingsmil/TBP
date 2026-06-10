# Investigate Stream Live E2E — Design

**Date:** 2026-06-10
**Status:** Approved (brainstormed with user)
**Depends on:** PR #4 (ToolRepository catalogue, `tests/e2e/` tier, `run_e2e.py --live`)

## Goal

One live-model E2E test that drives the full `investigate_stream` orchestration — vague profile → clarifying question → `refine_stream` answer → per-block deep analysis → `case_done` — against the real docker-compose PostGIS data, with a real LLM.

This is the only pipeline path the existing tiers do not cover: unit/integration/E2E tiers cover tools and single agents; the live tier covers per-agent tool calling. Nothing yet proves the *orchestration* (event ordering, the clarifying gate, refinement continuation, case-store persistence) works end-to-end with a live model.

## Scope

**In:** happy path including the refinement loop, in one test method.
**Out (explicitly):** `chat_in_case`, error paths (`case_error`), live narrative *quality* assertions, TestModel/mock-mode stream tests.

## Test File

`backend/tests/e2e/test_investigate_stream_live.py`

Gating (identical to `test_live_llm.py`):
- Skip unless `LIVE_LLM=1`
- Skip unless `AI_GATEWAY_API_KEY` set
- Skip if PostGIS unreachable (reuse `_connect()` from `tests/e2e/test_tools_e2e.py`)
- Runs under `python run_e2e.py --live`

## The Journey (single test method)

### Step 1 — vague profile triggers the clarifying gate

```python
PROFILE = ("Young family looking for a 4 ROOM flat, budget $750k, "
           "want good primary schools nearby.")
```

No town is given. Against ~9k blocks the candidate count exceeds the gate
threshold, so the stream must stop at a clarifying question.

Collect all events from `investigate_stream(repo, PROFILE, limit=2)`.

Assert:
- exactly one `clarifying_question` event; its `question` text is non-empty
- no `case_done` event in this first pass
- the first event is `agent_start` for agent `profile`
- a case exists in `case_store` for the returned `case_id`

**Failure honesty:** if the live model extracts preferences so specific that
the gate does not fire, fail with:
`"expected clarifying_question, got case_done — model parsed enough prefs from the vague profile; make PROFILE vaguer"`.
The test must not silently pass down the wrong path.

### Step 2 — refinement continues, does not loop

Call `refine_stream(repo, case_id, "Tampines please")` and collect events.

Assert:
- no `clarifying_question` event whose question text equals the Step 1
  question (regression guard for the refine-loop bug where the same question
  repeated — see memory `homeos-search-refinement-bug`)
- deep-analysis events are present (see Step 3)

If the model legitimately asks a *different* follow-up question, answer once
more (max 2 refinement rounds); if still no deep analysis, fail with the
accumulated question list.

### Step 3 — deep analysis event grammar (per block)

With `limit=2`, for each `block_id` appearing in deep-analysis events, assert
the per-agent sequence for each of `market`, `location`, `risk`:

```
agent_start(agent, block_id) → agent_summary(agent, block_id, narrative≠"") → agent_done(agent, block_id)
```

- ordering enforced within (agent, block_id); cross-agent interleaving allowed
- `agent_data` events, when present, must carry a `data` dict
- narratives asserted non-empty only — NEVER assert on live narrative content

### Step 4 — completion and persistence

Assert on the final event and the case store:
- last event is `case_done` with a `case_id` and non-empty `shortlist`
- every shortlist entry has `score` ∈ [0, 100] and a non-empty verdict string
- `case_store.get_case(case_id)["status"] == "done"`
- the case's `pipeline`/event log contains the clarifying question from
  Step 1 and the `case_done` from this step (full journey persisted)

## Cost Control

`limit=2` → 1 profile call + 1 refine call + (2 blocks × up to 4 agents)
≈ **10–11 billed calls** per run, single run, nano-tier model from `.env`
(`LLM_MODEL`). No retries on assertion failure.

## Non-Determinism Policy

Live output varies. Assertions are structural only:
- event kinds, ordering grammar, IDs, counts, score ranges, store status
- never narrative text, never specific blocks/towns in the shortlist
- the one content-ish assertion (Step 2 same-question check) compares against
  a string captured at runtime in Step 1, not a fixture

## Changes Outside the Test

- `~/.claude/skills/homeos-development/SKILL.md`: add the stream test to the
  live row of the test-tier table (doc-only)
- No production code changes. If the journey reveals a pipeline bug, fix it
  in a separate commit with its own regression test — do not bend the test
  to pass.

## Acceptance Criteria

1. `python run_e2e.py --live` runs the new test; it passes against the
   current compose DB + gateway model
2. Without `LIVE_LLM=1` the test skips; full offline suite unchanged
   (233 passed / 15+1 skipped, same 4 pre-existing failures)
3. The test fails loudly (not silently passes) when: the gate doesn't fire,
   the same question repeats, deep analysis never starts, or `case_done`
   is missing/malformed
