-- 0002 Reference spatial layers (near-static): planning areas, MRT, bus, schools, BTO.
-- Every spatial table carries geom (4326, canonical) + geom_svy21 (3414, metric, generated).
-- ST_Transform is IMMUTABLE, so it is valid inside a STORED generated column.

CREATE TABLE planning_areas (
    planning_area_id bigint PRIMARY KEY,
    name             text NOT NULL,
    region           text,
    geom             geometry(MultiPolygon, 4326) NOT NULL,
    geom_svy21       geometry(MultiPolygon, 3414)
                     GENERATED ALWAYS AS (ST_Transform(geom, 3414)) STORED
);
CREATE INDEX planning_areas_geom_gist       ON planning_areas USING gist (geom);
CREATE INDEX planning_areas_geom_svy21_gist ON planning_areas USING gist (geom_svy21);

-- Single MRT table with a status flag (operational | future). Simplifies
-- "nearest MRT (current or future)" queries and proximity refresh.
CREATE TABLE mrt_stations (
    station_id   bigint PRIMARY KEY,
    station_name text NOT NULL,
    line_name    text,
    status       text NOT NULL DEFAULT 'operational'
                 CHECK (status IN ('operational', 'future')),
    opening_year smallint,
    geom         geometry(Point, 4326) NOT NULL,
    geom_svy21   geometry(Point, 3414)
                 GENERATED ALWAYS AS (ST_Transform(geom, 3414)) STORED
);
CREATE INDEX mrt_stations_geom_gist       ON mrt_stations USING gist (geom);
CREATE INDEX mrt_stations_geom_svy21_gist ON mrt_stations USING gist (geom_svy21);
CREATE INDEX mrt_stations_status_idx      ON mrt_stations (status);

CREATE TABLE bus_stops (
    bus_stop_code text PRIMARY KEY,
    description   text,
    geom          geometry(Point, 4326) NOT NULL,
    geom_svy21    geometry(Point, 3414)
                  GENERATED ALWAYS AS (ST_Transform(geom, 3414)) STORED
);
CREATE INDEX bus_stops_geom_gist       ON bus_stops USING gist (geom);
CREATE INDEX bus_stops_geom_svy21_gist ON bus_stops USING gist (geom_svy21);

CREATE TABLE schools (
    school_id   bigint PRIMARY KEY,
    school_name text NOT NULL,
    school_type text,
    geom        geometry(Point, 4326) NOT NULL,
    geom_svy21  geometry(Point, 3414)
                GENERATED ALWAYS AS (ST_Transform(geom, 3414)) STORED
);
CREATE INDEX schools_geom_gist       ON schools USING gist (geom);
CREATE INDEX schools_geom_svy21_gist ON schools USING gist (geom_svy21);

CREATE TABLE bto_projects (
    project_id   bigint PRIMARY KEY,
    project_name text NOT NULL,
    launch_year  smallint,
    geom         geometry(Point, 4326) NOT NULL,
    geom_svy21   geometry(Point, 3414)
                 GENERATED ALWAYS AS (ST_Transform(geom, 3414)) STORED
);
CREATE INDEX bto_projects_geom_gist       ON bto_projects USING gist (geom);
CREATE INDEX bto_projects_geom_svy21_gist ON bto_projects USING gist (geom_svy21);

-- Bus routes: stored now; transit graph (NetworkX) is a later phase.
CREATE TABLE bus_routes (
    service_no    text NOT NULL,
    bus_stop_code text NOT NULL REFERENCES bus_stops (bus_stop_code),
    stop_sequence smallint NOT NULL,
    PRIMARY KEY (service_no, bus_stop_code, stop_sequence)
);
CREATE INDEX bus_routes_stop_idx ON bus_routes (bus_stop_code);
