# HDB Match — HomeOS

**An agentic, map-first decision platform for Singapore HDB buyers.**

HDB Match answers the question every Singaporean homebuyer actually asks —
*"Where should I live, and is this specific flat worth viewing?"* — by combining
a **PostGIS geospatial engine** with a **live multi-agent AI system** that
investigates blocks, streams its reasoning, and defends its shortlist in plain
English.

It is a spatial-query + analytics + scoring engine with a map and an agent on
top — **not** a listings portal.

> Heuristic decision aid only — scores and forecasts are **not financial advice**.

---

## Two ways to use it

| | **Explore** | **HomeOS (AI)** |
|---|---|---|
| **For** | Hands-on users who want to drive the map | Users who want an analyst to do the work |
| **How** | Filter, compare, and read analytics directly on the map | Describe your household in plain English; agents investigate for you |
| **Output** | Live charts, accessibility scores, estate comparisons | A ranked, evidence-backed shortlist you can interrogate |
| **Access** | Open to everyone | Subscription-gated |

Both modes read the **same underlying data and services** — HomeOS is the AI
orchestration layer over the analytics engine, not a separate product.

---

## The headline: HomeOS, a streaming multi-agent investigation

Type *"Family looking for a 4-room under 800k near primary schools and MRT"* and
HomeOS opens a **Case**. Five specialist agents then investigate each candidate
block and **stream their reasoning to the UI live** over Server-Sent Events —
you watch the analysis happen rather than waiting on a spinner.

```
ProfileAgent          parse the household description → structured buyer profile
   │
   ▼  (preference review: asks one clarifying question at a time if a
   │   high-impact dimension was never stated — commute, schools, risk…)
   │
   └── for each candidate block:
         MarketAgent      recent resale evidence, budget fit, confidence
         LocationAgent    MRT distance, schools, commute time, bus connectivity
         RiskAgent        appreciation, future MRT, future BTO supply pressure
         LifestyleAgent   blended livability score across transport/schools/cost
         QuestionsAgent   4–6 due-diligence questions to ask before viewing
   │
   ▼
   WorthViewingScorer    aggregates evidence → 0–100 score + verdict + reasons
   │
   ▼
   CaseDone              ranked shortlist lands on the map
```

After the shortlist appears, the Case stays **conversational**:

- **Ask** — *"Why Bishan over Tampines?"* streams an answer grounded only in the
  case's own evidence trace.
- **Refine** — answer a clarifying question and the relevant agents re-run.

### Agents that actually call tools

Each agent is a [Pydantic AI](https://ai.pydantic.dev/) `Agent` with a typed
output model and a set of **function-calling tools** — the same services that
power Explore mode. The LLM decides *when* and *how* to fetch data, rather than
being handed a static context blob:

| Agent | Tools it can call | Typed output |
|---|---|---|
| `profile` | — (pure NL parsing) | `HomeOSAvatar` |
| `market` | `get_transactions` | `MarketEvidence` |
| `location` | `get_proximity`, `get_commute`, `get_bus_routes` | `LocationEvidence` |
| `risk` | `get_appreciation`, `get_future_dev`, `get_accessibility` | `RiskEvidence` |
| `lifestyle` | `get_lifestyle_score` | `LifestyleEvidence` |
| `questions` | `get_transactions`, `get_proximity` | `AgentQuestions` |

Because tools wrap the deterministic service layer, every number an agent cites
is reproducible and traceable — there is no hallucinated data path.

### Provider-agnostic, deterministic in CI

The model factory auto-detects its provider from the environment. Production
runs through the **Vercel AI Gateway** (one key, any underlying model); CI runs
against Pydantic AI's `TestModel` with **no key and no network**, so the full
agent pipeline is unit-tested deterministically. Swapping to Anthropic or
OpenRouter is a single environment variable.

---

## Geospatial foundation

HomeOS is only as good as the spatial engine beneath it. PostGIS is a
first-class component from day one.

- **Dual-geometry model** — every feature is stored in **WGS84 (EPSG:4326)** for
  display and **SVY21 (EPSG:3414)**, Singapore's national projection, as a
  generated column for all metric maths (distance, KNN, buffers, area).
- **Vector tiles** served straight from the database via `ST_AsMVT`, rendered on
  a Leaflet map over OneMap tiles.
- **Precomputed proximity** (block → nearest MRT / schools / bus) and
  **analytics materialized views** for fast PSF/price/volume aggregations.
- **Idempotent ingestion** with geometry validation and point-in-polygon
  resolution of planning areas.

### What it computes

- **Accessibility scoring** — 0–100 sub-scores for MRT, future MRT, bus, and
  schools, plus a weighted combined score at block and estate level.
- **Commute engine** — behind a provider interface: live **OneMap
  public-transport routing** in production, deterministic heuristic offline.
  Includes a commute optimizer, a green/yellow/red burden heatmap, and a
  **couple mode** (combined burden + fairness score).
- **Appreciation & risk** — growth, liquidity, lease decay, accessibility,
  future-MRT upside and future-BTO supply pressure → score + confidence + risk.
- **Forecasting** — least-squares PSF trend with a confidence band.
- **Undervalued detector** — flags estates priced below their accessibility-
  implied peers.
- **Recommendations & Dream Home Finder** — composite ranking with
  human-readable reasons against hard requirements.
- **Live resale listings** — ingested from the official HDB Flat Portal API and
  matched to blocks (postal-code exact, then normalized block+street), surfaced
  as "On the market now" with agent-outreach message drafting.

---

## Tech stack

**Backend**
- Python 3.12, FastAPI, Uvicorn, Pydantic v2
- **Pydantic AI** multi-agent framework with function-calling tools + SSE streaming
- PostgreSQL + **PostGIS**, SQLAlchemy 2 + GeoAlchemy2, psycopg 3
- NumPy / Pandas for analytics and forecasting
- A dependency-free pure-Python geospatial core (SVY21 projection, distance,
  KNN, point-in-polygon) that mirrors PostGIS semantics and runs anywhere

**Frontend**
- React 18 + Vite + TypeScript, TailwindCSS, Radix UI
- React Leaflet + OneMap tiles, Supercluster, `@tanstack/react-query`, Recharts
- Streaming agent pipeline UI consuming SSE
- Vitest + Testing Library

**Auth & billing**
- JWT (python-jose) + bcrypt, **Stripe Checkout + webhooks** for subscription
  lifecycle, gating AI mode behind an active subscription
- `AUTH_REQUIRED` flag to toggle gating for local development

**Infrastructure & delivery**
- Dockerized backend on **AWS EC2**, images in **ECR**
- **GitHub Actions** CI/CD: test → build → push → deploy via **SSM**, with
  database migration, materialized-view refresh, and a live-listings sync step
  baked into the pipeline
- Terraform / Bedrock / SageMaker scaffolding under `infrastructure/`

**Live data sources**
- **data.gov.sg** — HDB resale transactions, school directory
- **OneMap** — map tiles, geocoding, public-transport routing, planning areas
- **LTA DataMall** — MRT and bus network
- **HDB Flat Portal** — live resale listings

---

## Architecture

A clean, layered, storage-agnostic design — services depend only on a
`Repository` interface, so the in-memory store (tests / mock mode) and PostGIS
(production) are interchangeable by configuration.

```
core (geo, models, CRS)         pure Python, no deps, fully tested
  └── repositories              Repository interface
        ├── memory              in-memory impl (tests / mock mode)
        └── postgis             SQLAlchemy + PostGIS impl (production)
  └── services                  search, analytics, accessibility, comparison,
        │                       commute (+OneMap), lifestyle, appreciation,
        │                       future_dev, dream_home, recommendation, forecast
        │
  └── homeos                    the AI layer
        ├── framework           AgentSpec / ToolSpec, model factory, registry
        ├── tools               function-calling wrappers over services
        ├── agents              profile / market / location / risk / lifestyle / questions
        ├── pipeline            investigate_stream, refine_stream, chat_in_case
        ├── scoring             worth-viewing aggregation
        └── case_store          in-memory Case lifecycle + event log
  └── api (FastAPI)             thin HTTP/SSE layer + auth + Stripe
```

See [`docs/HDB-Match-Geospatial-Architecture-Phase1.md`](docs/HDB-Match-Geospatial-Architecture-Phase1.md)
for the full geospatial design and
[`FUNCTION_CALLING_IMPLEMENTATION.md`](FUNCTION_CALLING_IMPLEMENTATION.md) for the
agent tool-calling internals.

---

## Repository layout

```
.
├── docker-compose.yml          # PostGIS + Redis + backend + frontend for local dev
├── Makefile                    # developer commands
├── docs/                       # architecture + design docs
├── infrastructure/             # terraform, ec2, bedrock, sagemaker scaffolding
├── .github/workflows/          # CI/CD: deploy-backend, deploy-frontend, sync-listings
├── backend/
│   └── app/
│       ├── schema/manifest.py  # single source of truth for the data model
│       ├── db/migrations/sql/  # ordered PostGIS migrations (real DDL)
│       ├── core/               # pure-Python geo engine: crs, geo, models
│       ├── repositories/       # base / memory / postgis
│       ├── services/           # analytics, accessibility, commute, scoring …
│       ├── homeos/             # AI agent framework, tools, pipeline, case store
│       ├── data/               # live ingestion (data.gov.sg, OneMap, HDB Portal)
│       └── api/                # FastAPI app, auth + Stripe, tiles, SSE endpoints
└── frontend/
    └── src/
        ├── lib/                # api client, auth, SSE, pure utils (tested)
        └── components/         # Map, filters, charts, CasesPanel, PipelinePanel …
```

---

## Running it

Requires Docker Desktop, Python 3.12+, and Node 18+. Copy `.env.example` to
`.env` and fill in any keys you have (OneMap is the main one for live data).

### Option A — Docker (everything in containers)

```bash
make docker-up        # PostGIS + Redis + backend + frontend
make live-load        # load live HDB resale data into PostGIS
```
Frontend → `http://localhost:5173` · API/Swagger → `http://localhost:8000/docs`

### Option B — host-run (backend + frontend on your machine, DB in Docker)

```bash
make db-up                                   # PostGIS + Redis only
make db-migrate                              # apply PostGIS migrations
cd backend && python -m app.data.seed_live   # load 10 years of live HDB data (default)
make backend                                 # API/Swagger → http://localhost:8010/docs
make frontend-install                        # first time only: npm install
make frontend-dev                            # Vite → http://localhost:5173
```

### Mock mode (no database, no keys)

```bash
cd backend && python -m app.run_server       # seeded in-memory data
```
The API falls back to an in-memory repository when `DATABASE_URL` is unset. The
map uses `/reference/{layer}` GeoJSON instead of vector tiles (those need PostGIS).

### Data commands

```bash
make seed                                          # mock/sample data into PostGIS
cd backend && python -m app.data.seed_live         # live data, last 120 months (10y)
cd backend && python -m app.data.seed_live --months 24   # shorter window
make listings-load                                 # "on the market now" HDB listings
```

### OneMap (live commute routing + address geocoding)

Set credentials in `.env` and the backend auto-mints + refreshes its token
(3-day TTL) — no manual rotation needed:
```
ONEMAP_EMAIL=you@example.com
ONEMAP_PASSWORD=...
```
Register free at <https://www.onemap.gov.sg/apidocs/register>. A static
`ONEMAP_TOKEN` is still honoured if you prefer.

### Appreciation rankings

Ranks every region and block by 10-year price appreciation (CAGR) and stores it
(needs live PostGIS data):

```bash
cd backend && python -m app.analysis.build_rankings               # fast, CAGR-only (~1s)
cd backend && python -m app.analysis.build_rankings --with-score  # + composite score (bounded)
```
The backend also rebuilds these monthly in the background
(`RANKINGS_AUTO_REFRESH`, default on). Read them via `GET /rankings/regions`
and `GET /rankings/blocks`, or the **Info** tab in the UI.

---

## Run locally over HTTPS (share a link)

Serve the whole app from your machine behind a trusted public HTTPS URL — no
cloud deploy. Installs the tools it needs on first run:

```powershell
./deploy/serve.ps1        # install (if needed) + DB + backend + Caddy + tunnel
./deploy/stop.ps1         # stop it all  (-Db also stops the DB containers)
```

Prints a `https://*.trycloudflare.com` URL anyone can open. Set `CF_TUNNEL_NAME`
in `.env` for a stable URL on your own domain. Full guide:
[`deploy/local-https-tunnel.md`](deploy/local-https-tunnel.md).

---

## Testing

```bash
make test                          # full backend suite (pytest)
make test-core                     # dependency-free pure-Python core (runs anywhere)
make frontend-test                 # Vitest unit/component tests
cd frontend && npx tsc --noEmit    # frontend typecheck
```

The pure-Python core, all scoring/analytics/ranking logic, the agent pipeline
(via `TestModel`, no API key), the SSE event sequence, and the API service layer
are unit-tested. Frontend tests cover pure utilities and core components.

---

## API reference

Interactive docs at `/docs`. Selected endpoints:

| Method & path | Description |
|---|---|
| `GET /health` | Service status + mode (postgis/mock) |
| **HomeOS (AI)** | |
| `POST /homeos/investigate-stream` | Open a Case; stream the agent pipeline (SSE) |
| `GET /homeos/cases` · `GET /homeos/cases/{id}` | List / fetch full Case + trace |
| `POST /homeos/cases/{id}/chat` | Ask a question grounded in the Case evidence (SSE) |
| `POST /homeos/cases/{id}/refine` | Answer a clarifying question; re-run agents (SSE) |
| `POST /homeos/case-file/{block_id}` | Full evidence dossier for one block |
| **Auth & billing** | |
| `POST /auth/register` · `POST /auth/login` · `GET /auth/me` | JWT auth |
| `POST /stripe/checkout` · `POST /stripe/webhook` · `GET /stripe/status` | Subscriptions |
| **Geospatial & analytics** | |
| `GET /properties/search` | Filtered block search (viewport + attrs + proximity + price) |
| `GET /tiles/{layer}/{z}/{x}/{y}.pbf` | PostGIS vector tiles (`ST_AsMVT`) |
| `GET /reference/{layer}` | GeoJSON for mrt/future_mrt/bus_stops/schools/bto |
| `GET /analytics/estate/{id}` · `GET /analytics/block/{id}` | Metrics & time series |
| `GET /accessibility/block/{id}` · `/estate/{id}` | MRT/bus/school + combined scores |
| `GET /comparison/estates` | Side-by-side estate comparison |
| `POST /commute/optimize` · `/heatmap` | Commute burden ranking + heatmap |
| `POST /couple-mode/optimize` | Combined burden + fairness for two people |
| `POST /lifestyle/block/{id}` | Lifestyle score for a block |
| `GET /appreciation/{id}` · `/future-mrt/{id}` · `/future-supply/{id}` | Risk signals |
| `GET /forecast/block/{id}` · `/estate/{id}` | PSF projection with confidence band |
| `GET /undervalued` | Estates priced below accessibility-implied peers |
| `POST /recommendations` · `/dream-home-finder` | Composite ranking with reasons |
| `GET /blocks/{id}/listings` | Live resale listings for a block |
| **Score ranking & appreciation** | |
| `GET /score-ranking/fields` · `POST /score-ranking` | User-weighted property ranking (extensible factors) |
| `GET /rankings/regions` · `/rankings/blocks` | Precomputed 10-year appreciation rankings |

---

## Coordinate reference systems

- **EPSG:4326 (WGS84)** — canonical geometry, display & interchange.
- **EPSG:3414 (SVY21)** — generated column for all metric maths. Singapore's
  national projection.
- **EPSG:3857 (Web Mercator)** — vector-tile output only.

Rule: measuring distance/area → SVY21; rendering/exporting → WGS84.

---

## Notes & limitations

- Cases are held in memory for the session — there is no cross-refresh Case
  persistence by design.
- Commute uses OneMap routing when `ONEMAP_TOKEN` is set, otherwise a heuristic.
- Scores, appreciation, and forecasts are heuristic decision aids and are
  **not financial advice**.
