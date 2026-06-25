# Estimated BTO Resale Availability — rules & maintenance

This document explains how the **Estimated BTO Resale Availability** feature
("Upcoming HDB Resale Supply" in the UI) computes its estimates, what the
confidence levels mean, and **what a human or AI agent must update** when HDB
changes policy or when better source data becomes available.

> **These are estimates, not confirmed resale dates.** Actual resale eligibility
> depends on each owner's legal completion date, physical occupation during the
> MOP, and prevailing HDB rules. The UI states this prominently and so must any
> derived feature.

## The calculation

For each project / estate group:

```
estimated_resale_eligible_date = anchor_date + MOP years
```

- **anchor_date** = the key-collection date if known, otherwise the estimated
  completion date. (HDB measures MOP from key collection / legal completion, so
  key collection is preferred when available.)
- **MOP years** is determined by the flat's classification (below).

Implemented in `backend/app/data/bto_mop.py` (pure, unit-tested functions:
`normalise_classification`, `mop_years`, `parse_partial_date`, `make_record`,
`build_estimates`).

## MOP policy (the part HDB can change)

| Classification | MOP (years) | Notes |
|---|---|---|
| `STANDARD` | 5 | Standard / "normal" flats |
| `UNCLASSIFIED` | 5 | Pre-2024 launches with no Plus/Prime label |
| `PLUS` | 10 | Plus model (introduced Oct 2024) |
| `PRIME` | 10 | Prime Location Public Housing |
| `PLH` | 10 | Legacy name for Prime Location Public Housing |
| `UNKNOWN` | 5 (default) | Classification not known → confidence is lowered |

The single source of truth is `CLASSIFICATION_MOP` in
`backend/app/data/bto_mop.py`. **If HDB changes the MOP for any model, edit that
map and this table in the same commit**, then re-run the rebuild (below).

**Excluded:** the Fresh Start Housing Scheme (20-year MOP) is **household-specific**
and is deliberately *not* modelled at the project level. Do not add it unless a
reliable project-level source exists.

## Confidence levels

| Level | Meaning |
|---|---|
| `HIGH` | Project-level completion / key-collection **month** is known (from the manual seed). |
| `MEDIUM` | Project-level completion **year** is known, but the month was estimated to January. |
| `LOW` | Only launch metadata is available; completion is estimated as launch + ~42 months. |

A seed entry may set `confidence` explicitly to override the automatic level.

## Data sources (layered, highest priority first)

1. **Manual seed** — `backend/app/data/manual/bto-project-mop-seed.json`.
   Authoritative; overrides automatic rows for the same
   `(project_name, town, flat_classification)`.
2. **Launch metadata** already ingested into `bto_application_rates` +
   `bto_exercises` (classification + launch date). Used to produce LOW-confidence
   rows for everything not in the seed.

Future sources (adapters can be added without changing the schema — set
`source_type` accordingly): `DATA_GOV_HDB_PROPERTY_INFO` (block/street/year_completed),
`DATA_GOV_COMPLETION_STATUS` (town/estate completion). See `docs/DATA_SOURCES.md`.

## How to update safely (humans & AI agents)

When HDB announces a completion / key-collection date, or you want to upgrade a
LOW-confidence row:

1. Edit `backend/app/data/manual/bto-project-mop-seed.json`. Add an object under
   `projects` following `_schema` in that file. Required: `project_name`, a
   `flat_classification`, and one of `estimated_completion_date` /
   `estimated_key_collection_date`. Prefer `estimated_key_collection_date` with a
   **month** (`YYYY-MM`) so the row becomes HIGH confidence. Set `source_url` and
   `last_verified_at`.
2. **Do not** invent precise dates. If you only know a year, write the year
   (`"2028"`) — the pipeline will correctly mark it MEDIUM.
3. Keep `(project_name, town, flat_classification)` unique — that tuple is the
   upsert key.
4. Validate + rebuild:
   ```bash
   cd backend
   ./.venv/Scripts/python.exe -m pytest tests/test_bto_mop.py -q   # validates the seed file
   ./.venv/Scripts/python.exe -m app.data.bto_mop                  # rebuild (needs DATABASE_URL)
   ```
   The seed file is validated on load (`validate_seed`); a malformed entry raises
   and aborts the rebuild rather than writing bad data.

The scheduler also rebuilds the estimates monthly after the BTO data refresh
(`backend/app/analysis/scheduler.py`), so seed edits go live on the next refresh
even without a manual rebuild.
