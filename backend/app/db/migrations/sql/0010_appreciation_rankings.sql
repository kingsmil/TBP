-- Precomputed appreciation rankings (built by app.analysis.build_rankings,
-- refreshed monthly). Two grains: planning area ("region") and block.
--
-- Each row carries BOTH a backward-looking realized metric (cagr_pct over the
-- analysis window) and a forward-looking composite score (appreciation_score,
-- from the appreciation engine). Tables are fully replaced on each rebuild.

CREATE TABLE IF NOT EXISTS region_appreciation_ranking (
    planning_area_id    BIGINT PRIMARY KEY REFERENCES planning_areas(planning_area_id) ON DELETE CASCADE,
    name                TEXT,
    region              TEXT,
    rank                INT NOT NULL,
    appreciation_score  DECIMAL(6, 2),   -- forward-looking composite (0-100)
    cagr_pct            DECIMAL(7, 2),   -- realized annualised PSF growth over the window
    median_psf_start    DECIMAL(10, 2),
    median_psf_end      DECIMAL(10, 2),
    year_start          INT,
    year_end            INT,
    txn_count           INT NOT NULL DEFAULT 0,
    block_count         INT NOT NULL DEFAULT 0,
    computed_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_region_appr_rank ON region_appreciation_ranking(rank);

CREATE TABLE IF NOT EXISTS block_appreciation_ranking (
    block_id            INT PRIMARY KEY REFERENCES hdb_blocks(block_id) ON DELETE CASCADE,
    planning_area_id    BIGINT,
    rank                INT NOT NULL,          -- overall rank across all blocks
    region_rank         INT,                   -- rank within the block's planning area
    appreciation_score  DECIMAL(6, 2),
    cagr_pct            DECIMAL(7, 2),
    median_psf_start    DECIMAL(10, 2),
    median_psf_end      DECIMAL(10, 2),
    year_start          INT,
    year_end            INT,
    txn_count           INT NOT NULL DEFAULT 0,
    computed_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_block_appr_rank ON block_appreciation_ranking(rank);
CREATE INDEX IF NOT EXISTS idx_block_appr_pa   ON block_appreciation_ranking(planning_area_id);
