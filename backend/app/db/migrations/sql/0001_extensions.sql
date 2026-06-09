-- 0001 Extensions
-- PostGIS is a first-class component from day one.
CREATE EXTENSION IF NOT EXISTS postgis;

-- Migration bookkeeping (used by app.db.migrate).
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     text PRIMARY KEY,
    applied_at  timestamptz NOT NULL DEFAULT now()
);
