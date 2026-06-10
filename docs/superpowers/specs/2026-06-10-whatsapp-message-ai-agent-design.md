# WhatsApp Message AI Agent — Design Spec

**Date:** 2026-06-10
**Status:** Draft — pending approval
**Context:** HDB Match / TBP hackathon. Builds on
[Spec 1 — HDB Listings → Block Enrichment](2026-06-10-hdb-listings-block-enrichment-design.md).
**Delivery:** same fresh branch off TBP `main` → PR (one PR carries both features).

This is **Spec 2 of 2**.

---

## 1. Goal

When a buyer picks a **specific listing** (a specific agent/seller) on a block, an AI agent
**prepares a ready-to-send WhatsApp message** tailored to *that* listing and *this* buyer —
grounded in the buyer's HomeOS profile and the block's evidence — so the buyer can reach out in
one tap instead of writing a cold message from scratch.

Demo payoff: *"I like the 4-room at 126A Kim Tian — [Prepare message]"* → a polished, specific
WhatsApp message appears (intro, the exact unit, 2–3 sharp due-diligence questions, the buyer's
profile in one line, availability) → one tap opens WhatsApp with it pre-filled.

---

## 2. The hard constraint (read first)

Per Spec 1 §3.3: the HDB public API **does not expose agent phone numbers** (login-gated). So
this feature cannot rely on a real `wa.me` number being present. The design therefore separates
the two halves:

1. **Message generation** — always works (the valuable, AI part).
2. **Delivery channel** — best-effort: deep-link when a number exists, otherwise copy-to-clipboard
   + `mailto:` fallback.

This keeps the feature honest and demoable even though numbers are usually absent.

---

## 3. Non-Goals

- No sending on the user's behalf (no WhatsApp Business API, no automation). We only *prepare*.
- No scraping/bypassing HDB's login-gated contact endpoints.
- No conversation/threading — single outbound message only.
- No new buyer auth.

---

## 4. Inputs

The agent assembles context from data already in the system:

| Source | Provides |
|---|---|
| `ActiveListing` (Spec 1, by `listing_id`) | unit specifics: price, flat type, floor area, storey, remaining lease, block/street, agent name (if any) |
| HomeOS `Case` avatar + preferences (selected case, optional) | buyer one-liner, budget, household, commute/school priorities |
| Block evidence (existing services: proximity, accessibility) | MRT/school context for grounded questions |
| Optional buyer-supplied fields | contact name, availability windows, free-text note |

When no HomeOS case is selected, the agent still produces a generic-but-correct message from the
listing alone.

---

## 5. The agent

Reuse the existing Pydantic AI plumbing (`get_model()` → Vercel AI Gateway, same as the HomeOS
agents). New agent in the homeos agents package, e.g. `whatsapp_agent` /
`backend/app/homeos/agents/outreach.py`:

- **Output model** `OutreachMessage` (Pydantic): `{ message: str, questions: list[str] }`
  (typed output → no string parsing; `message` is the full body, `questions` echoed for the UI).
- **System prompt:** *"You write a concise, polite WhatsApp message from a prospective HDB buyer
  to the seller/agent of a specific resale flat. ≤ 90 words. Warm, specific, not pushy. Reference
  the exact unit. Include 2–3 genuine due-diligence questions grounded in the provided evidence
  (lease, storey, renovation, viewing availability). End with the buyer's one-line profile and
  availability if given. No markdown, no emojis-spam, plain text suitable for WhatsApp."*
- **Mock mode** parity: a deterministic `mock_outreach_message()` (mirrors the existing
  `homeos/mock` pattern) so `HOMEOS_AGENT_MODE=mock` and CI need no LLM key.

Greeting personalization: `"Hi {agent_first_name}"` when `agent_name` is present, else `"Hi"` —
ported from PR #3's `schedule_homeos_viewing`.

---

## 6. Delivery channel resolution

Given the generated `message` and the chosen `ActiveListing`:

```
phone = sanitize(listing.agent_phone)         # digits only, may be None
if phone:
    whatsapp_url = f"https://wa.me/65{phone}?text={urlencode(message)}"   # +65 SG
email_url = f"mailto:{listing.agent_email}?subject=...&body={urlencode(message)}"  if email else None
```

Response always includes `message`; includes `whatsapp_url` / `email_url` only when the
respective contact exists. The UI adapts (§8).

---

## 7. API

`POST /listings/{listing_id}/outreach-message`

Request:
```json
{
  "case_id": "optional — HomeOS case for buyer context",
  "contact_name": "optional",
  "availability": ["optional", "windows"],
  "note": "optional free text"
}
```
Response:
```json
{
  "listing_id": 40661,
  "message": "Hi, I'm interested in your 4-room at 126A Kim Tian Rd ...",
  "questions": ["Is the 85-year lease ...", "..."],
  "whatsapp_url": "https://wa.me/65XXXXXXXX?text=...",   // present only if phone known
  "email_url": "mailto:...",                              // present only if email known
  "agent_name": "..."                                     // present only if known
}
```
404 if `listing_id` unknown. Streaming is unnecessary (single short message) — return JSON.

---

## 8. UI

In the Spec 1 listing card (block detail panel), each listing gets a **"Prepare message"** button:

1. Click → `POST /listings/{id}/outreach-message` (passing the active HomeOS `case_id` if any).
2. Show the returned `message` in a small panel/modal with the questions listed.
3. Actions, shown conditionally:
   - **"Open in WhatsApp"** (primary) — `whatsapp_url`, only when a number exists.
   - **"Copy message"** — always (clipboard); the fallback when no number.
   - **"Email"** — `email_url`, only when an email exists.
4. Empty/absent contact → only "Copy message" shows, with a one-line hint
   *"Contact this seller via the HDB Flat Portal and paste this message."*

New TS type `OutreachMessage` in `types.ts`; `prepareOutreachMessage(listingId, body)` in
`lib/api.ts`.

---

## 9. Testing

- **Agent (mock):** `mock_outreach_message()` produces a non-empty body referencing the unit;
  deterministic for a fixed listing + case.
- **Channel resolution (unit):** phone present → `wa.me` URL with url-encoded text; phone absent →
  no `whatsapp_url`; email present → `mailto`; phone sanitization (spaces/`+65`/dashes stripped).
- **API (unit):** valid `listing_id` → 200 with `message`; unknown → 404; works with and without
  `case_id`; no LLM key needed (mock mode).
- **Frontend:** button → renders message; shows WhatsApp action only when URL present; copy always
  present.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| No public phone number (the big one) | Generation decoupled from delivery; copy + mailto fallback; honest UI hint (§8.4). |
| LLM unavailable / no key at demo | Mock-mode deterministic message; CI uses mock. |
| Message too long / markdown leaks into WhatsApp | Prompt caps ≤ 90 words, plain text; trim server-side. |
| Wrong country code | Hardcode `+65` (SG); document assumption. |
| PII / unsolicited contact concerns | We only *prepare* a message the user chooses to send; no automated sending, no stored contact beyond what the public API already returns. |

---

## 11. Decisions captured

- Reuse existing Vercel AI Gateway / Pydantic AI agent stack — consistent with HomeOS.
- Prepare-only (no auto-send) — per scope ("prepare the user with a WhatsApp message").
- Per-listing / per-agent (user chooses the specific agent) — per user.
- Graceful fallback when no number — forced by API reality (§2).
- Ships in the same PR as Spec 1.
