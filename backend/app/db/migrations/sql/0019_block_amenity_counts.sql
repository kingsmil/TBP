-- 0019 Precomputed amenity counts per block (within 1 km), for the client's
-- "Lifestyle" score. The COUNTS are precomputed here; the user's per-amenity
-- WEIGHTS are applied at read time in the browser — so retuning weights needs no
-- recompute (only changing the radius does). Refreshed alongside the amenity
-- seed (app.data.amenity_counts), invoked by the monthly scheduler.

-- Give amenity_pois real geometry (+ metric SVY21) so the count is an indexed
-- spatial join instead of a full scan.
ALTER TABLE amenity_pois
    ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326)
        GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(lon, lat), 4326)) STORED;
ALTER TABLE amenity_pois
    ADD COLUMN IF NOT EXISTS geom_svy21 geometry(Point, 3414)
        GENERATED ALWAYS AS (ST_Transform(ST_SetSRID(ST_MakePoint(lon, lat), 4326), 3414)) STORED;
CREATE INDEX IF NOT EXISTS amenity_pois_geom_svy21_gist ON amenity_pois USING gist (geom_svy21);

-- One row per block: counts keyed by amenity (e.g. {"hawker":3,"parks":2,...}),
-- including "schools" merged in from block_proximity.
CREATE TABLE IF NOT EXISTS block_amenity_counts (
    block_id   bigint PRIMARY KEY REFERENCES hdb_blocks (block_id),
    counts     jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);
