-- Proximity rebuild: the SQL equivalent of app.core.geo / compute_proximity.
-- Uses the GIST-indexed geom_svy21 column, the KNN operator (<->) for nearest
-- neighbours, and ST_DWithin for radius counts. Run after reference layers or
-- blocks change.

TRUNCATE block_proximity;

INSERT INTO block_proximity (
    block_id,
    nearest_mrt_station_id, nearest_mrt_distance_m,
    nearest_future_mrt_station_id, nearest_future_mrt_distance_m,
    nearest_bus_stop_code, nearest_bus_distance_m,
    schools_within_1km, schools_within_2km, bus_stops_within_400m
)
SELECT
    b.block_id,
    m.station_id, m.dist,
    fm.station_id, fm.dist,
    bs.bus_stop_code, bs.dist,
    (SELECT count(*) FROM schools s
       WHERE ST_DWithin(b.geom_svy21, s.geom_svy21, 1000)),
    (SELECT count(*) FROM schools s
       WHERE ST_DWithin(b.geom_svy21, s.geom_svy21, 2000)),
    (SELECT count(*) FROM bus_stops bb
       WHERE ST_DWithin(b.geom_svy21, bb.geom_svy21, 400))
FROM hdb_blocks b
LEFT JOIN LATERAL (
    SELECT m.station_id, ST_Distance(b.geom_svy21, m.geom_svy21) AS dist
    FROM mrt_stations m
    WHERE m.status = 'operational'
    ORDER BY b.geom_svy21 <-> m.geom_svy21
    LIMIT 1
) m ON true
LEFT JOIN LATERAL (
    SELECT m.station_id, ST_Distance(b.geom_svy21, m.geom_svy21) AS dist
    FROM mrt_stations m
    WHERE m.status = 'future'
    ORDER BY b.geom_svy21 <-> m.geom_svy21
    LIMIT 1
) fm ON true
LEFT JOIN LATERAL (
    SELECT bb.bus_stop_code, ST_Distance(b.geom_svy21, bb.geom_svy21) AS dist
    FROM bus_stops bb
    ORDER BY b.geom_svy21 <-> bb.geom_svy21
    LIMIT 1
) bs ON true;
