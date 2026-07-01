-- Active HDB sale/rental listings fetched from public listing sources.
-- One block has 0..N active listings (one per flat/unit on the market).
-- Agent contact columns are nullable: the public API only exposes them for
-- the rare agent-managed listing (contact is otherwise login-gated).
CREATE TABLE IF NOT EXISTS hdb_active_listings (
    listing_type TEXT NOT NULL DEFAULT 'resale',
    listing_id BIGINT NOT NULL,
    block_id INT NOT NULL REFERENCES hdb_blocks(block_id) ON DELETE CASCADE,
    block_number TEXT NOT NULL,
    street_name TEXT NOT NULL,
    postal_code TEXT NOT NULL DEFAULT '',
    town TEXT NOT NULL DEFAULT '',
    price DECIMAL(12, 2) NOT NULL,
    flat_type TEXT NOT NULL,
    floor_area_sqm DECIMAL(6, 2) NOT NULL,
    storey_range TEXT NOT NULL DEFAULT '',
    remaining_lease TEXT NOT NULL DEFAULT '',
    bedroom INT,
    bathroom INT,
    description TEXT,
    photo_path TEXT,
    agent_name TEXT,
    agent_phone TEXT,
    agent_email TEXT,
    agency_name TEXT,
    managed_by_agent BOOLEAN NOT NULL DEFAULT FALSE,
    last_updated TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (listing_type, listing_id)
);

-- Quick lookup of all active listings when viewing a block.
CREATE INDEX IF NOT EXISTS idx_active_listings_block_id ON hdb_active_listings(block_id);
