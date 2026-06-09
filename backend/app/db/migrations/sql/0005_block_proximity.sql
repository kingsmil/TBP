-- 0005 Precomputed proximity: one row per block. Refreshed by a background job
-- when reference layers change. Turns accessibility filters into indexed numeric
-- comparisons instead of live KNN.

CREATE TABLE block_proximity (
    block_id                      bigint PRIMARY KEY REFERENCES hdb_blocks (block_id),
    nearest_mrt_station_id        bigint,
    nearest_mrt_distance_m        numeric(10,2),
    nearest_future_mrt_station_id bigint,
    nearest_future_mrt_distance_m numeric(10,2),
    nearest_bus_stop_code         text,
    nearest_bus_distance_m        numeric(10,2),
    schools_within_1km            smallint,
    schools_within_2km            smallint,
    bus_stops_within_400m         smallint
);

CREATE INDEX block_proximity_mrt_dist_idx     ON block_proximity (nearest_mrt_distance_m);
CREATE INDEX block_proximity_bus_dist_idx     ON block_proximity (nearest_bus_distance_m);
CREATE INDEX block_proximity_schools_1km_idx  ON block_proximity (schools_within_1km);
