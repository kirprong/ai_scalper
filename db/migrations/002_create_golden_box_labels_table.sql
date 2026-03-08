-- Migration: 002_create_golden_box_labels_table
-- Description: Create golden_box_labels table for ML training labels
-- Created: 2026-03-08

-- Use the market_data database
USE market_data;

-- Create the golden_box_labels table
-- This table stores Is_Golden_Box labels for historical data points
-- Each row represents a label for a specific (symbol, timestamp) combination
CREATE TABLE IF NOT EXISTS market_data.golden_box_labels
(
    symbol String,              -- Trading pair identifier (e.g., 'BTCUSDT', 'POLY:123')
    ts DateTime64(3),           -- Timestamp with millisecond precision
    is_golden_box UInt8,        -- Label: 1 if inside golden rectangle, 0 otherwise
    box_id String DEFAULT '',   -- ID of the golden rectangle (optional, for traceability)
    created_at DateTime DEFAULT now(),  -- When this label was created
    
    -- Indexes for fast queries
    INDEX idx_symbol symbol TYPE bloom_filter GRANULARITY 1,
    INDEX idx_ts ts TYPE minmax GRANULARITY 1,
    INDEX idx_label is_golden_box TYPE minmax GRANULARITY 1
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)       -- Partition by month for efficient data management
ORDER BY (symbol, ts)           -- Primary key for sorting and fast range queries
SETTINGS index_granularity = 8192;

-- Create a materialized view for quick statistics
-- This view provides counts of golden box labels per symbol
CREATE MATERIALIZED VIEW IF NOT EXISTS market_data.golden_box_stats
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (symbol, toStartOfDay(ts))
AS SELECT
    symbol,
    toStartOfDay(ts) AS day,
    count() AS total_points,
    sum(is_golden_box) AS golden_box_count
FROM market_data.golden_box_labels
GROUP BY symbol, day;

-- Create a view for easy querying of labeled data
-- This view joins market_data with labels
CREATE VIEW IF NOT EXISTS market_data.labeled_market_data AS
SELECT
    m.symbol,
    m.ts,
    m.price,
    m.volume,
    m.side,
    m.source,
    COALESCE(l.is_golden_box, 0) AS is_golden_box,
    l.box_id
FROM market_data.market_data AS m
LEFT JOIN market_data.golden_box_labels AS l
    ON m.symbol = l.symbol AND m.ts = l.ts;

-- Log successful migration
SELECT 'Migration 002_create_golden_box_labels_table completed successfully' AS status;
