# Data sources

What is **official data** and what is **estimated**, per feature. Secrets are
never committed — all credentials come from environment variables (`.env`,
gitignored).

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

## Private Property transactions (Feature 2 — official, with mock fallback)
- **Source:** URA Private Residential Property Transactions API (official; rolling
  ~60-month window).
- **Credentials (env, never hardcoded):** `URA_ACCESS_KEY`, `URA_TOKEN_URL`,
  `URA_API_URL`. When absent, the app runs in mock mode
  (`PRIVATE_PROPERTY_MOCK_MODE=true`) using bundled fixtures so dev/CI never
  break.
- **Caveat (shown in UI):** URA caveat data may not include every transaction —
  caveat lodging is not mandatory, so some resale/subsale deals are missing.
- *(Implemented in the Private Property feature branch.)*

## Auth / saved user state (Feature 1)
- **Source:** the app's own PostGIS database (`users`, `saved_locations`,
  `user_preferences`). No third-party identity provider.
- **Dev/prod:** controlled by `AUTH_REQUIRED` (see README). Personal data is only
  persisted for authenticated users.
