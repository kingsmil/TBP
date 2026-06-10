#!/bin/sh
# Dump the active-listing -> block mapping as CSV (run after `make listings-load`).
OUT="${1:-listing_block_mapping.csv}"
docker exec hdbmatch_postgis psql -U hdbmatch -d hdbmatch -c "\copy (
  SELECT l.listing_id,
         l.block_id,
         b.block_number,
         b.street_name,
         b.town       AS block_town,
         l.postal_code AS listing_postal,
         l.flat_type,
         l.price,
         l.floor_area_sqm,
         l.storey_range,
         l.remaining_lease,
         l.managed_by_agent,
         l.agent_name,
         l.agent_phone,
         l.agency_name
  FROM hdb_active_listings l
  JOIN hdb_blocks b ON b.block_id = l.block_id
  ORDER BY b.town, b.street_name, b.block_number, l.price
) TO STDOUT WITH CSV HEADER" > "$OUT"
echo "wrote $OUT ($(wc -l < "$OUT") lines)"
