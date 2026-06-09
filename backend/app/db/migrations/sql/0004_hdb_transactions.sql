-- 0004 HDB resale transactions: large, append-mostly, RANGE-partitioned by month.
-- Partition pruning + generated psf are the key analytics optimizations.

CREATE TABLE hdb_transactions (
    transaction_id    bigint GENERATED ALWAYS AS IDENTITY,
    block_id          bigint NOT NULL REFERENCES hdb_blocks (block_id),
    transaction_month date   NOT NULL,
    resale_price      numeric(12,2) NOT NULL,
    floor_area_sqm    numeric(8,2)  NOT NULL,
    floor_area_sqft   numeric(12,4)
                      GENERATED ALWAYS AS (floor_area_sqm * 10.7639) STORED,
    psf               numeric(12,4)
                      GENERATED ALWAYS AS (resale_price / NULLIF(floor_area_sqm * 10.7639, 0)) STORED,
    flat_type         text NOT NULL,
    storey_range      text,
    -- PK must include the partition key.
    PRIMARY KEY (transaction_id, transaction_month)
) PARTITION BY RANGE (transaction_month);

-- Yearly partitions. Add more as data grows (or automate in the ingest job).
CREATE TABLE hdb_transactions_2017 PARTITION OF hdb_transactions
    FOR VALUES FROM ('2017-01-01') TO ('2018-01-01');
CREATE TABLE hdb_transactions_2018 PARTITION OF hdb_transactions
    FOR VALUES FROM ('2018-01-01') TO ('2019-01-01');
CREATE TABLE hdb_transactions_2019 PARTITION OF hdb_transactions
    FOR VALUES FROM ('2019-01-01') TO ('2020-01-01');
CREATE TABLE hdb_transactions_2020 PARTITION OF hdb_transactions
    FOR VALUES FROM ('2020-01-01') TO ('2021-01-01');
CREATE TABLE hdb_transactions_2021 PARTITION OF hdb_transactions
    FOR VALUES FROM ('2021-01-01') TO ('2022-01-01');
CREATE TABLE hdb_transactions_2022 PARTITION OF hdb_transactions
    FOR VALUES FROM ('2022-01-01') TO ('2023-01-01');
CREATE TABLE hdb_transactions_2023 PARTITION OF hdb_transactions
    FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
CREATE TABLE hdb_transactions_2024 PARTITION OF hdb_transactions
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE hdb_transactions_2025 PARTITION OF hdb_transactions
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
CREATE TABLE hdb_transactions_2026 PARTITION OF hdb_transactions
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

-- Indexes declared on the partitioned parent propagate to all partitions.
CREATE INDEX hdb_txn_block_idx       ON hdb_transactions (block_id);
CREATE INDEX hdb_txn_flat_type_idx   ON hdb_transactions (flat_type);
CREATE INDEX hdb_txn_psf_idx         ON hdb_transactions (psf);
CREATE INDEX hdb_txn_block_month_idx ON hdb_transactions (block_id, transaction_month);
