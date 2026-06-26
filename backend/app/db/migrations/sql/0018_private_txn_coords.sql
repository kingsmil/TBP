-- Lat/lon for private (URA) transactions so they can be shown on the map.
-- URA provides SVY21 (EPSG:3414) x/y per project; app.services.private_property
-- converts them to WGS84 (EPSG:4326) via PostGIS ST_Transform at persist time.
-- Nullable — URA omits coordinates for some projects.

ALTER TABLE private_transactions ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION;
ALTER TABLE private_transactions ADD COLUMN IF NOT EXISTS lon DOUBLE PRECISION;

CREATE INDEX IF NOT EXISTS idx_priv_txn_latlon ON private_transactions(lat, lon);
