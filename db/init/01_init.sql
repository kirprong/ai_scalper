-- Initialize ClickHouse database with ZSTD compression for float columns
-- This script runs on container startup

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS market_data;

-- Use the market_data database
USE market_data;

-- Create a sample table demonstrating ZSTD compression for float columns
-- This will be replaced by proper migrations in TASK-003
CREATE TABLE IF NOT EXISTS market_data.sample_ticks
(
    symbol String,
    ts DateTime64(3),
    price Float64 CODEC(ZSTD(1)),
    volume Float64 CODEC(ZSTD(1)),
    side String
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (symbol, ts)
SETTINGS index_granularity = 8192;
