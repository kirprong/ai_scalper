"""
Test script for ASOF JOIN Time Aligner

This script:
1. Inserts sample market data (Binance and Polymarket) for 1 hour
2. Runs the time aligner
3. Outputs the average time delta statistics
"""

import asyncio
import logging
import os
import random
from datetime import datetime, timedelta

import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ClickHouse connection settings
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_HTTP_PORT = os.getenv("CLICKHOUSE_HTTP_PORT", "8123")
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "admin")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "admin123")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "market_data")


async def insert_sample_data(
    start_time: datetime,
    duration_hours: int = 1,
    binance_trades_per_minute: int = 100,
    poly_trades_per_minute: int = 10,
):
    """
    Insert sample market data for testing.
    
    Creates realistic test data with:
    - Binance trades with random timestamps
    - Polymarket trades with timestamps offset from Binance
    
    Args:
        start_time: Start time for sample data
        duration_hours: Duration in hours
        binance_trades_per_minute: Approximate Binance trades per minute
        poly_trades_per_minute: Approximate Polymarket trades per minute
    """
    logger.info(f"Inserting sample data starting at {start_time}")
    
    url = f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_HTTP_PORT}/"
    
    # Generate Binance data
    binance_records = []
    end_time = start_time + timedelta(hours=duration_hours)
    
    current_time = start_time
    while current_time < end_time:
        # Add some randomness to timestamps
        for _ in range(binance_trades_per_minute // 60):
            ts = current_time + timedelta(
                milliseconds=random.randint(0, 999)
            )
            price = 50000 + random.uniform(-100, 100)  # BTC price around 50k
            volume = random.uniform(0.01, 1.0)
            side = "buy" if random.random() > 0.5 else "sell"
            
            binance_records.append({
                "symbol": "BTCUSDT",
                "ts": ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "price": price,
                "volume": volume,
                "side": side,
                "source": "binance",
            })
        
        current_time += timedelta(seconds=1)
    
    # Generate Polymarket data with intentional time offset
    poly_records = []
    current_time = start_time
    
    # Time offset range (simulating real-world delay)
    # Polymarket trades may lag behind Binance by 0-500ms
    time_offset_ms_range = (0, 500)
    
    while current_time < end_time:
        for _ in range(poly_trades_per_minute // 60):
            # Add time offset to simulate real-world conditions
            time_offset_ms = random.randint(*time_offset_ms_range)
            
            ts = current_time + timedelta(
                milliseconds=random.randint(0, 999) + time_offset_ms
            )
            
            # Probability price (0-1 scale)
            price = random.uniform(0.3, 0.7)
            volume = random.uniform(10, 1000)
            side = "buy" if random.random() > 0.5 else "sell"
            
            poly_records.append({
                "symbol": "POLY:BTC_100K",
                "ts": ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "price": price,
                "volume": volume,
                "side": side,
                "source": "polymarket",
            })
        
        current_time += timedelta(seconds=1)
    
    logger.info(f"Generated {len(binance_records)} Binance records")
    logger.info(f"Generated {len(poly_records)} Polymarket records")
    
    # Insert Binance data
    if binance_records:
        await insert_batch(url, binance_records, "binance")
    
    # Insert Polymarket data
    if poly_records:
        await insert_batch(url, poly_records, "polymarket")
    
    logger.info("Sample data insertion complete")
    
    return len(binance_records), len(poly_records)


async def insert_batch(url: str, records: list, source: str):
    """Insert a batch of records into ClickHouse."""
    query = f"""
    INSERT INTO {CLICKHOUSE_DATABASE}.market_data
    (symbol, ts, price, volume, side, source)
    FORMAT JSONEachRow
    """
    
    payload_lines = []
    for record in records:
        payload_lines.append(
            f'{{"symbol":"{record["symbol"]}",'
            f'"ts":"{record["ts"]}",'
            f'"price":{record["price"]},'
            f'"volume":{record["volume"]},'
            f'"side":"{record["side"]}",'
            f'"source":"{record["source"]}"}}'
        )
    
    payload = "\n".join(payload_lines)
    
    params = {
        "query": query,
        "user": CLICKHOUSE_USER,
        "password": CLICKHOUSE_PASSWORD,
        "database": CLICKHOUSE_DATABASE,
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            params=params,
            data=payload,
            headers={"Content-Type": "application/x-ndjson"},
        ) as response:
            if response.status == 200:
                logger.info(f"Inserted {len(records)} {source} records")
            else:
                error_text = await response.text()
                raise Exception(f"Failed to insert {source} data: {error_text}")


async def clear_test_data(start_time: datetime, end_time: datetime):
    """Clear test data from ClickHouse."""
    url = f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_HTTP_PORT}/"
    
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
    
    query = f"""
    ALTER TABLE {CLICKHOUSE_DATABASE}.market_data
    DELETE WHERE ts >= '{start_str}' AND ts < '{end_str}'
    """
    
    params = {
        "query": query,
        "user": CLICKHOUSE_USER,
        "password": CLICKHOUSE_PASSWORD,
        "database": CLICKHOUSE_DATABASE,
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params) as response:
            if response.status == 200:
                logger.info("Cleared existing test data")
            else:
                logger.warning("Failed to clear test data (may not exist)")


async def run_test():
    """Run the time aligner test."""
    # Use a fixed time range for testing
    # Using a date in the past to avoid conflicts
    test_start = datetime(2026, 3, 8, 10, 0, 0)
    test_end = test_start + timedelta(hours=1)
    
    logger.info("=" * 60)
    logger.info("ASOF JOIN Time Aligner Test")
    logger.info("=" * 60)
    logger.info(f"Test time range: {test_start} to {test_end}")
    
    # Clear any existing test data
    await clear_test_data(test_start, test_end)
    
    # Wait for deletion to complete
    await asyncio.sleep(2)
    
    # Insert sample data
    binance_count, poly_count = await insert_sample_data(
        start_time=test_start,
        duration_hours=1,
        binance_trades_per_minute=100,
        poly_trades_per_minute=10,
    )
    
    # Wait for data to be available
    await asyncio.sleep(1)
    
    # Run time aligner
    from backend.sync.time_aligner import TimeAligner
    
    logger.info("\n" + "=" * 60)
    logger.info("Running Time Aligner")
    logger.info("=" * 60)
    
    async with TimeAligner() as aligner:
        result = await aligner.align_time_range(
            start_time=test_start,
            end_time=test_end,
            time_window_ms=1000,
        )
    
    # Output results
    logger.info("\n" + "=" * 60)
    logger.info("Test Results")
    logger.info("=" * 60)
    
    if result.success:
        logger.info(f"Status: SUCCESS")
        logger.info(f"Matched pairs: {result.matched_pairs}")
        logger.info(f"Unmatched Polymarket: {result.unmatched_poly}")
        logger.info(f"Unmatched Binance: {result.unmatched_binance}")
        
        if result.stats:
            logger.info(f"\n{result.stats}")
            
            # Verify the average delta is within expected range
            # Since we generated data with 0-500ms offset, the average should be around 250ms
            logger.info(f"\nExpected average delta: ~250ms (based on test data generation)")
            logger.info(f"Actual average delta: {result.stats.mean_ms:.3f}ms")
            
            if 100 <= result.stats.mean_ms <= 400:
                logger.info("✓ Average delta is within expected range!")
            else:
                logger.warning("⚠ Average delta is outside expected range")
    else:
        logger.error(f"Status: FAILED")
        logger.error(f"Error: {result.error}")
        return False
    
    # Cleanup test data
    await clear_test_data(test_start, test_end)
    
    return result.success


if __name__ == "__main__":
    success = asyncio.run(run_test())
    exit(0 if success else 1)
