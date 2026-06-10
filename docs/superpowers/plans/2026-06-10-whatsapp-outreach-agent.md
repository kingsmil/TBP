# WhatsApp Message AI Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For a chosen active listing, an AI agent prepares a ready-to-send WhatsApp message tailored to the buyer's HomeOS profile and the unit — with a `wa.me` deep-link when the agent's number is public, and copy/mailto fallback otherwise.

**Architecture:** New `OutreachMessage` Pydantic model + `outreach_agent` (Pydantic AI, same `get_model()` stack) + deterministic mock. A service (`app/services/outreach.py`) assembles listing + case + proximity context, runs the agent (or mock), and resolves delivery channels. One endpoint `POST /listings/{listing_id}/outreach-message`. Frontend adds a "Prepare message" flow to `ActiveListingsSection` cards.

**Tech Stack:** Pydantic AI via Vercel AI Gateway (existing `get_model()`), FastAPI, React + TS + vitest.

Spec: `docs/superpowers/specs/2026-06-10-whatsapp-message-ai-agent-design.md`
Builds on: `feat/hdb-active-listings` (PR #2) — stacked branch.

---

### Task 1: OutreachMessage model + agent + mock

**Files:**
- Create: `backend/app/homeos/models/outreach.py`
- Modify: `backend/app/services/homeos_ai_agents.py` (add `outreach_agent`), `backend/app/homeos/mock/agents.py` (add `mock_outreach_message`)
- Test: `backend/tests/test_outreach.py` (new)

- [ ] Failing test: `mock_outreach_message(listing_dict, avatar_summary, contact_name, availability)` returns plain text referencing the unit (block number + flat type) and the availability; deterministic.
- [ ] `OutreachMessage(BaseModel)`: `message: str`, `questions: list[str] = []`.
- [ ] `outreach_agent: Agent[None, OutreachMessage]` with the spec §5 system prompt (≤90 words, plain text, 2–3 due-diligence questions, end with buyer one-liner + availability).
- [ ] Mock: f-string template using listing fields + avatar summary.
- [ ] Run → PASS → commit `feat(homeos): outreach message agent + mock`.

### Task 2: Outreach service (context assembly + channel resolution)

**Files:**
- Create: `backend/app/services/outreach.py`
- Test: `backend/tests/test_outreach.py` (extend)

- [ ] Failing tests: `sanitize_phone("+65 9123-4567") == "6591234567"`, `"9123 4567" → "6591234567"`, `None/"" → None`; `prepare_outreach_message(repo, listing_id=…)` returns dict with `message`; includes `whatsapp_url` only when listing has `agent_phone`; includes `email_url` only when `agent_email`; raises `ValueError` for unknown listing; works without `case_id`.
- [ ] Implement: load listing via `repo.active_listing()`; optional case via `case_store.get_case()` (avatar summary + prefs); proximity via `repo.proximity(listing.block_id)`; mock mode via `app.homeos.mock.tools.is_mock_mode()`, else `asyncio.run(outreach_agent.run(prompt))` (sync_agents pattern); `wa.me/{phone}?text={quote(message)}`; `mailto:` with subject+body.
- [ ] Run → PASS → commit `feat(services): outreach message preparation + channel resolution`.

### Task 3: API endpoint

**Files:**
- Modify: `backend/app/api/main.py`, `backend/app/api/schemas.py` (`OutreachRequest`)
- Test: `backend/tests/test_outreach.py` (extend, TestClient + dependency override, `HOMEOS_AGENT_MODE=mock`)

- [ ] Failing tests: 200 with `message` for seeded listing; `whatsapp_url` present only when phone seeded; unknown listing → 404.
- [ ] `OutreachRequest(BaseModel)`: `case_id: str | None = None`, `contact_name: str | None = None`, `availability: list[str] = []`, `note: str | None = None`.
- [ ] `POST /listings/{listing_id}/outreach-message` → `prepare_outreach_message(...)`; `ValueError` → 404.
- [ ] Run → PASS → commit `feat(api): POST /listings/{listing_id}/outreach-message`.

### Task 4: Frontend — Prepare message flow

**Files:**
- Modify: `frontend/src/types.ts` (`OutreachMessage`), `frontend/src/lib/api.ts` (`prepareOutreachMessage`), `frontend/src/components/ActiveListingsSection.tsx`
- Test: `frontend/src/components/ActiveListingsSection.test.tsx` (extend)

- [ ] Failing tests: clicking "Prepare message" renders returned message text; "Open in WhatsApp" link only when `whatsapp_url` present; "Copy message" always present after prepare.
- [ ] Implement: button per card → `POST`, inline result panel with message, conditional WhatsApp link (primary), Copy button (`navigator.clipboard`), conditional Email link, hint when no contact: "Contact this seller via the HDB Flat Portal and paste this message."
- [ ] Run vitest → PASS → commit `feat(fe): prepare WhatsApp outreach message from listing card`.

### Task 5: Wiring & PR

- [ ] Full backend + frontend suites green (modulo pre-existing failures).
- [ ] Push `feat/whatsapp-outreach-agent`; PR → base `feat/hdb-active-listings` on kingsmil/TBP.
