-- Active listings can now represent resale or rental listings.
ALTER TABLE hdb_active_listings
    ADD COLUMN IF NOT EXISTS listing_type TEXT NOT NULL DEFAULT 'resale';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'hdb_active_listings_pkey'
          AND conrelid = 'hdb_active_listings'::regclass
    ) THEN
        ALTER TABLE hdb_active_listings DROP CONSTRAINT hdb_active_listings_pkey;
    END IF;
END $$;

ALTER TABLE hdb_active_listings
    ADD CONSTRAINT hdb_active_listings_pkey PRIMARY KEY (listing_type, listing_id);
