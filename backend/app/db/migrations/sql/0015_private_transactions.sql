-- Private (URA) residential transactions, seeded once + refreshed monthly in the
-- background (app.data.ura), so we don't re-pull ~137k rows from URA on every
-- server restart or client request. Reference data — no FK.

CREATE TABLE IF NOT EXISTS private_transactions (
    id               TEXT PRIMARY KEY,        -- normalised hash id (stable)
    project_name     TEXT,
    property_type    TEXT NOT NULL,           -- CONDO|APARTMENT|EC|LANDED|STRATA_LANDED
    sale_type        TEXT NOT NULL,           -- NEW_SALE|RESALE|SUB_SALE
    district         TEXT,
    planning_region  TEXT,                    -- CCR|RCR|OCR
    address          TEXT,
    sale_date        DATE NOT NULL,
    price            BIGINT NOT NULL,
    area_sqm         DOUBLE PRECISION,
    area_sqft        DOUBLE PRECISION,
    psf              DOUBLE PRECISION,
    tenure           TEXT,
    floor_range      TEXT,
    source           TEXT NOT NULL DEFAULT 'URA',
    fetched_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_priv_txn_saledate ON private_transactions(sale_date);
CREATE INDEX IF NOT EXISTS idx_priv_txn_type     ON private_transactions(property_type);
CREATE INDEX IF NOT EXISTS idx_priv_txn_sale     ON private_transactions(sale_type);
CREATE INDEX IF NOT EXISTS idx_priv_txn_district ON private_transactions(district);
CREATE INDEX IF NOT EXISTS idx_priv_txn_project  ON private_transactions(LOWER(project_name));
