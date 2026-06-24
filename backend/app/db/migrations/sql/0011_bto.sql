-- BTO (Build-To-Order) sales exercises + application rates, scraped from the
-- HDB Flat Portal (services-homes.hdb.gov.sg/sales/files/apprates/BTO{YYYYMM}.json)
-- by app.data.bto, refreshed monthly in the background. Reference data — no FK
-- to blocks/transactions.

CREATE TABLE IF NOT EXISTS bto_exercises (
    exercise_id        TEXT PRIMARY KEY,     -- 'YYYYMM' of the launch
    label              TEXT,                 -- e.g. 'June 2026'
    launch_start_date  DATE,
    launch_end_date    DATE,
    is_final_update    BOOLEAN NOT NULL DEFAULT FALSE,
    estate_count       INT NOT NULL DEFAULT 0,
    total_units        INT NOT NULL DEFAULT 0,
    total_applicants   INT NOT NULL DEFAULT 0,
    overall_app_rate   DECIMAL(8, 2),        -- applicants / units
    fetched_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- One row per (exercise, estate, flat type).
CREATE TABLE IF NOT EXISTS bto_application_rates (
    id                    SERIAL PRIMARY KEY,
    exercise_id           TEXT NOT NULL REFERENCES bto_exercises(exercise_id) ON DELETE CASCADE,
    estate_name           TEXT NOT NULL,
    flat_type             TEXT NOT NULL,
    classification        TEXT,                 -- Standard / Plus / Prime
    project_names         TEXT,                 -- comma-separated
    flat_supply           INT NOT NULL DEFAULT 0,
    total_applicant_no    INT NOT NULL DEFAULT 0,
    overall_rate          DECIMAL(8, 2),        -- applicants / supply
    rate_first_time_fam   DECIMAL(8, 2),
    rate_second_time_fam  DECIMAL(8, 2),
    rate_first_time_singles DECIMAL(8, 2),
    rate_elderly          DECIMAL(8, 2),
    UNIQUE (exercise_id, estate_name, flat_type)
);

CREATE INDEX IF NOT EXISTS idx_bto_rates_exercise ON bto_application_rates(exercise_id);
CREATE INDEX IF NOT EXISTS idx_bto_rates_estate   ON bto_application_rates(estate_name);
CREATE INDEX IF NOT EXISTS idx_bto_rates_flattype ON bto_application_rates(flat_type);
