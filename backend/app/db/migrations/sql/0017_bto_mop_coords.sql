-- Coordinates for BTO project MOP estimates, so projects can be shown on the
-- map (geocoded by app.data.bto_mop: OneMap by project name, town-centroid
-- fallback). Nullable — a project may not geocode.

ALTER TABLE bto_project_mop_estimates ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION;
ALTER TABLE bto_project_mop_estimates ADD COLUMN IF NOT EXISTS lon DOUBLE PRECISION;
