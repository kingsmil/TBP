# HDB Match — Geospatial Architecture (Phase 1 Foundation)

**Document type:** Technical Design — Geospatial Foundation
**Scope:** Phase 1 only — Database Setup, Data Ingestion Pipelines, Interactive Map, HDB Filters, Analytics Dashboard
**Architectural stance:** Geospatial analytics platform first. Every Phase 1 decision optimizes for map rendering performance, spatial query latency, and analytics throughput — not listing management. PostGIS is a first-class component from day one.
**Date:** 2026-05-31

---

## 1. Purpose and Reading Guide

This document refines the original TDD for the Phase 1 foundation, re-centering it on a geospatial-first model. It does not introduce code; it specifies the data model, coordinate strategy, indexing, query patterns, tile-serving pipeline, ingestion design, and caching that the implementation will follow.

The central thesis: **HDB Match is a spatial query engine with a map on top, not a CRUD app with a map widget.** The hot paths are "render N thousand geo-features in a viewport at 60fps," "find blocks within X metres of an MRT," and "aggregate transactions over space and time." If the foundation serves those well, the scoring engines in later phases become straightforward consumers of the same primitives.

The remaining phases (commute, scoring, appreciation, forecasting) are explicitly out of scope here, but the schema and query layer are designed so those engines plug in without restructuring.

---

## 2. Guiding Architectural Principles

The following tenets govern every decision in this document.

**Geometry is canonical, attributes are secondary.** Every spatial entity carries a real geometry column with a spatial index. We never reconstruct location from `latitude`/`longitude` floats at query time; those floats are inputs to ingestion, not the source of truth for queries.

**Precompute spatial relationships, query attributes live.** Point-to-point distances, nearest-neighbour links, and "count within radius" are expensive and change rarely (reference data like MRT and schools is near-static). These are materialized once and refreshed on data change. Attribute filters (price, flat type, lease) are cheap B-tree lookups and run live.

**The map is fed by vector tiles, not GeoJSON dumps.** Serving raw feature collections does not scale past a few thousand features. PostGIS generates Mapbox Vector Tiles (`ST_AsMVT`) server-side, simplified per zoom level and cached. This is the single most important map-performance decision in Phase 1.

**Analytics are materialized and cached, not computed per request.** Median/average PSF, transaction volume, and time series are rolled up into materialized views refreshed by background jobs and served from Redis.

**Metric accuracy uses Singapore's national projection.** All distance, buffer, and area maths run in EPSG:3414 (SVY21), not in degrees. Display and interchange use EPSG:4326. See Section 3.

**Idempotent, validated ingestion.** Every pipeline can re-run safely, validates and repairs geometry on the way in, and never partially corrupts a layer.

---

## 3. Coordinate Reference System Strategy

This is foundational and easy to get wrong, so it is decided up front.

Singapore has a national projected CRS — **SVY21 / EPSG:3414** — whose units are metres and which is accurate for distance and area within Singapore. Web mapping and data interchange use **WGS84 / EPSG:4326** (degrees). Web tiles render in **Web Mercator / EPSG:3857**.

**Decision — store dual geometry:**

Every spatial table stores two geometry columns:

- `geom geometry(<type>, 4326)` — canonical WGS84, used for display, GeoJSON, interchange, and as the source of truth on ingest.
- `geom_svy21 geometry(<type>, 3414)` — a **generated/stored** column, `ST_Transform(geom, 3414)`, used for all metric operations: `ST_DWithin`, `ST_Distance`, `ST_Buffer`, KNN ordering, and area.

Both columns get their own GIST index. Rationale: computing distances in 4326 with `ST_Distance` forces the planner onto the slower geography path or yields degree-distances that are wrong for buffers; carrying a projected column lets every proximity query stay metric, index-assisted, and correct.

Tile generation transforms 4326 → 3857 at tile time via `ST_AsMVTGeom`; we do not store a 3857 column.

**Rule of thumb for implementers:** if a query measures *how far* or *how big*, it uses `geom_svy21`. If it *renders* or *exports*, it uses `geom`.

---

## 4. PostGIS Data Model (Improved Schema)

The original table list is treated as a starting point. Below is the geospatial-first revision for Phase 1. Conventions: all spatial tables gain `geom` (4326) and a generated `geom_svy21` (3414); timestamps `created_at`/`updated_at` are implied on all tables; surrogate keys are `bigint` identity unless noted.

### 4.1 Core spatial entities

**`hdb_blocks`** — the central spatial entity.

| Column | Type | Notes |
|---|---|---|
| `block_id` | bigint PK | surrogate |
| `block_number` | text | |
| `street_name` | text | |
| `postal_code` | text | added — primary join key to HDB/OneMap |
| `town` | text | |
| `planning_area_id` | bigint FK → `planning_areas` | added — resolved by point-in-polygon at ingest |
| `lease_commencement_year` | smallint | |
| `geom` | geometry(Point,4326) | canonical |
| `geom_svy21` | geometry(Point,3414) GENERATED | `ST_Transform(geom,3414)` — `ST_Transform` is immutable, so this is a valid stored generated column |

`remaining_lease_years` is **not** a stored generated column — it depends on the current date (`now()` is non-immutable and disallowed in `GENERATED` columns). It is exposed as a computed expression in a view over `hdb_blocks` (`99 - (extract(year from current_date) - lease_commencement_year)`), or materialized into `block_proximity`/a stats layer and refreshed daily, so filters on remaining lease still hit an indexable column.

Unique constraint on (`block_number`, `street_name`) or `postal_code` to make ingestion idempotent.

**`mrt_stations`**, **`future_mrt_stations`** — same geometry treatment; keep `station_name`, `line_name`, `opening_year`. Consider merging into one `mrt_stations` table with a `status` enum (`operational` / `future`) and `opening_year`; it simplifies "distance to nearest MRT (current or future)" queries and proximity refresh. Recommendation: **single table with status flag**, exposed as two logical layers.

**`bus_stops`** — `bus_stop_code` PK, `description`, geometry. ~5,000 rows; the densest layer, so tiling and clustering matter most here.

**`schools`** — `school_id` PK, `school_name`, `school_type`, geometry.

**`bto_projects`** — `project_id` PK, `project_name`, `launch_year`, geometry. (Phase 1 stores and displays; supply scoring is later.)

**`planning_areas`** — **new table**, sourced from OneMap planning-area polygons.

| Column | Type | Notes |
|---|---|---|
| `planning_area_id` | bigint PK | |
| `name` | text | |
| `region` | text | |
| `geom` | geometry(MultiPolygon,4326) | |
| `geom_svy21` | geometry(MultiPolygon,3414) GENERATED | for area/containment in metres |

This table turns "which town/region is this block in" from a fragile string match into an authoritative point-in-polygon resolution, and gives the map a real boundary layer.

### 4.2 Transactions (large, append-mostly, partitioned)

**`hdb_transactions`** — the analytics workhorse; will grow to hundreds of thousands of rows.

| Column | Type | Notes |
|---|---|---|
| `transaction_id` | bigint PK | |
| `block_id` | bigint FK → `hdb_blocks` | |
| `transaction_month` | date | partition key (first of month) |
| `resale_price` | numeric | |
| `floor_area_sqm` | numeric | |
| `floor_area_sqft` | numeric GENERATED | `floor_area_sqm * 10.7639` |
| `psf` | numeric GENERATED | `resale_price / (floor_area_sqm * 10.7639)` |
| `flat_type` | text | |
| `storey_range` | text | |

**Decision — declarative range partitioning by `transaction_month`** (yearly partitions). Rationale: every analytics query is time-bounded ("last 12 months", "since 2020"), so partition pruning cuts scan volume dramatically, and monthly ingestion only touches the current partition. `psf` is a generated column so analytics never recompute it and it can be indexed directly.

### 4.3 Precomputed proximity (the spatial hot-path cache)

**`block_proximity`** — **new table**, one row per HDB block, refreshed by Celery when reference layers change.

| Column | Type | Notes |
|---|---|---|
| `block_id` | bigint PK FK → `hdb_blocks` | |
| `nearest_mrt_station_id` | bigint | current MRT |
| `nearest_mrt_distance_m` | numeric | metres, via SVY21 |
| `nearest_future_mrt_station_id` | bigint | |
| `nearest_future_mrt_distance_m` | numeric | |
| `nearest_bus_stop_code` | text | |
| `nearest_bus_distance_m` | numeric | |
| `schools_within_1km` | smallint | |
| `schools_within_2km` | smallint | |
| `bus_stops_within_400m` | smallint | walkable bus access |

This is what makes the accessibility filters in Section 9 instantaneous. Without it, every filter request would run thousands of KNN computations live. With it, accessibility filters become indexed numeric comparisons. It is computed once with the KNN/`ST_DWithin` patterns in Section 6 and refreshed only when MRT/bus/school data changes (rarely) or new blocks are ingested.

### 4.4 Bus routes (Phase 1 storage, later graph)

**`bus_routes`** — keep `service_no`, `bus_stop_code`, `stop_sequence`. Phase 1 only stores and displays. The NetworkX transit graph for commute routing is a later phase, but storing `stop_sequence` correctly now means we can derive route LineStrings and an edge list later without re-ingesting.

### 4.5 Materialized views for analytics

Two rollups back the entire analytics dashboard:

- **`mv_block_monthly_stats`** — grouped by (`block_id`, `transaction_month`, `flat_type`): `median_psf` (`percentile_cont(0.5)`), `avg_psf`, `median_price`, `avg_price`, `txn_count`.
- **`mv_estate_monthly_stats`** — same metrics grouped by (`planning_area_id`/`town`, `transaction_month`, `flat_type`), plus an estate-level lease profile aggregate.

These are refreshed `CONCURRENTLY` after each transaction-ingest run. Charts (PSF over time, volume over time, PSF by flat type) read straight from these, then results are cached in Redis. Live `GROUP BY` over the partitioned base table is reserved for ad-hoc/uncached paths only.

> Materialized views must have a unique index to support `REFRESH ... CONCURRENTLY`; add one on the full group-by key tuple.

---

## 5. Indexing Strategy

Indexes are chosen for the two query shapes that dominate Phase 1: spatial filtering (viewport + proximity) and time-bounded attribute aggregation.

**Spatial (GIST).** Every geometry column is indexed:

- GIST on `hdb_blocks.geom` and `hdb_blocks.geom_svy21` (the SVY21 index serves KNN and `ST_DWithin`; the 4326 index serves viewport `ST_Intersects` and tile generation).
- GIST on `geom`/`geom_svy21` for `mrt_stations`, `bus_stops`, `schools`, `bto_projects`.
- GIST on `planning_areas.geom` for point-in-polygon resolution.

**Attribute (B-tree).** On `hdb_blocks`: `town`, `planning_area_id`, and `lease_commencement_year` (the indexable proxy for lease age, since `remaining_lease_years` is date-derived and lives in a view / refreshed stats column). On the partitioned `hdb_transactions`: `block_id`, `flat_type`, and `psf` (generated), plus the partition key handles time. A composite `(block_id, transaction_month)` supports the per-block time series.

**Proximity (B-tree).** On `block_proximity`: `nearest_mrt_distance_m`, `schools_within_1km`, etc., so accessibility filters are range scans.

**Composite for common filter combos.** The frequent combination is `town` + `flat_type` + price range. Because price lives in transactions and flat type spans both, the search path (Section 9) drives off `hdb_blocks` filtered attributes joined to `block_proximity`, with the transaction-derived price band resolved through `mv_block_monthly_stats`. Index `mv_block_monthly_stats` on `(block_id, flat_type)` and `(planning_area_id, flat_type, transaction_month)`.

**What we deliberately avoid:** functional indexes on raw lat/lng, and any `ST_Distance(...) < x` pattern (non-sargable). All radius logic uses `ST_DWithin` against the GIST-indexed SVY21 column.

---

## 6. Core Spatial Query Patterns

These are the reusable primitives the services compose. Stated as patterns rather than final SQL.

**Viewport fetch (map pan/zoom).** Bound features to the current map extent with a bounding-box intersection:
`WHERE geom && ST_MakeEnvelope(:minx,:miny,:maxx,:maxy, 4326)`.
This is index-assisted and is also the basis of tile queries. Never fetch a layer unbounded.

**Radius / "within X metres" (accessibility).** Always metric and index-assisted:
`WHERE ST_DWithin(b.geom_svy21, t.geom_svy21, :metres)`.
Used to build proximity counts and ad-hoc "blocks near this station" queries.

**Nearest neighbour (KNN).** Use the GIST distance operator for index-ordered nearest lookups:
`ORDER BY b.geom_svy21 <-> s.geom_svy21 LIMIT 1` (per block, via `LATERAL`).
This populates `nearest_*` columns in `block_proximity`. The `<->` operator uses the GIST index; ordinary `ST_Distance` in `ORDER BY` does not.

**Point-in-polygon (town/planning-area resolution).** At ingest, resolve each block's `planning_area_id`:
`WHERE ST_Contains(pa.geom, b.geom)`.
Stored as an FK so the dashboard never recomputes containment.

**Proximity-table build (batch).** `block_proximity` is rebuilt with one `LATERAL` join per reference layer (nearest MRT, nearest bus, nearest future MRT) plus `ST_DWithin` count subqueries for schools/bus within radius. Run as a single Celery task after reference data changes; targets full rebuild in seconds for ~12k blocks given the GIST indexes.

**Time-bounded aggregation.** Analytics queries always carry a `transaction_month` range so partition pruning applies, then group and use `percentile_cont` for medians.

---

## 7. Vector Tile Pipeline (Map Performance Core)

Rendering ~12k HDB blocks, ~5k bus stops, plus MRT/schools as GeoJSON over the wire is the classic way to make a map feel broken. Phase 1 serves **Mapbox Vector Tiles generated in PostGIS**.

**Generation.** A tile endpoint `GET /tiles/{layer}/{z}/{x}/{y}.pbf` runs a query that:

1. Computes the tile envelope with `ST_TileEnvelope(z,x,y)` (Web Mercator).
2. Clips and projects features with `ST_AsMVTGeom(ST_Transform(geom,3857), envelope, ...)`.
3. Emits the tile with `ST_AsMVT(...)`, attaching a small attribute payload (e.g. block id, flat-type availability flag, a precomputed style bucket) so the client can style without extra round-trips.

**Zoom-dependent generalization.** Low zooms (Singapore-wide) serve aggregated/simplified representations — bus stops and blocks are clustered or dropped below a zoom threshold; high zooms serve full per-feature geometry. This keeps every tile small regardless of layer density.

**Caching.** Tiles are cached in Redis keyed by `layer:z:x:y`, with a content version stamp in the key. A data refresh bumps the version, which cleanly invalidates affected layers without per-key deletion. Static reference layers (MRT, schools, planning areas) cache for long TTLs; block/transaction-derived layers cache shorter.

**Client integration note.** React Leaflet does not render MVT natively. Phase 1 uses the `Leaflet.VectorGrid` plugin (protobuf tiles) layered over OneMap raster base tiles. This is flagged as a known integration point: if MVT styling control proves limiting, the fallback is viewport-bounded GeoJSON with server-side clustering for the densest layers — but MVT is the primary path and the reason the tile endpoint exists.

---

## 8. Data Ingestion Architecture

Ingestion is a set of idempotent, validated, scheduled pipelines built on Pandas/GeoPandas, orchestrated by Celery, writing to PostGIS through staging tables.

**Shape of every pipeline.** Extract from source → normalize to a common frame in GeoPandas → set CRS to 4326 → validate and repair geometry (`ST_IsValid` / `ST_MakeValid`, drop empties) → load into a `staging_*` table → `MERGE`/upsert into the target on its natural key → resolve derived fields (planning area FK, proximity) → refresh dependent materialized views.

**Idempotency.** Natural keys (`postal_code` / `block_number`+`street_name`, `bus_stop_code`, `station_name`, `school_id`) carry unique constraints; loads are upserts, so re-running a pipeline never duplicates rows. Staging-then-merge means a failed run leaves the live table untouched.

**Source-specific notes.**

- **OneMap** — geocodes HDB addresses to lat/lng (build `geom` from result), supplies planning-area polygons, and serves the raster base tiles consumed directly by the client. Respect rate limits; cache geocode results so re-ingest doesn't re-hit the API.
- **HDB resale transactions / property info / existing buildings** — the trickiest join is matching a transaction's address text to a `block_id`. Normalize block/street strings and match on `postal_code` where available; quarantine unmatched rows in a `staging_unmatched_transactions` table for inspection rather than dropping them silently.
- **LTA DataMall** — MRT stations, bus stops, bus routes. `stop_sequence` preserved per service for later graph construction.
- **MOE school directory** — geocode via OneMap where coordinates aren't provided.
- **MRT expansion / BTO** — future stations and projects; stored now, scored later.

**Scheduling.** Transactions refresh monthly (new partition month); reference layers refresh on a slower cadence or on demand. Any reference-layer change triggers a `block_proximity` rebuild; any transaction load triggers materialized-view refresh.

**Validation gates.** Each run records row counts in/out, unmatched count, and invalid-geometry count. A run that exceeds an anomaly threshold (e.g. sudden drop in matched rows) is flagged rather than published.

---

## 9. HDB Filtering as Spatial + Attribute Queries

The filter panel is the product's primary interaction, so its query path is designed explicitly rather than left to an ORM.

Filters fall into three classes, each resolved by the cheapest mechanism:

- **Block attributes** (`town`, `planning_area`, `flat_type`, `floor_area`, `storey_range`, lease fields) → indexed B-tree predicates on `hdb_blocks` (and `flat_type`/`floor_area` against the transaction/stats layer).
- **Price / PSF bands** (`min/max price`, `min/max psf`) → resolved against `mv_block_monthly_stats` for the selected flat type over a recent window, so the price band reflects current market stats rather than scanning raw transactions per request.
- **Accessibility** (`distance to MRT`, `distance to bus stop`, `schools within radius`) → pure numeric comparisons against the precomputed `block_proximity` table. No live spatial computation on the request path.

**Composition.** A search request is: viewport bounding-box filter (`geom &&` envelope) `AND` block-attribute predicates `AND` proximity-table predicates `AND` price band from the stats MV. Because each clause hits an index and the heavy spatial work is precomputed, even broad searches return quickly. The viewport bound also means the result set is naturally capped to what the map can show.

**Result contract.** `/properties/search` returns lightweight block summaries (id, location, headline stats) plus a tile-style hint, not full transaction histories — detail is fetched on selection via `/properties/{id}`. This keeps the list/map in sync with the tile layer and avoids over-fetching.

---

## 10. Analytics Dashboard Data Layer

The dashboard is a read-only consumer of the materialized views from Section 4.5, fronted by Redis.

**Estate-level** (`/analytics/estate/{estate}`) and **block-level** (`/analytics/block/{block}`) endpoints read `mv_estate_monthly_stats` / `mv_block_monthly_stats` and shape them for Recharts:

- *PSF over time* and *transaction volume over time* → time series straight from the monthly MV.
- *PSF by flat type* → group by `flat_type` over the selected window.
- *PSF by lease age* → join stats to the computed remaining-lease value (view expression or refreshed stats column) bucketed.
- *Price vs MRT distance* → join stats to `block_proximity.nearest_mrt_distance_m`; this scatter is essentially free because proximity is precomputed.
- *Estate growth comparison* → period-over-period change derived from the estate MV.

Medians use `percentile_cont(0.5)` computed at MV-refresh time, not per request. Every endpoint response is cached in Redis keyed by `(scope, id, flat_type, window)` and invalidated when the underlying MV refreshes (version-stamped, same scheme as tiles).

---

## 11. Caching Strategy (Redis)

Redis serves three distinct workloads, each with its own keyspace and invalidation rule:

- **Vector tiles** — `tile:{layer}:{z}:{x}:{y}:{version}`. Highest hit rate; bytes served directly. Invalidated by version bump on data refresh.
- **Analytics responses** — `analytics:{scope}:{id}:{flat_type}:{window}:{version}`. Invalidated when the relevant MV refreshes.
- **Geocode results** — `geocode:{normalized_address}`. Long TTL; protects the OneMap rate limit across ingest re-runs.

A single `data_version` registry (per layer/domain) drives invalidation by inclusion in cache keys, avoiding fragile per-key deletion. Cache warming for the most-viewed tiles and top estates runs after each refresh so the first user request isn't a cold miss.

---

## 12. API Surface (Phase 1)

Only the endpoints needed for the Phase 1 foundation, plus the tile endpoint that the original TDD's API list omitted but the architecture requires.

| Method & path | Purpose | Backing |
|---|---|---|
| `GET /tiles/{layer}/{z}/{x}/{y}.pbf` | Vector tiles for each map layer | `ST_AsMVT` + Redis |
| `GET /properties/search` | Filtered block search (attribute + spatial + proximity) | `hdb_blocks` × `block_proximity` × stats MV |
| `GET /properties/{id}` | Block detail + recent transactions | `hdb_blocks`, partitioned `hdb_transactions` |
| `GET /analytics/estate/{estate}` | Estate-level metrics & series | `mv_estate_monthly_stats` + Redis |
| `GET /analytics/block/{block}` | Block-level metrics & series | `mv_block_monthly_stats` + Redis |
| `GET /reference/{layer}` *(optional)* | Bounded reference features when not tiled | bounded GeoJSON |

The scoring/commute/forecasting endpoints from the full TDD (`/commute/*`, `/couple-mode/*`, `/appreciation/*`, `/future-*`, `/dream-home-finder`) are intentionally absent here; they are later phases. The schema and proximity/MV layers above are designed so they attach without migration churn.

---

## 13. Performance Targets

Concrete budgets to validate the foundation against, so "map performance first" is measurable rather than aspirational.

- **Tile response:** p95 < 50 ms cached, < 250 ms cold for any layer/zoom.
- **Map interaction:** smooth pan/zoom across Singapore at all zooms with no layer exceeding a per-tile feature budget (enforced by zoom-based generalization).
- **`/properties/search`:** p95 < 300 ms for a typical multi-filter query within a viewport.
- **Analytics endpoint:** p95 < 150 ms cached, < 800 ms cold (MV-backed).
- **`block_proximity` full rebuild:** seconds, not minutes, for ~12k blocks.
- **Monthly transaction ingest + MV refresh:** completes within a single off-peak job window.

---

## 14. Revised Phase 1 Build Sequence

The original order is sound; this refines it so each step lands on a geospatial-ready substrate.

1. **PostGIS-enabled database + schema.** Enable PostGIS, create spatial tables with dual geometry columns, generated columns, transaction partitioning, and all GIST/B-tree indexes (Sections 3–5). Stand up `planning_areas`, `block_proximity` (empty), and the two MVs.
2. **Ingestion pipelines.** Build the staging→merge pipelines with geometry validation and idempotent upserts (Section 8). Order: planning areas → reference layers (MRT, bus, schools, future MRT, BTO) → HDB blocks (geocode, resolve planning-area FK) → transactions. Then build `block_proximity` and refresh MVs.
3. **Tile endpoint + interactive map.** Implement `ST_AsMVT` tiles with Redis caching and zoom generalization; wire React Leaflet + VectorGrid over OneMap base tiles (Section 7).
4. **HDB filters.** Implement `/properties/search` composing viewport + attribute + proximity + price-band predicates (Section 9).
5. **Analytics dashboard.** Implement estate/block analytics endpoints off the MVs with Redis caching and the Recharts shapes (Section 10).

A useful checkpoint after step 2: the database can already answer every Phase 1 spatial question (nearest MRT, blocks near X, estate medians) via SQL before any frontend exists — proving the foundation independently of the UI.

---

## 15. Open Questions and Risks

- **HDB address ↔ block matching.** The transaction-to-block join is the highest-risk ingestion step; quality depends on postal-code availability and string normalization. Mitigation: quarantine unmatched rows and report match rate per run.
- **OneMap rate limits and token lifecycle.** Geocoding volume on first full ingest is significant; caching and backoff are required. Confirm token refresh handling.
- **MVT styling control in Leaflet.** `Leaflet.VectorGrid` is less actively maintained than MapLibre's vector stack. If styling/interaction needs outgrow it, evaluate MapLibre GL with OneMap tiles as a fallback — flagged now so it doesn't surprise later.
- **Single vs split MRT tables.** Recommendation is one `mrt_stations` table with a `status` flag; confirm before building ingestion, as it affects proximity columns and tile layers.
- **Median accuracy at low volume.** Block-month cells with few transactions yield noisy medians; the dashboard should surface `txn_count` alongside medians so thin data is visible rather than misleading.
- **Generated `geom_svy21` storage cost.** Doubling geometry storage is a deliberate trade for query speed and correctness; acceptable at Singapore's data scale but noted.

---

*Scope note: this document covers Phase 1 (foundation) only. Commute optimization, scoring engines, appreciation modelling, and forecasting build on these primitives in later phases and are out of scope here.*

