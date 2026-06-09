-- 0006 Analytics materialized views. These back the entire dashboard.
-- Each MV has a UNIQUE index so REFRESH MATERIALIZED VIEW CONCURRENTLY works.
-- Medians via percentile_cont are computed once at refresh time, not per request.

CREATE MATERIALIZED VIEW mv_block_monthly_stats AS
SELECT
    t.block_id,
    t.transaction_month,
    t.flat_type,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY t.psf)          AS median_psf,
    avg(t.psf)                                                   AS avg_psf,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY t.resale_price)  AS median_price,
    avg(t.resale_price)                                          AS avg_price,
    count(*)                                                     AS txn_count
FROM hdb_transactions t
GROUP BY t.block_id, t.transaction_month, t.flat_type
WITH NO DATA;

CREATE UNIQUE INDEX mv_block_monthly_stats_uidx
    ON mv_block_monthly_stats (block_id, transaction_month, flat_type);

CREATE MATERIALIZED VIEW mv_estate_monthly_stats AS
SELECT
    b.planning_area_id,
    t.transaction_month,
    t.flat_type,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY t.psf)          AS median_psf,
    avg(t.psf)                                                   AS avg_psf,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY t.resale_price)  AS median_price,
    avg(t.resale_price)                                          AS avg_price,
    count(*)                                                     AS txn_count
FROM hdb_transactions t
JOIN hdb_blocks b ON b.block_id = t.block_id
WHERE b.planning_area_id IS NOT NULL
GROUP BY b.planning_area_id, t.transaction_month, t.flat_type
WITH NO DATA;

CREATE UNIQUE INDEX mv_estate_monthly_stats_uidx
    ON mv_estate_monthly_stats (planning_area_id, transaction_month, flat_type);
