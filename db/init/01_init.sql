-- Initialize ClickHouse database with ZSTD compression for float columns
-- This script runs on container startup

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS market_data;

-- Note: Tables and views are created via migration scripts in db/migrations/
-- Run migrations using: python scripts/run_migrations.py
