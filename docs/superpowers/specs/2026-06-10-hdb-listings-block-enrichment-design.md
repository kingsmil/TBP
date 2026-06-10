# HDB Resale Listings → Block Enrichment — Design Spec

**Date:** 2026-06-10
**Status:** Draft — pending approval
**Context:** HDB Match / TBP hackathon. Ports & extends the "active listings" idea from
`moroha29/estate-finder` PR #3 onto **TBP `main`** as a clean, self-contained feature.
**Delivery:** fresh branch off `origin/main` (TBP) → PR.

This is **Spec 1 of 2**. Spec 2 ([WhatsApp Message AI Agent](2026-06-10-whatsapp-message-ai-agent-design.md))
builds on the data this spec produces.

---

## 1. Goal

Enrich each of our **blocks** with the **real, currently-listed resale flats** in that block,
pulled live from the official HDB Flat Portal API, and show them in the block detail panel.

Our data is **block-grained**; the HDB portal is **flat-grained** (one listing per unit, one
agent/seller per listing). The relationship is therefore:

> **one Block → 0..N ActiveListings** (one block, at most many agents/flats).

The demo payoff: a user drills into a shortlisted block and sees *"3 units on the market here
right now — $1.33M 4-room on the 40th floor, 93 sqm, 85 yrs lease left"* with the real photo and
listing details — turning an analytics tool into something a buyer can act on today.

---

## 2. Non-Goals

- No buyer-side authentication (Singpass / HDB login). Public endpoints only.
- No write-back to HDB (no booking viewings via the portal API).
- No historical listing archive — we store the **current** snapshot and refresh it.
- WhatsApp / message generation is **out of scope here** — see Spec 2.

---

## 3. Data source — HDB Flat Portal public API

Base: `https://api.homes.hdb.gov.sg/flatback`
All calls are `POST`, `Content-Type: application/json`. CloudFront requires browser-like headers
(`User-Agent`, `Referer: https://homes.hdb.gov.sg/`, `Origin`, `X-XSRF-TOKEN` + matching
`XSRF-TOKEN`/`HDB_HOMES` cookies). These are obtained once and refreshed on `403`.

### 3.1 Endpoints (verified working, public)

| Purpose | Path | Body | Returns |
|---|---|---|---|
| All listing markers | `/public/v1/map/getCoordinatesByFilters` | full filter object (see §3.3) | `[{coords, props:{type, region, desc:[{id}]}}]` — **2,193 Resale** + BTO markers |
| Listing detail | `/public/v1/listing/resale/detailsJdbc` | `{"listingId":"<id>"}` | flat detail (see §3.2) |
| Listing images | `/public/v1/resale/getAllImagesByListing` | `{"listingId":"<id>"}` | image paths (optional) |

`detailsJdbc` is the workhorse: one call per resale `id` from the markers feed.

### 3.2 `detailsJdbc` response — verified shape (id `40661`)

```json
{
  "photo": "rf/40661/40661-IMG-1781023872084.jpg",
  "bedroom": 3, "bathroom": 2, "balcony": "No", "extension": "Yes",
  "price": 1330000,
  "block": "126A", "street": "KIM TIAN RD", "town": "Bukit Merah", "postal": "161126",
  "storeyRange": "More than 30", "remainingLease": "85 years 8 months",
  "flatType": "4-Room", "floorArea": 93.0,
  "managedByAgent": false,
  "description": [{
    "description": "Rare 40th Top-Floor Gem ...",
    "name": null, "number": null, "email": null,
    "agencyName": null, "ceaNumber": null, "licenseNo": null,
    "lastUpdated": "2026-06-10 01:07:50.96"
  }]
}
```

### 3.3 ⚠️ Reality check — agent contact is NOT public

Empirically scanning **80 live resale listings: 0 were agent-managed and 0 exposed a public
phone/name/email** — every `description[].number/name/email/agencyName` was `null`
(`managedByAgent: false`). The portal gates seller/agent contact behind a **login-only**
endpoint (`/protected/v1/agent/getSellerAgentContactDetails`,
`/protected/v1/buyer/requestForContactJdbc`).

**Consequence:** we get rich **flat** data publicly, but agent name/phone/email are usually
absent. The data model keeps those fields **nullable**, populating them only when the rare
agent-managed listing exposes them. Spec 2 is designed around this constraint (it does not
assume a phone number exists).

### 3.4 Photos (optional)

`photo` is a relative path (`rf/<id>/<id>-IMG-*.jpg`). The display base URL was not confirmed
during investigation. Per product decision, **photos are optional**: store the raw path, attempt
to render, and degrade gracefully (placeholder) if it 404s. Image rendering must never block the
listing data.

---

## 4. Matching listings to our blocks (the core problem)

HDB listing identifiers vs our `Block` fields (`block_number`, `street_name`, `postal_code`, `town`):

| HDB field | Our field | Notes |
|---|---|---|
| `postal` ("161126") | `postal_code` | 6-digit postal = unique HDB building. **Most precise** join. |
| `block` ("126A") | `block_number` | Both uppercased, includes letter suffix. |
| `street` ("KIM TIAN RD") | `street_name` | Both use HDB-abbreviated road names (RD/AVE/ST). |
| `town` ("Bukit Merah") | `town` | Coarse; tiebreaker only. |

### 4.1 Why postal alone is not enough

Our `postal_code` is **not reliably populated**: `data_gov_sg.py` sets it from OneMap geocoding
(real when geocode succeeds, `""` on failure), `fetch_live.py` hardcodes `postal_code=""`, and
mock data uses synthetic `460000 + block_id`. So a postal-only join silently drops matches.

### 4.2 Matching strategy — tiered, deterministic

For each fetched listing, resolve to a `block_id` via:

1. **Tier 1 — postal exact:** `listing.postal == block.postal_code` (both non-empty). High confidence.
2. **Tier 2 — block + street normalized:** `norm(block_number) == norm(block)` **and**
   `norm(street_name) == norm(street)`, where `norm()` uppercases, collapses whitespace, strips
   punctuation, and applies a small road-abbreviation map (`ROAD→RD`, `AVENUE→AVE`, `STREET→ST`,
   `DRIVE→DR`, etc.) to both sides.
3. **No match → skip** the listing and count it (do not invent a block).

Build an in-memory index of blocks keyed by `postal_code` and by `(norm_block, norm_street)` so
matching is O(1) per listing. Emit an `IngestReport`-style summary: `listings_fetched`,
`matched_tier1`, `matched_tier2`, `unmatched`, `blocks_with_listings`.

A block legitimately holds **multiple** listings (different units/agents) — all matched listings
are stored, keyed by `listing_id`.

---

## 5. Data model

New core model `ActiveListing` (`backend/app/core/models.py`):

```python
@dataclass(frozen=True)
class ActiveListing:
    listing_id: int          # HDB resale id (PK)
    block_id: int            # FK → our Block (resolved via §4)
    block_number: str        # raw "126A"
    street_name: str         # raw "KIM TIAN RD"
    postal_code: str
    town: str
    price: float
    flat_type: str           # "4-Room" (kept verbatim from portal)
    floor_area_sqm: float
    storey_range: str        # "More than 30"
    remaining_lease: str
    bedroom: int | None
    bathroom: int | None
    description: str | None   # listing blurb (description[0].description)
    photo_path: str | None    # raw "rf/.../*.jpg", may be null
    agent_name: str | None    # usually null (see §3.3)
    agent_phone: str | None   # usually null
    agent_email: str | None   # usually null
    agency_name: str | None   # usually null
    managed_by_agent: bool
    last_updated: str
```

`floor_area_sqft` stays a derived property (`sqm * 10.7639`).

---

## 6. Storage & repository

- **Migration** `0007_active_listings.sql` (next free number on TBP): `hdb_active_listings` table
  (columns mirror §5; `listing_id` PK; `block_id` FK → `hdb_blocks ON DELETE CASCADE`;
  nullable agent/photo columns) + `idx_active_listings_block_id`.
- **Repository interface** (`base.py`) gains:
  - `add_active_listings(items: Iterable[ActiveListing]) -> None`
  - `active_listings_for_block(block_id: int) -> Sequence[ActiveListing]`
  - `active_listing(listing_id: int) -> ActiveListing | None`
- **Memory repo:** dict `_active[listing_id]` + `_active_by_block[block_id]` (matches existing
  transaction storage pattern). Powers mock mode & tests.
- **PostGIS repo:** `INSERT … ON CONFLICT (listing_id) DO UPDATE` (refresh price/description/
  last_updated), and `_ACTIVE_SELECT … WHERE block_id = :id`.

---

## 7. Ingestion

New module `backend/app/data/hdb_listings.py` + a `make` target / CLI entry:

```
fetch_listings(limit=None) ->
  1. POST getCoordinatesByFilters            → resale ids (filter props.type == "Resale")
  2. for each id: POST detailsJdbc           → raw detail (bounded concurrency, retry on 403 → refresh token)
  3. map raw detail → block_id via §4
  4. repo.add_active_listings(matched)
  5. return ListingIngestReport
```

- Idempotent (upsert by `listing_id`); safe to re-run to refresh.
- Bounded concurrency + polite delay; `--limit` for fast demo seeds (e.g. 200) vs full (~2,200).
- Network-tolerant: a failed detail call is logged and skipped, never aborts the batch.
- Token/cookie acquisition isolated in one helper so it can be refreshed or swapped.

---

## 8. API

`GET /blocks/{block_id}/listings` → `200 [ActiveListingOut, …]` (empty list when none).
`ActiveListingOut` (Pydantic, `schemas.py`) exposes the §5 fields, omitting nulls, plus
`floor_area_sqft`. Sorted by `price` ascending. Reuses the existing FastAPI app & repo dependency.

(Optionally fold a `listings_count` + cheapest price into the existing block-summary payload so
the shortlist can badge blocks — but the detail panel is the committed surface.)

---

## 9. UI — block detail panel only

In the block detail panel (`HomeOSDetailPanel.tsx` / block panel), add an **"On the market now"**
section, rendered only when `listings.length > 0`:

- Section header: *"N units listed in this block"*.
- One card per listing: price (prominent), `flatType` · `floorArea` sqm · `storeyRange`,
  `remainingLease`, truncated `description`, photo thumbnail (lazy, placeholder on error).
- Agent/agency line shown **only if present** (else omitted — no empty "Agent: —").
- Each card carries the `listing_id` → hook point for the Spec 2 "Prepare WhatsApp message" button.

Fetched via a `react-query` call to `GET /blocks/{block_id}/listings` when a block is selected.
New TS types `ActiveListing` in `types.ts`; API helper in `lib/api.ts`.

---

## 10. Testing

- **Matching (unit):** postal-exact, block+street normalized (incl. road-abbrev variants),
  no-match-skip, one-block-many-listings. The hard logic — test thoroughly with fixtures.
- **Repo (unit):** add → `active_listings_for_block` / `active_listing` round-trip (memory).
- **Ingestion (unit):** raw-detail → `ActiveListing` mapper against the **recorded `detailsJdbc`
  fixture** (id 40661); report counters. Network is mocked — no live calls in CI.
- **API (unit):** `GET /blocks/{id}/listings` shape, empty-list, sort order.
- **Frontend:** detail panel renders N cards; hides agent line when null; hides section when empty.

---

## 11. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Agent contact rarely public (§3.3) | Nullable fields; UI hides when absent; Spec 2 designed without assuming a phone. |
| `postal_code` unreliable on our side | Tiered match with block+street fallback (§4.2). |
| Street-name abbreviation mismatches | `norm()` abbreviation map; report unmatched count to tune it. |
| CloudFront 403 / token expiry | Centralized token helper, retry-with-refresh, browser-like headers. |
| Photo base URL unknown | Photos optional; graceful placeholder. |
| Live API down during demo | Ingestion writes to repo ahead of time; demo reads stored snapshot, not live. |

---

## 12. Out-of-repo decisions captured

- **Data source:** real HDB Flat Portal public API (not mock) — per user.
- **UI surface:** block detail panel only — per user.
- **Photos:** optional — per user.
- **Cardinality:** one block → at most many agents/listings — per user.
- **Delivery:** fresh branch off TBP `main` → PR.
