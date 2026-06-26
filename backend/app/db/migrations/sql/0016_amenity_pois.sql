-- OneMap-sourced amenity POIs (parks, hawker centres, hospitals, sports, etc.),
-- seeded once + refreshed monthly (app.data.amenities), so we don't re-pull them
-- from the OneMap Themes API on every server restart. Schools are not stored
-- here — they come from our existing reference layer. Reference data, no FK.

CREATE TABLE IF NOT EXISTS amenity_pois (
    id         SERIAL PRIMARY KEY,
    amenity    TEXT NOT NULL,           -- amenity key (parks, hawker, hospitals, …)
    name       TEXT NOT NULL,
    lat        DOUBLE PRECISION NOT NULL,
    lon        DOUBLE PRECISION NOT NULL,
    address    TEXT,
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_amenity_pois_key ON amenity_pois(amenity);
