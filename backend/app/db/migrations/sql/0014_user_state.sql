-- Saved user state: locations + preferences, so logged-in users don't re-key
-- the same info. FK to the existing users table (0009). Anonymous users keep
-- their state client-side (localStorage) and push it here on login.

-- A stable row for the AUTH_REQUIRED=false dev-bypass user (CurrentUser.user_id
-- = 0 in app.api.auth), so saved-state CRUD works locally without registering.
INSERT INTO users (id, email, password_hash, is_subscribed)
VALUES (0, 'dev@local', 'x', TRUE)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS saved_locations (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label         TEXT NOT NULL,
    address       TEXT,
    postal_code   TEXT,
    lat           DOUBLE PRECISION,
    lng           DOUBLE PRECISION,
    location_type TEXT NOT NULL DEFAULT 'custom',  -- home|work|school|partner|family|custom
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS saved_locations_user_idx ON saved_locations(user_id);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id                          INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    preferred_property_modes         TEXT,            -- comma-separated: bto,resale,private
    last_search_mode                 TEXT,            -- resale|bto|private|unsure
    commute_weight                   DOUBLE PRECISION,
    lifestyle_weight                 DOUBLE PRECISION,
    affordability_weight             DOUBLE PRECISION,
    schools_weight                   DOUBLE PRECISION,
    mrt_weight                       DOUBLE PRECISION,
    future_mrt_weight                DOUBLE PRECISION,
    max_budget                       BIGINT,
    preferred_towns                  TEXT,            -- comma-separated
    preferred_flat_types             TEXT,            -- comma-separated
    preferred_private_property_types TEXT,            -- comma-separated
    metadata_json                    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at                       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
