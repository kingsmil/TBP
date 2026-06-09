# HomeOS — Complete Reference

**Stack:** FastAPI (port 8010) + React/Vite + PostGIS + Redis. Run: `python setup.py --run`.

---

## Pipeline (3 phases, all in `backend/app/services/homeos.py`)

```
POST /homeos/investigate-stream  →  investigate_stream(repo, profile_text)
  Phase 1  profile_agent.run(text)            → HomeOSAvatar (prefs: flat_type, max_price, town, commute_priority, school_priority …)
  Phase 2  _search_phase(repo, case_id, prefs) → search_blocks() → up to 500 results → _lightweight_rank(top 10)
           if count > 10  → emit clarifying_question SSE, status="refining", STOP
           if count ≤ 10  → Phase 3
  Phase 3  per candidate: market_analysis_agent → location_graph_agent → risk_value_agent → worth_viewing_score()
           emit case_done SSE with ranked shortlist

POST /homeos/cases/{id}/refine   →  refine_stream(repo, case_id, user_message)
  appends user message to case["conversation"]
  builds structured Q&A prompt pairing pipeline clarifying_questions with conversation answers
  re-runs profile_agent on prompt  →  updated prefs
  applies _direct_answer_overrides() to guarantee correct field (e.g. "within 600m" → commute_priority="high")
  re-runs Phase 2; if still > 10 asks another question, else proceeds to Phase 3
```

**Case statuses:** `running` → `refining` ↔ loop → `done` | `error`  
**Threshold constant:** `_ANALYSIS_THRESHOLD = 10`

---

## Key source files

| File | What it does |
|------|-------------|
| `backend/app/services/homeos.py` | Pipeline orchestration, all Phase 2 helpers, refine_stream |
| `backend/app/services/homeos_ai_agents.py` | Pydantic AI agent instances (profile, market, location, risk, questions) |
| `backend/app/services/homeos_ai_models.py` | Pydantic output models + flat_type/town validators |
| `backend/app/services/homeos_agents.py` | Deterministic sub-agents (market_analysis_agent, location_graph_agent, risk_value_agent, worth_viewing_score) |
| `backend/app/services/homeos_case_store.py` | In-memory case dict store (pipeline events, conversation, shortlist) |
| `backend/app/services/search.py` | search_blocks() — 4 filter layers: bbox, block attrs, proximity, price/flat_type |
| `backend/app/api/main.py` | All /homeos/* HTTP endpoints |
| `frontend/src/components/CasesPanel.tsx` | Left panel: cases dropdown, chat history, auto-grow textarea |
| `frontend/src/components/PipelinePanel.tsx` | Right panel: agent steps, shortlist, download button |
| `frontend/src/lib/api.ts` | investigateStream(), refineStream(), chatInCase() SSE generators |
| `frontend/src/types.ts` | AgentEvent, HomeOSCase, HomeOSAvatar, HomeOSPreferences TypeScript types |

---

## prefs → SearchQuery mapping (`_prefs_to_search_query`)

| Pref field | SearchQuery field |
|------------|------------------|
| `flat_type` | `flat_type` — must be "4 ROOM" format (normalised by field_validator) |
| `max_price` | `max_price` — blocks with median txn price above this are excluded |
| `town` | `town` — upper-cased HDB town name |
| `commute_priority="high"` | `max_mrt_distance_m=600` |
| `commute_priority="medium"` | `max_mrt_distance_m=1200` |
| `school_priority="high"` | `min_schools_within_1km=2` |
| `school_priority="medium"` | `min_schools_within_1km=1` |

---

## SSE events

| Event | When | Key fields |
|-------|------|-----------|
| `agent_start` | before each agent | `agent`, `block_id` |
| `agent_summary` | after each agent | `agent`, `narrative`, `data` (includes `search_query` for search agent) |
| `agent_done` | signals completion | `agent`, `block_id` |
| `clarifying_question` | search > threshold | `question` — stream stops, case="refining" |
| `case_done` | Phase 3 complete | `shortlist[]` with worth_viewing_score, verdict, top_reasons |
| `case_error` | exception | `message` |

---

## Clarifying question order (`_clarifying_question`)

1. `flat_type` missing → ask flat type
2. `max_price` missing → ask budget
3. `commute_priority != "high"` → ask MRT importance (High=600m / Medium=1.2km)
4. `school_priority == "low"` → ask school importance
5. fallback → ask preferred town

## Why `_direct_answer_overrides` exists

`gpt-5.4-nano` cannot reliably map `"within 600m"` → `commute_priority="high"`. After the profile agent runs, this function reads the last `clarifying_question` from the pipeline (stateless — no stored field tag), identifies the field from question keywords (`"mrt"` → commute_priority), and applies rule-based keyword matching on the user's answer. The result is merged over the LLM output as a guaranteed override.

---

## Case store schema (`homeos_case_store.py`)

```
case_id, profile_text, avatar, pipeline[], shortlist[], conversation[], status, search_prefs{}, candidate_ids[]
```
All in-memory — cleared on server restart. Accessed via `GET /homeos/cases` and `GET /homeos/cases/{id}`.

## worth_viewing_score breakdown (`homeos_agents.py`)

within_budget +30 | above_budget +10 | txn≥4 +20 | MRT strong +18 | MRT moderate +11 | school strong (family) +18 | risk.score_adjustment ±12 | max 100
Verdicts: ≥75 "Worth viewing" · ≥50 "Maybe view" · <50 "Skip for now"
