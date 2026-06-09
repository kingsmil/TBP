# HDB Resale Listings → Block Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pull live resale listings from the HDB Flat Portal public API, match each to one of our blocks (postal-exact, then normalized block+street), store them (one Block → many ActiveListings), and surface them in the block detail panel.

**Architecture:** New `ActiveListing` core model + repository methods (memory/PostGIS) + migration `0008`. A standalone ingestion module (`app/data/hdb_listings.py`) fetches markers → details, matches to blocks, upserts. One new read endpoint `GET /blocks/{block_id}/listings`. Frontend adds an `ActiveListingsSection` to `HomeOSDetailPanel`.

**Tech Stack:** FastAPI, httpx, dataclasses, PostGIS (SQLAlchemy text SQL), React + TS + vitest.

Spec: `docs/superpowers/specs/2026-06-10-hdb-listings-block-enrichment-design.md`

---

### Task 1: `ActiveListing` core model

**Files:**
- Modify: `backend/app/core/models.py` (after `Transaction`)
- Test: `backend/tests/test_active_listings.py` (new)

- [ ] **Step 1: Write failing test**

```python
"""Tests for ActiveListing model, repo methods, and listing→block matching."""
import unittest

from app.core.models import ActiveListing


def make_listing(**kw):
    base = dict(
        listing_id=40661, block_id=1, block_number="126A",
        street_name="KIM TIAN RD", postal_code="161126", town="Bukit Merah",
        price=1330000.0, flat_type="4-Room", floor_area_sqm=93.0,
        storey_range="More than 30", remaining_lease="85 years 8 months",
        bedroom=3, bathroom=2, description="Rare top-floor gem",
        photo_path="rf/40661/40661-IMG.jpg", agent_name=None, agent_phone=None,
        agent_email=None, agency_name=None, managed_by_agent=False,
        last_updated="2026-06-10 01:07:50",
    )
    base.update(kw)
    return ActiveListing(**base)


class ActiveListingModelTest(unittest.TestCase):
    def test_floor_area_sqft_derived(self):
        listing = make_listing()
        self.assertAlmostEqual(listing.floor_area_sqft, 93.0 * 10.7639, places=2)

    def test_nullable_agent_fields_default_none(self):
        listing = make_listing()
        self.assertIsNone(listing.agent_name)
        self.assertFalse(listing.managed_by_agent)
```

- [ ] **Step 2: Run** `cd backend && python -m unittest tests.test_active_listings -v` → FAIL (ImportError)

- [ ] **Step 3: Implement** in `core/models.py` after `Transaction`:

```python
@dataclass(frozen=True)
class ActiveListing:
    """A currently-listed resale flat from the HDB Flat Portal, matched to a Block."""
    listing_id: int
    block_id: int
    block_number: str
    street_name: str
    postal_code: str
    town: str
    price: float
    flat_type: str
    floor_area_sqm: float
    storey_range: str
    remaining_lease: str
    bedroom: int | None
    bathroom: int | None
    description: str | None
    photo_path: str | None
    agent_name: str | None
    agent_phone: str | None
    agent_email: str | None
    agency_name: str | None
    managed_by_agent: bool
    last_updated: str

    @property
    def floor_area_sqft(self) -> float:
        return self.floor_area_sqm * 10.7639
```

- [ ] **Step 4: Run test** → PASS
- [ ] **Step 5: Commit** `feat(core): add ActiveListing model`

---

### Task 2: Repository methods (base + memory)

**Files:**
- Modify: `backend/app/repositories/base.py`, `backend/app/repositories/memory.py`
- Test: `backend/tests/test_active_listings.py` (extend)

- [ ] **Step 1: Failing test**

```python
from app.repositories.memory import InMemoryRepository


class ActiveListingRepoTest(unittest.TestCase):
    def test_add_and_read_listings_by_block(self):
        repo = InMemoryRepository()
        repo.add_active_listings([
            make_listing(listing_id=1, block_id=10),
            make_listing(listing_id=2, block_id=10, price=900000.0),
            make_listing(listing_id=3, block_id=11),
        ])
        ten = repo.active_listings_for_block(10)
        self.assertEqual({l.listing_id for l in ten}, {1, 2})
        self.assertEqual(repo.active_listings_for_block(99), [])
        self.assertEqual(repo.active_listing(3).block_id, 11)
        self.assertIsNone(repo.active_listing(99))

    def test_upsert_replaces_same_listing_id(self):
        repo = InMemoryRepository()
        repo.add_active_listings([make_listing(listing_id=1, block_id=10, price=1.0)])
        repo.add_active_listings([make_listing(listing_id=1, block_id=10, price=2.0)])
        self.assertEqual(len(repo.active_listings_for_block(10)), 1)
        self.assertEqual(repo.active_listing(1).price, 2.0)
```

- [ ] **Step 2: Run** → FAIL (no method)
- [ ] **Step 3: Implement.** `base.py`: add to `Repository` protocol (import `ActiveListing`):

```python
    def add_active_listings(self, items: Iterable[ActiveListing]) -> None: ...
    def active_listings_for_block(self, block_id: int) -> Sequence[ActiveListing]: ...
    def active_listing(self, listing_id: int) -> ActiveListing | None: ...
```

`memory.py`: add `self._active: dict[int, ActiveListing] = {}` to `__init__`; methods rebuild the by-block view so re-adding a listing_id replaces (upsert semantics):

```python
    def add_active_listings(self, items: Iterable[ActiveListing]) -> None:
        for it in items:
            self._active[it.listing_id] = it

    def active_listings_for_block(self, block_id: int) -> Sequence[ActiveListing]:
        return [a for a in self._active.values() if a.block_id == block_id]

    def active_listing(self, listing_id: int) -> ActiveListing | None:
        return self._active.get(listing_id)
```

- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `feat(repo): active listing storage (base protocol + memory)`

---

### Task 3: Migration + PostGIS repository

**Files:**
- Create: `backend/app/db/migrations/sql/0008_active_listings.sql`
- Modify: `backend/app/repositories/postgis.py`
- Test: `backend/tests/test_migrations_sql.py` already validates SQL files parse/order — run it.

- [ ] **Step 1: Migration**

```sql
-- Active HDB resale listings fetched from the HDB Flat Portal public API.
-- One block has 0..N active listings (one per flat/unit on the market).
CREATE TABLE IF NOT EXISTS hdb_active_listings (
    listing_id BIGINT PRIMARY KEY,
    block_id INT NOT NULL REFERENCES hdb_blocks(block_id) ON DELETE CASCADE,
    block_number TEXT NOT NULL,
    street_name TEXT NOT NULL,
    postal_code TEXT NOT NULL DEFAULT '',
    town TEXT NOT NULL DEFAULT '',
    price DECIMAL(12, 2) NOT NULL,
    flat_type TEXT NOT NULL,
    floor_area_sqm DECIMAL(6, 2) NOT NULL,
    storey_range TEXT NOT NULL DEFAULT '',
    remaining_lease TEXT NOT NULL DEFAULT '',
    bedroom INT,
    bathroom INT,
    description TEXT,
    photo_path TEXT,
    agent_name TEXT,
    agent_phone TEXT,
    agent_email TEXT,
    agency_name TEXT,
    managed_by_agent BOOLEAN NOT NULL DEFAULT FALSE,
    last_updated TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_active_listings_block_id ON hdb_active_listings(block_id);
```

- [ ] **Step 2: PostGIS repo** — mirror `add_transactions` / `_txn_row` patterns: `INSERT … ON CONFLICT (listing_id) DO UPDATE SET price/description/photo_path/agent_*/managed_by_agent/last_updated = EXCLUDED.…`; `_ACTIVE_SELECT` constant; `_active_row` static builder; `active_listings_for_block` / `active_listing` queries. (Text SQL like the rest of the file; no ORM models.)
- [ ] **Step 3: Run** `python -m unittest tests.test_migrations_sql tests.test_active_listings -v` → PASS
- [ ] **Step 4: Commit** `feat(db): hdb_active_listings migration + postgis repo support`

---

### Task 4: Listing→block matcher

**Files:**
- Create: `backend/app/data/hdb_listings.py`
- Test: `backend/tests/test_active_listings.py` (extend)

- [ ] **Step 1: Failing tests**

```python
from app.core.geo import Point
from app.core.models import Block
from app.data.hdb_listings import BlockMatcher, normalize_street


def make_block(block_id=1, number="126A", street="KIM TIAN RD", postal="161126"):
    return Block(block_id=block_id, block_number=number, street_name=street,
                 postal_code=postal, town="BUKIT MERAH", planning_area_id=None,
                 lease_commencement_year=2001, point=Point(103.83, 1.28))


class StreetNormTest(unittest.TestCase):
    def test_abbreviations_collapse(self):
        self.assertEqual(normalize_street("Kim Tian Road"), "KIM TIAN RD")
        self.assertEqual(normalize_street("ANG MO KIO AVENUE 3"), "ANG MO KIO AVE 3")
        self.assertEqual(normalize_street("  jurong   west st 42 "), "JURONG WEST ST 42")


class BlockMatcherTest(unittest.TestCase):
    def test_tier1_postal_exact(self):
        m = BlockMatcher([make_block()])
        bid, tier = m.match(postal="161126", block="999Z", street="NOWHERE")
        self.assertEqual((bid, tier), (1, 1))

    def test_tier2_block_street_when_postal_missing_on_our_side(self):
        m = BlockMatcher([make_block(postal="")])
        bid, tier = m.match(postal="161126", block="126a", street="Kim Tian Road")
        self.assertEqual((bid, tier), (1, 2))

    def test_no_match_returns_none(self):
        m = BlockMatcher([make_block()])
        bid, tier = m.match(postal="999999", block="1", street="FAKE ST")
        self.assertEqual((bid, tier), (None, 0))
```

- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement** in `hdb_listings.py`:

```python
_ROAD_ABBREV = {
    "ROAD": "RD", "AVENUE": "AVE", "STREET": "ST", "DRIVE": "DR",
    "CRESCENT": "CRES", "CLOSE": "CL", "PLACE": "PL", "TERRACE": "TER",
    "GARDENS": "GDNS", "HEIGHTS": "HTS", "NORTH": "NTH", "SOUTH": "STH",
    "CENTRAL": "CTRL", "UPPER": "UPP", "JALAN": "JLN", "LORONG": "LOR",
    "BUKIT": "BT", "TANJONG": "TG", "KAMPONG": "KG", "SAINT": "ST.",
}

def normalize_street(s: str) -> str:
    words = re.sub(r"[^\w\s.]", " ", s.upper()).split()
    return " ".join(_ROAD_ABBREV.get(w, w) for w in words)


class BlockMatcher:
    """Tiered listing→block resolution: postal exact, then norm(block)+norm(street)."""
    def __init__(self, blocks: Sequence[Block]):
        self._by_postal = {b.postal_code: b.block_id for b in blocks if b.postal_code}
        self._by_addr = {(b.block_number.strip().upper(), normalize_street(b.street_name)): b.block_id
                         for b in blocks}

    def match(self, postal: str, block: str, street: str) -> tuple[int | None, int]:
        bid = self._by_postal.get((postal or "").strip())
        if bid is not None:
            return bid, 1
        bid = self._by_addr.get(((block or "").strip().upper(), normalize_street(street or "")))
        if bid is not None:
            return bid, 2
        return None, 0
```

- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** `feat(data): tiered listing→block matcher`

---

### Task 5: HDB portal client + ingestion

**Files:**
- Modify: `backend/app/data/hdb_listings.py`
- Create: `backend/tests/fixtures/hdb_detail_40661.json` (recorded real response from spec §3.2)
- Test: `backend/tests/test_active_listings.py` (extend; network mocked)

- [ ] **Step 1: Failing tests** — `parse_detail(raw, listing_id)` maps the recorded fixture to an `ActiveListing`-shaped dict (no block_id yet); `ingest_listings(repo, fetch_markers, fetch_detail)` wires markers → details → matcher → `repo.add_active_listings`, returns report with counters `listings_fetched/matched_tier1/matched_tier2/unmatched`. Inject fetchers as callables so tests pass lambdas (no network).

```python
class ParseDetailTest(unittest.TestCase):
    def test_parse_recorded_fixture(self):
        import json, pathlib
        raw = json.loads((pathlib.Path(__file__).parent / "fixtures" / "hdb_detail_40661.json").read_text())
        d = parse_detail(raw, 40661)
        self.assertEqual(d["postal_code"], "161126")
        self.assertEqual(d["price"], 1330000)
        self.assertEqual(d["block_number"], "126A")
        self.assertIsNone(d["agent_name"])          # §3.3: agent contact not public
        self.assertFalse(d["managed_by_agent"])


class IngestTest(unittest.TestCase):
    def test_ingest_matches_and_stores(self):
        repo = InMemoryRepository()
        repo.add_blocks([make_block()])
        raw = {...fixture dict...}
        report = ingest_listings(
            repo,
            fetch_markers=lambda: ["40661"],
            fetch_detail=lambda lid: raw,
        )
        self.assertEqual(report.matched_tier1, 1)
        self.assertEqual(len(repo.active_listings_for_block(1)), 1)
```

- [ ] **Step 2: Implement** — `ListingIngestReport` dataclass; `parse_detail` (description[0] holds blurb + agent fields; flat fields verbatim); httpx-based `fetch_markers()` / `fetch_detail()` with browser-like headers, env-overridable XSRF/cookie (`HDB_XSRF_TOKEN`, `HDB_HOMES_COOKIE`), bootstrap GET to grab cookies when unset, retry-once-on-403; `ingest_listings()` orchestrator + `main()` CLI (`--limit`). Failed detail calls logged + counted, never abort.
- [ ] **Step 3: Run full suite** `python -m unittest discover -s tests -p "test_*.py"` → PASS
- [ ] **Step 4: Commit** `feat(data): HDB Flat Portal listings ingestion`

---

### Task 6: API endpoint

**Files:**
- Modify: `backend/app/api/main.py`
- Test: `backend/tests/test_active_listings.py` (extend, FastAPI TestClient — follow `test_homeos_stream_api.py` style)

- [ ] **Step 1: Failing test** — seed repo + listings, `GET /blocks/{id}/listings` → 200 sorted-by-price list with `floor_area_sqft`, omits null agent fields; unknown block → 404; block with none → `[]`.
- [ ] **Step 2: Implement** in `main.py` near `property_detail`:

```python
@app.get("/blocks/{block_id}/listings")
def block_listings(block_id: int, repo: Repository = Depends(get_repository)):
    if repo.block(block_id) is None:
        raise HTTPException(status_code=404, detail="block not found")
    listings = sorted(repo.active_listings_for_block(block_id), key=lambda a: a.price)
    out = []
    for a in listings:
        d = {k: v for k, v in a.__dict__.items() if v is not None}
        d["floor_area_sqft"] = round(a.floor_area_sqft, 1)
        out.append(d)
    return {"count": len(out), "listings": out}
```

- [ ] **Step 3: Run** → PASS, commit `feat(api): GET /blocks/{block_id}/listings`

---

### Task 7: Frontend — ActiveListingsSection

**Files:**
- Create: `frontend/src/components/ActiveListingsSection.tsx`, `frontend/src/components/ActiveListingsSection.test.tsx`
- Modify: `frontend/src/types.ts` (`ActiveListing`, `BlockListingsResponse`), `frontend/src/lib/api.ts` (`getBlockListings`), `frontend/src/components/HomeOSDetailPanel.tsx` (render section)

- [ ] **Step 1: Types + api helper** (`getBlockListings(blockId): Promise<BlockListingsResponse>` via `getJSON`).
- [ ] **Step 2: Failing component tests** — renders "N units listed in this block" + price/flat-type per card; omits agent line when absent; renders nothing when `listings=[]`.
- [ ] **Step 3: Implement** `ActiveListingsSection({ blockId })`: fetch on mount, card list ("On the market now"), price prominent (`formatSGD`), `flat_type · floor_area_sqm sqm · storey_range`, remaining lease, truncated description, lazy `<img>` with `onError` hide, agent/agency line only when present. Mount in `HomeOSDetailPanel` below the case-file section.
- [ ] **Step 4: Run** `cd frontend && npx vitest run` → PASS
- [ ] **Step 5: Commit** `feat(fe): active listings in block detail panel`

---

### Task 8: Wiring & PR

- [ ] Makefile target `listings-load: cd backend && python -m app.data.hdb_listings`; mention in `make help` + README features list.
- [ ] Full backend (`python -m unittest discover -s tests -p "test_*.py"`) + frontend (`npx vitest run`) suites green.
- [ ] Live smoke (optional, network): `python -m app.data.hdb_listings --limit 20` against seeded repo; check report counts.
- [ ] Commit docs; push `feat/hdb-active-listings`; open PR → `kingsmil/TBP` `main`.
