-- 0010_homeos_cases: persisted HomeOS investigation cases, scoped per user.
-- The full case object (avatar, pipeline events, shortlist, conversation,
-- search state) is stored as a JSONB blob in `data`. The scalar columns are
-- denormalized copies used for cheap list queries and ownership checks.
CREATE TABLE IF NOT EXISTS homeos_cases (
    case_id       TEXT PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    profile_text  TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'running',
    data          JSONB NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- List "my cases, newest first" hits this index.
CREATE INDEX IF NOT EXISTS homeos_cases_user_idx
    ON homeos_cases (user_id, created_at DESC);
