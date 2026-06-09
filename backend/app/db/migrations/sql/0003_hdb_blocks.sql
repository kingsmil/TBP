-- 0003 HDB blocks: the central spatial entity.

CREATE TABLE hdb_blocks (
    block_id                bigint PRIMARY KEY,
    block_number            text NOT NULL,
    street_name             text NOT NULL,
    postal_code             text,
    town                    text,
    planning_area_id        bigint REFERENCES planning_areas (planning_area_id),
    lease_commencement_year smallint,
    geom                    geometry(Point, 4326) NOT NULL,
    geom_svy21              geometry(Point, 3414)
                            GENERATED ALWAYS AS (ST_Transform(geom, 3414)) STORED,
    CONSTRAINT hdb_blocks_natural_key UNIQUE (block_number, street_name)
);

CREATE INDEX hdb_blocks_geom_gist        ON hdb_blocks USING gist (geom);
CREATE INDEX hdb_blocks_geom_svy21_gist  ON hdb_blocks USING gist (geom_svy21);
CREATE INDEX hdb_blocks_town_idx         ON hdb_blocks (town);
CREATE INDEX hdb_blocks_planning_area_idx ON hdb_blocks (planning_area_id);
CREATE INDEX hdb_blocks_lease_year_idx   ON hdb_blocks (lease_commencement_year);

-- remaining_lease_years depends on the current date, so it cannot be a STORED
-- generated column (now() is non-immutable). Expose it via a view instead.
CREATE VIEW hdb_blocks_enriched AS
SELECT
    b.*,
    GREATEST(0, 99 - (EXTRACT(YEAR FROM CURRENT_DATE)::int - b.lease_commencement_year))
        AS remaining_lease_years
FROM hdb_blocks b;
