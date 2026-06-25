-- Estimated BTO Resale Availability.
--
-- Precomputed estimates of when newer BTO projects / estates may become
-- eligible for the resale market, i.e. completion/key-collection + MOP. These
-- are ESTIMATES, not confirmed resale dates — actual eligibility depends on each
-- owner's legal completion date and physical occupation period (see
-- docs/BTO_MOP_ESTIMATION_RULES.md).
--
-- Built in the background by app.data.bto_mop from a manual seed file plus the
-- launch metadata already in bto_application_rates / bto_exercises. Reference
-- data — no FK to blocks/transactions.

CREATE TABLE IF NOT EXISTS bto_project_mop_estimates (
    id                          SERIAL PRIMARY KEY,
    project_name                TEXT NOT NULL,        -- falls back to estate when no project is named
    town                        TEXT,
    estate                      TEXT,
    launch_exercise             TEXT,                 -- bto_exercises.exercise_id ('YYYYMM'), if derived from a launch
    flat_classification         TEXT NOT NULL,        -- STANDARD | PLUS | PRIME | PLH | UNCLASSIFIED | UNKNOWN
    flat_types                  TEXT,                 -- comma-separated, e.g. '3 ROOM, 4 ROOM'
    estimated_completion_date   DATE,
    estimated_key_collection_date DATE,
    mop_years                   INT NOT NULL,
    estimated_resale_eligible_date DATE,
    confidence                  TEXT NOT NULL,        -- HIGH | MEDIUM | LOW
    confidence_reason           TEXT,
    source_url                  TEXT,
    source_type                 TEXT NOT NULL,        -- HDB_LAUNCH_PAGE | DATA_GOV_HDB_PROPERTY_INFO | DATA_GOV_COMPLETION_STATUS | MANUAL_SEED
    last_verified_at            DATE,
    created_at                  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (project_name, town, flat_classification)
);

CREATE INDEX IF NOT EXISTS idx_bto_mop_eligible ON bto_project_mop_estimates(estimated_resale_eligible_date);
CREATE INDEX IF NOT EXISTS idx_bto_mop_town     ON bto_project_mop_estimates(town);
CREATE INDEX IF NOT EXISTS idx_bto_mop_class    ON bto_project_mop_estimates(flat_classification);
CREATE INDEX IF NOT EXISTS idx_bto_mop_conf     ON bto_project_mop_estimates(confidence);
