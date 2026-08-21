-- ClickHouse Retention Policies
-- Source spec: §5.5 (Data Retention)
-- Migration Owner: Pourya

-- tx_staging self-cleans transient batch rows after 7 days
ALTER TABLE tx_staging MODIFY TTL created_at + INTERVAL 7 DAY;

-- tx_raw maintains 24 months hot storage, then drops or moves partitions
ALTER TABLE tx_raw MODIFY TTL created_at + INTERVAL 24 MONTH;
