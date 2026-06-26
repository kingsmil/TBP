# Data sources

What is **official data** and what is **estimated**, per feature. Secrets are
never committed — all credentials come from environment variables (`.env`,
gitignored).

## Amenity POIs — parks, hawker, hospitals, sports, community, libraries (OneMap)
- **Source:** OneMap Themes API (official reference data). Schools come from our
  own reference layer, not this.
- **Seeding / refresh:** fetched once into `amenity_pois` (migration `0016`) by
  `app.data.amenities` and refreshed **monthly** by the scheduler, so the map
  doesn't re-hit OneMap on every restart. Falls back to a live (24h-cached)
  fetch when the table is empty / no DB. CLI: `python -m app.data.amenities`.

## Property images (detail view)
Layered fallback in `app.services.images`, served via `GET /image/property`
(keeps tokens/keys server-side, in-process cached):
1. **Real HDB listing photo** — `https://static.homes.hdb.gov.sg/` + the block's
   active-listing `photo_path` (HDB Flat Portal). Only for blocks with a current
   listing.
2. **Google Street View Static** — real façade from lat/lon. Optional; needs
   `GOOGLE_MAPS_API_KEY` (cost applies). Absent → skipped.
3. **OneMap Static Map** — free location thumbnail for any lat/lon (token managed
   server-side). The always-available fallback.

## HDB resale transactions & blocks (existing)
- **Source:** data.gov.sg HDB resale datasets + OneMap geocoding (official).
- **Status:** official transaction records. Geocoded coordinates are official
  (OneMap).
- **Ingest:** `backend/app/data/` (`data_gov_sg.py`, `ingest.py`, `seed_live.py`).

## BTO sales exercises & application rates (existing)
- **Source:** HDB Flat Portal
  `https://services-homes.hdb.gov.sg/sales/files/apprates/BTO{YYYYMM}.json`
  (official) + BTO selling-price ranges from data.gov.sg (official).
- **Status:** official. Refreshed monthly in the background.
- **Ingest:** `backend/app/data/bto.py`.

## Estimated BTO Resale Availability (Feature 3 — **estimated**)
- **Sources (layered):**
  1. `backend/app/data/manual/bto-project-mop-seed.json` — manually curated
     completion / key-collection dates (official where cited via `source_url`).
  2. Launch metadata from the BTO ingest above (official launch dates +
     classification) → completion **estimated** as launch + ~42 months.
- **Status:** **ESTIMATE.** The resale-eligible date is derived (anchor + MOP),
  never a confirmed date. Confidence (`HIGH`/`MEDIUM`/`LOW`) and `source_type`
  are stored per row so the UI can explain reliability.
- **Rules / maintenance:** `docs/BTO_MOP_ESTIMATION_RULES.md`.
- **Future official sources** (drop-in, same schema): data.gov.sg *HDB Property
  Information* (`year_completed` per block) and *HDB Completion Status*
  (town/estate completion). Set `source_type` to
  `DATA_GOV_HDB_PROPERTY_INFO` / `DATA_GOV_COMPLETION_STATUS` when added.
- **Coordinates (lat/lon):** geocoded by `app.data.bto_mop` so projects show on
  the map — OneMap public search by project name, with a town-centroid fallback
  (computed from `hdb_blocks`) + small deterministic jitter so same-town projects
  don't stack. Approximate by nature; nullable when neither resolves.

## Private Property transactions (Feature 2 — official, with mock fallback)
- **Source:** URA Private Residential Property Transactions API (official; rolling
  ~60-month window).
- **Credentials (env, never hardcoded):** `URA_ACCESS_KEY`, `URA_TOKEN_URL`,
  `URA_API_URL`. When absent, the app runs in mock mode
  (`PRIVATE_PROPERTY_MOCK_MODE=true`) using bundled fixtures so dev/CI never
  break.
- **Caveat (shown in UI):** URA caveat data may not include every transaction —
  caveat lodging is not mandatory, so some resale/subsale deals are missing.
- **Adapter:** `backend/app/services/private_property/` — `ura_client.py` (daily
  token + 4 rolling batches, SWR-cached), `normalise.py` (raw → normalised
  `PrivateTransaction`), `fixtures.py` (mock data), `service.py` (filters +
  median/avg/min/max PSF + monthly trend + project search). Endpoints
  `GET /private/transactions`, `GET /private/projects`. UI: a third
  **Private property** mode in the chooser → `PrivateDashboard`.
- **Property types:** `CONDO`, `APARTMENT`, `EC`, `LANDED`, `STRATA_LANDED`
  (landed vs strata-landed disambiguated by URA `typeOfArea`). Sale types:
  `NEW_SALE`, `RESALE`, `SUB_SALE`.
- **Seeding / refresh:** pulled once into `private_transactions` (migration
  `0015`) by `app.data.ura` and refreshed **monthly** by the background
  scheduler — so URA is not called per request or per restart. SQL-side
  filtering/aggregation via `private_property/store.py`. Daily URA token is
  auto-renewed in `ura_client`.
- **Coordinates (lat/lon):** URA gives SVY21 (EPSG:3414) x/y per project;
  converted to WGS84 (EPSG:4326) via PostGIS `ST_Transform` at persist time
  (migration `0018`). ~80% of transactions have coordinates (URA omits them for
  some projects); the rest have no map pin.

## Auth / saved user state (Feature 1)
- **Source:** the app's own PostGIS database (`users`, `saved_locations`,
  `user_preferences`). No third-party identity provider.
- **Dev/prod:** controlled by `AUTH_REQUIRED` (see README). Personal data is only
  persisted for authenticated users.
