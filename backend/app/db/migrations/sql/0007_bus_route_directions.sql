ALTER TABLE bus_routes DROP CONSTRAINT bus_routes_pkey;
ALTER TABLE bus_routes ADD COLUMN direction smallint NOT NULL DEFAULT 1;
ALTER TABLE bus_routes ADD COLUMN distance_km numeric(8,3);
ALTER TABLE bus_routes ADD PRIMARY KEY (service_no, direction, stop_sequence);
CREATE INDEX bus_routes_service_direction_idx
    ON bus_routes (service_no, direction, stop_sequence);
