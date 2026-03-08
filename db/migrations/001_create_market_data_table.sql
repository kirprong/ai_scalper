-- Migration: 001_create_market_data_table
-- Description: Create market_data table with ZSTD compression and OHLC views
-- Created: 2026-03-08

-- Use the market_data database
USE market_data;

-- Drop existing sample table if exists (from init script)
DROP TABLE IF EXISTS market_data.sample_ticks;

-- Create the main market_data table
-- This table stores raw trade/tick data with columnar storage optimization
CREATE TABLE IF NOT EXISTS market_data.market_data
(
    symbol String,                          -- Trading pair identifier (e.g., 'BTCUSDT', 'POLY:123')
    ts DateTime64(3),                       -- Timestamp with millisecond precision
    price Float64 CODEC(ZSTD(1)),           -- Trade price with ZSTD compression
    volume Float64 CODEC(ZSTD(1)),          -- Trade volume with ZSTD compression
    side Enum8('buy' = 1, 'sell' = 2),      -- Trade side: buy or sell
    source String,                          -- Data source: 'binance', 'polymarket', etc.
    
    -- Indexes for fast queries
    INDEX idx_symbol symbol TYPE bloom_filter GRANULARITY 1,
    INDEX idx_ts ts TYPE minmax GRANULARITY 1
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)                   -- Partition by month for efficient data management
ORDER BY (symbol, ts)                       -- Primary key for sorting and fast range queries
SETTINGS index_granularity = 8192;

-- Create OHLC view for 1-second aggregation
CREATE VIEW IF NOT EXISTS market_data.ohlc_1s AS
SELECT
    symbol,
    toStartOfInterval(ts, INTERVAL 1 SECOND) AS interval_start,
    argMin(price, ts) AS open,              -- First price in interval
    max(price) AS high,                      -- Highest price in interval
    min(price) AS low,                       -- Lowest price in interval
    argMax(price, ts) AS close,             -- Last price in interval
    sum(volume) AS volume,                   -- Total volume in interval
    count() AS trade_count                   -- Number of trades in interval
FROM market_data.market_data
GROUP BY symbol, interval_start
ORDER BY symbol, interval_start;

-- Create OHLC view for 5-second aggregation
CREATE VIEW IF NOT EXISTS market_data.ohlc_5s AS
SELECT
    symbol,
    toStartOfInterval(ts, INTERVAL 5 SECOND) AS interval_start,
    argMin(price, ts) AS open,
    max(price) AS high,
    min(price) AS low,
    argMax(price, ts) AS close,
    sum(volume) AS volume,
    count() AS trade_count
FROM market_data.market_data
GROUP BY symbol, interval_start
ORDER BY symbol, interval_start;

-- Create OHLC view for 10-second aggregation
CREATE VIEW IF NOT EXISTS market_data.ohlc_10s AS
SELECT
    symbol,
    toStartOfInterval(ts, INTERVAL 10 SECOND) AS interval_start,
    argMin(price, ts) AS open,
    max(price) AS high,
    min(price) AS low,
    argMax(price, ts) AS close,
    sum(volume) AS volume,
    count() AS trade_count
FROM market_data.market_data
GROUP BY symbol, interval_start
ORDER BY symbol, interval_start;

-- Log successful migration
SELECT 'Migration 001_create_market_data_table completed successfully' AS status;
