# Estate Finder (HDB Match)

A **map-first geospatial analytics platform** that helps Singapore HDB buyers
decide *where* to live — by affordability, accessibility, commute fit, and
future appreciation potential. It is a spatial-query + analytics + scoring
engine with a map on top, **not** a property-listing portal. PostGIS is a
first-class component from day one.

> Heuristic decision aid only — scores and forecasts are **not financial advice**.

---

## Table of contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [Running without a database (mock mode)](#running-without-a-database-mock-mode)
- [Testing](#testing)
- [API reference](#api-reference)
- [Coordinate reference systems](#coordinate-reference-systems)
- [Notes & limitations](#notes--limitations)

---

## Features

Built in five phases. Every backend feature is covered by tests.

**Phase 1 — Geospatial foundation**
- PostGIS schema with dual geometry (WGS84 + SVY21), month-partitioned
  transactions, precomputed proximity, and analytics materialized views.
- Idempotent data ingestion with geometry validation and point-in-polygon
  resolution of planning areas (mock/sample data included).
- Interactive Leaflet map over OneMap tiles, served by a PostGIS
  `ST_AsMVT` vector-tile endpoint.
- HDB filters: viewport + attributes + proximity + price/PSF band.
- Analytics dashboard: median/avg PSF & price, volume, PSF-over-time,
  PSF-by-flat-type, PSF-by-lease-age, price-vs-MRT-distance.

**Phase 2 — Accessibility & comparison**
- 0–100 accessibility sub-scores for MRT, future MRT, bus, and schools, plus a
  weighted combined score (block- and estate-level).
- Estate comparison: PSF, growth, lease profile, and accessibility side by side.

**Phase 3 — Commute & lifestyle**
- Commute engine behind a provider interface: **OneMap public-transport
  routing** in production, with a deterministic offline fallback.
- Commute optimizer + green/yellow/red heatmap (weekly/monthly burden, score).
- Couple mode: combined burden + fairness score + recommended estates.
- Lifestyle score: weighted blend of commute, transport, schools, affordability
  (unsupplied factors are excluded, not averaged).

**Phase 4 — Appreciation & dream home**
- Appreciation engine: growth, liquidity, lease, accessibility, future MRT,
  and future-supply pressure → score + confidence level + risk level.
- Future MRT impact and future BTO supply analysis.
- Dream Home Finder: hard requirements + a match score across commute,
  lifestyle, appreciation, and budget fit.

**Active listings (HDB Flat Portal)**
- Live resale listings ingested from the official HDB Flat Portal public API,
  matched to blocks (postal-code exact, then normalized block+street) — one
  block holds 0..N listings. `make listings-load`, `GET /blocks/{id}/listings`,
  and an "On the market now" section in the block detail panel.

**Phase 5 — Recommendations & forecasting**
- Recommendation engine: composite ranking with human-readable reasons.
- Undervalued estate detector: peer model (PSF vs accessibility) flags estates
  priced below comparable peers with positive growth.
- Advanced forecasting: least-squares PSF trend with a confidence band.

---

## Tech stack

**Backend**
- Python 3.10+, FastAPI, Uvicorn, Pydantic
- PostgreSQL + **PostGIS**, SQLAlchemy 2 + GeoAlchemy2, psycopg 3
- Redis (caching), Celery (background jobs — proximity rebuild, MV refresh)
- NumPy / Pandas for analytics and forecasting
- A dependency-free pure-Python geospatial core (SVY21 projection, distance,
  KNN, point-in-polygon) that mirrors PostGIS semantics and runs anywhere

**Frontend**
- React + Vite + TypeScript, TailwindCSS
- React Leaflet + OneMap tiles, `@tanstack/react-query`, Recharts
- Vitest + Testing Library

**Data sources** (production)
- OneMap (tiles, geocoding, routing, planning areas)
- HDB resale transactions & property info; LTA DataMall (MRT, bus); MOE schools;
  MRT expansion & BTO data

**Deployment targets**
- Frontend: Vercel · Backend: Railway/Render · Database: Supabase PostgreSQL

---

## Architecture

A clean, layered, storage-agnostic design:

```
core (geo, models, CRS)        pure Python, no deps, fully tested
  └── repositories             Repository interface
        ├── memory             in-memory impl (tests / mock mode)
        └── postgis            SQLAlchemy + PostGIS impl (production)
  └── services                 search, analytics, accessibility, comparison,
                               commute (+OneMap), lifestyle, appreciation,
                               future_dev, dream_home, recommendation, forecasting
  └── api (FastAPI)            thin HTTP layer over the services
```

Services depend only on the `Repository` interface, so switching from the
in-memory store to PostGIS is a configuration change. See
[`docs/HDB-Match-Geospatial-Architecture-Phase1.md`](docs/HDB-Match-Geospatial-Architecture-Phase1.md)
for the full geospatial design (CRS strategy, indexing, tiling, ingestion).

---

## Repository layout

```
estate-finder/
├── docker-compose.yml          # PostGIS + Redis for local dev
├── Makefile                    # developer commands
├── docs/                       # architecture design doc
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── schema/manifest.py  # single source of truth for the data model
│       ├── db/migrations/sql/  # ordered PostGIS migrations (real DDL)
│       ├── db/migrate.py        # SQL migration runner
│       ├── db/maintenance.{sql,py}  # proximity rebuild + MV refresh
│       ├── core/                # geo engine: crs, geo, models
│       ├── repositories/        # base / memory / postgis
│       ├── services/            # analytics, accessibility, commute, scoring …
│       ├── data/                # mock data + ingestion + seed
│       └── api/                 # FastAPI app, deps, schemas, tiles
│       └── tests/               # 146 tests (stdlib unittest / pytest)
└── frontend/
    └── src/
        ├── lib/                 # api client + pure utils (tested)
        └── components/          # Map, filters, charts, panels (tested)
```

---

## Quick start

Requires Docker, Python 3.10+, and Node 18+.

### Docker-hosted app with live data.gov.sg resale data

```bash
# Start PostGIS, Redis, FastAPI, and Vite in Docker.
make docker-up

# Load live HDB resale transactions from data.gov.sg into PostGIS.
# Default imports the first 5,000 records; use DATA_GOV_LIMIT=all for all rows.
make live-load
```

Open:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`

The resale transaction feed is live from data.gov.sg. Because that dataset does
not include coordinates, the loader geocodes unique block/street addresses with
OneMap search before inserting blocks into PostGIS. If OneMap rate-limits
unauthenticated geocoding, set `ONEMAP_TOKEN` or lower `DATA_GOV_LIMIT`.

### Host-run development

```bash
# 1. Database (PostGIS) + Redis
cp .env.example .env
make db-up

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ..
make db-migrate        # apply PostGIS migrations
make seed              # load sample data (swap for real ingestion later)
make backend           # FastAPI at http://localhost:8010  (/docs for Swagger)

# 3. Frontend (new terminal)
make frontend-install
make frontend-dev      # Vite dev server at http://localhost:5173
```

To enable real OneMap public-transport routing, add a token to `.env`:

```
ONEMAP_TOKEN=your_token_here
```

Without it, the commute engine uses the built-in heuristic estimator.

---

## Running without a database (mock mode)

The API auto-falls back to a **seeded in-memory repository** when
`DATABASE_URL` is unset, so you can run the backend and frontend with no
Postgres at all:

```bash
cd backend && python -m app.run_server
```

The map's vector-tile endpoint requires PostGIS; in mock mode the map uses the
`/reference/{layer}` GeoJSON endpoints instead.

---

## Testing

```bash
# Dependency-free core suite (146 tests, stdlib only — runs anywhere)
make test-core

# Full backend suite with pytest (after pip install)
make test

# Frontend unit/component tests (Vitest)
make frontend-test
```

The pure-Python core, all scoring/analytics logic, data transforms, and API
service layer are unit-tested. Frontend tests cover pure utilities and core
components.

---

## API reference

Interactive docs at `http://localhost:8010/docs`. Summary:

| Method & path | Description |
|---|---|
| `GET /health` | Service status + mode (postgis/mock) |
| `GET /properties/search` | Filtered block search (viewport + attrs + proximity + price) |
| `GET /properties/{id}` | Block detail + recent transactions + analytics |
| `GET /analytics/estate/{id}` | Estate metrics & time series |
| `GET /analytics/block/{id}` | Block metrics & time series |
| `GET /accessibility/block/{id}` | MRT/bus/school + combined scores |
| `GET /accessibility/estate/{id}` | Estate-level accessibility |
| `GET /comparison/estates` | Side-by-side estate comparison |
| `GET /reference/{layer}` | GeoJSON for mrt/future_mrt/bus_stops/schools/bto |
| `GET /tiles/{layer}/{z}/{x}/{y}.pbf` | PostGIS vector tiles (ST_AsMVT) |
| `POST /commute/optimize` | Rank blocks by commute burden |
| `POST /commute/heatmap` | Per-block commute fit (green/yellow/red) |
| `POST /couple-mode/optimize` | Combined burden + fairness for two people |
| `POST /lifestyle/block/{id}` | Lifestyle score for a block |
| `GET /appreciation/{id}` | Appreciation score + confidence + risk |
| `GET /future-mrt/{id}` | Nearest future MRT + transport growth score |
| `GET /future-supply/{id}` | Nearby future BTO supply + risk |
| `POST /dream-home-finder` | Rank blocks against the user's requirements |
| `GET /forecast/block/{id}` | PSF projection for a block |
| `GET /forecast/estate/{id}` | PSF projection for an estate |
| `GET /undervalued` | Estates priced below accessibility-implied peers |
| `POST /recommendations` | Composite block recommendations with reasons |

---

## Coordinate reference systems

- **EPSG:4326 (WGS84)** — canonical geometry, display & interchange.
- **EPSG:3414 (SVY21)** — generated column for all metric maths (distance,
  buffer, KNN, area). Singapore's national projection.
- **EPSG:3857 (Web Mercator)** — vector-tile output only.

Rule: measuring distance/area → SVY21; rendering/exporting → WGS84.

---

## Notes & limitations

- The repository ships with **mock/sample data**; wire the real OneMap/HDB/LTA/
  MOE pipelines into `backend/app/data/` to load production data.
- Commute uses OneMap routing when `ONEMAP_TOKEN` is set, otherwise a heuristic.
- Scores, appreciation, and forecasts are heuristic decision aids and are
  **not financial advice**.
