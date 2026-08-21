-- ClickHouse Schema for ZarinPal Merchant Dashboard
-- Source spec: §5.4 (Idempotent Ingestion, Corrected Column Names)
-- Migration Owner: Pourya

-- 1. Transient Staging Table
CREATE TABLE IF NOT EXISTS tx_staging
(
    session_key          UInt64,
    try_seq              UInt16,
    terminal_key         String,
    merchant_key         String,
    category_id          String,
    category_title       String,
    amount               UInt64,
    adjusted_fee         UInt64,
    session_status       LowCardinality(String),
    try_status           LowCardinality(String),
    switch_response_code LowCardinality(String),
    psp_code             LowCardinality(String),
    issuer_bank_code     LowCardinality(String),
    payer_card_key       String,
    verify_type          LowCardinality(String),  -- 'Automated' | 'Manual'
    init_time_ms         Nullable(UInt32),
    verify_time_ms       Nullable(UInt32),
    created_at           DateTime,
    try_created_at       Nullable(DateTime),
    verified_at          Nullable(DateTime),
    settled_at           Nullable(DateTime),
    expire_in            DateTime,
    ingest_batch_id      UUID
)
ENGINE = MergeTree
ORDER BY (merchant_key, created_at, session_key, try_seq)
TTL created_at + INTERVAL 7 DAY;


-- 2. Final Transaction Fact Table
CREATE TABLE IF NOT EXISTS tx_raw
(
    session_key          UInt64,
    try_seq              UInt16,
    terminal_key         String,
    merchant_key         String,
    category_id          String,
    category_title       String,
    amount               UInt64 CODEC(Delta, ZSTD(3)),
    adjusted_fee         UInt64 CODEC(Delta, ZSTD(3)),
    session_status       LowCardinality(String),
    try_status           LowCardinality(String),
    switch_response_code LowCardinality(String),
    psp_code             LowCardinality(String),
    issuer_bank_code     LowCardinality(String),
    payer_card_key       String,
    verify_type          LowCardinality(String),
    init_time_ms         Nullable(UInt32),
    verify_time_ms       Nullable(UInt32),
    created_at           DateTime CODEC(Delta, ZSTD(3)),
    try_created_at       Nullable(DateTime),
    verified_at          Nullable(DateTime),
    settled_at           Nullable(DateTime),
    expire_in            DateTime,
    ingest_batch_id      UUID
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(created_at)
ORDER BY (merchant_key, created_at, session_key, try_seq);


-- 3. Daily Merchant Rollup Materialized View
CREATE MATERIALIZED VIEW IF NOT EXISTS tx_daily_rollup
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (merchant_key, day)
AS
SELECT
    merchant_key,
    toDate(created_at) AS day,
    uniqExactState(session_key)                                                      AS sessions_started_state,
    uniqExactIfState(session_key, session_status IN ('Verified','Paid'))             AS sessions_succeeded_state,
    uniqExactIfState(session_key, session_status = 'Reversed')                       AS sessions_reversed_state,
    sumIfState(amount, session_status IN ('Verified','Paid'))                        AS gross_volume_state,
    sumIfState(adjusted_fee, session_status IN ('Verified','Paid'))                  AS gross_fee_proxy_state,
    avgIfState(try_seq, session_status IN ('Verified','Paid'))                       AS avg_try_seq_on_success_state,
    countIfState(try_status = 'NoAttempt')                                           AS abandoned_before_attempt_state,
    quantileTimingState(0.5)(init_time_ms)                                           AS p50_init_ms_state,
    quantileTimingState(0.95)(init_time_ms)                                          AS p95_init_ms_state
FROM tx_raw
GROUP BY merchant_key, day;


-- 4. Category Daily Rollup Materialized View (Peer Comparison)
CREATE MATERIALIZED VIEW IF NOT EXISTS category_daily_rollup
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (category_id, day)
AS
SELECT
    category_id,
    toDate(created_at) AS day,
    uniqExactState(merchant_key)                                         AS active_merchants_state,
    uniqExactState(session_key)                                          AS category_sessions_state,
    sumIfState(amount, session_status IN ('Verified','Paid'))            AS category_gross_volume_state,
    avgIfState(amount, session_status IN ('Verified','Paid'))            AS category_avg_ticket_state,
    quantileState(0.5)(amount)                                           AS category_median_ticket_state,
    quantileState(0.9)(amount)                                           AS category_p90_ticket_state,
    quantileState(0.95)(amount)                                          AS category_p95_ticket_state
FROM tx_raw
GROUP BY category_id, day;


-- 5. Terminal NoAttempt Clusters Materialized View (Anomaly Detection)
CREATE MATERIALIZED VIEW IF NOT EXISTS terminal_noattempt_clusters
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(bucket_start)
ORDER BY (terminal_key, bucket_start)
AS
SELECT
    terminal_key,
    merchant_key,
    toStartOfInterval(created_at, INTERVAL 30 MINUTE) AS bucket_start,
    round(amount, -4)                                 AS amount_bucket,
    countState()                                       AS cluster_size_state,
    minState(created_at)                               AS first_seen_state,
    maxState(created_at)                               AS last_seen_state
FROM tx_raw
WHERE try_status = 'NoAttempt'
GROUP BY terminal_key, merchant_key, bucket_start, amount_bucket;
