-- Extra read indexes for richer private-transaction filtering.

CREATE INDEX IF NOT EXISTS idx_priv_txn_region ON private_transactions(planning_region);
CREATE INDEX IF NOT EXISTS idx_priv_txn_floor ON private_transactions(floor_range);
CREATE INDEX IF NOT EXISTS idx_priv_txn_price ON private_transactions(price);
CREATE INDEX IF NOT EXISTS idx_priv_txn_psf ON private_transactions(psf);
CREATE INDEX IF NOT EXISTS idx_priv_txn_area_sqft ON private_transactions(area_sqft);
CREATE INDEX IF NOT EXISTS idx_priv_txn_address ON private_transactions(LOWER(address));
