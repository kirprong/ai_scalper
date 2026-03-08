"""
ASOF JOIN Time Aligner for Market Data Synchronization

This module calculates Delta_T = Poly_TS - Binance_TS using ClickHouse ASOF JOIN
for millisecond-precision matching between Polymarket and Binance data streams.

ASOF JOIN allows finding the closest match in time, which is essential for
aligning trades from different sources that may have slight timestamp differences.
"""

import asyncio
import logging
import os
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import aiohttp
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_HTTP_PORT = os.getenv("CLICKHOUSE_HTTP_PORT", "8123")
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "admin")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "admin123")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "market_data")

# Default symbols
DEFAULT_BINANCE_SYMBOL = "BTCUSDT"
DEFAULT_POLYMARKET_PREFIX = "POLY:"


class TimeDeltaStats(BaseModel):
    """Statistics for time delta calculations."""
    
    count: int = Field(..., description="Number of matched pairs")
    mean_ms: float = Field(..., description="Mean delta in milliseconds")
    median_ms: float = Field(..., description="Median delta in milliseconds")
    std_dev_ms: float = Field(..., description="Standard deviation in milliseconds")
    min_ms: float = Field(..., description="Minimum delta in milliseconds")
    max_ms: float = Field(..., description="Maximum delta in milliseconds")
    p25_ms: float = Field(..., description="25th percentile in milliseconds")
    p75_ms: float = Field(..., description="75th percentile in milliseconds")
    p95_ms: float = Field(..., description="95th percentile in milliseconds")
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        return (
            f"Time Delta Statistics:\n"
            f"  Matched pairs: {self.count}\n"
            f"  Mean:   {self.mean_ms:.3f} ms\n"
            f"  Median: {self.median_ms:.3f} ms\n"
            f"  StdDev: {self.std_dev_ms:.3f} ms\n"
            f"  Min:    {self.min_ms:.3f} ms\n"
            f"  Max:    {self.max_ms:.3f} ms\n"
            f"  P25:    {self.p25_ms:.3f} ms\n"
            f"  P75:    {self.p75_ms:.3f} ms\n"
            f"  P95:    {self.p95_ms:.3f} ms"
        )


class MatchedPair(BaseModel):
    """A single matched pair of Polymarket and Binance trades."""
    
    poly_ts: datetime = Field(..., description="Polymarket timestamp")
    binance_ts: datetime = Field(..., description="Binance timestamp")
    delta_ms: float = Field(..., description="Time delta in milliseconds (Poly - Binance)")
    poly_price: float = Field(..., description="Polymarket price")
    binance_price: float = Field(..., description="Binance price")
    poly_volume: float = Field(..., description="Polymarket volume")
    binance_volume: float = Field(..., description="Binance volume")
    poly_side: str = Field(..., description="Polymarket trade side")
    binance_side: str = Field(..., description="Binance trade side")


class AlignmentResult(BaseModel):
    """Result of time alignment operation."""
    
    success: bool = Field(..., description="Whether alignment was successful")
    stats: Optional[TimeDeltaStats] = Field(None, description="Time delta statistics")
    matched_pairs: int = Field(0, description="Number of matched pairs")
    unmatched_poly: int = Field(0, description="Unmatched Polymarket trades")
    unmatched_binance: int = Field(0, description="Unmatched Binance trades")
    error: Optional[str] = Field(None, description="Error message if failed")
    time_window_ms: int = Field(0, description="Time window used for matching")


class TimeAligner:
    """
    ASOF JOIN Time Aligner for market data synchronization.
    
    Uses ClickHouse ASOF JOIN to find the closest Binance trade for each
    Polymarket trade within a configurable time window.
    
    Example:
        async with TimeAligner() as aligner:
            result = await aligner.align_time_range(
                start_time=datetime(2026, 3, 8, 10, 0),
                end_time=datetime(2026, 3, 8, 11, 0),
                time_window_ms=1000
            )
            print(result.stats)
    """
    
    def __init__(
        self,
        clickhouse_host: str = CLICKHOUSE_HOST,
        clickhouse_port: str = CLICKHOUSE_HTTP_PORT,
        clickhouse_user: str = CLICKHOUSE_USER,
        clickhouse_password: str = CLICKHOUSE_PASSWORD,
        clickhouse_database: str = CLICKHOUSE_DATABASE,
        binance_symbol: str = DEFAULT_BINANCE_SYMBOL,
        polymarket_prefix: str = DEFAULT_POLYMARKET_PREFIX,
    ):
        """
        Initialize the time aligner.
        
        Args:
            clickhouse_host: ClickHouse server host
            clickhouse_port: ClickHouse HTTP port
            clickhouse_user: ClickHouse username
            clickhouse_password: ClickHouse password
            clickhouse_database: ClickHouse database name
            binance_symbol: Binance symbol to match (default: BTCUSDT)
            polymarket_prefix: Prefix for Polymarket symbols (default: POLY:)
        """
        self.clickhouse_host = clickhouse_host
        self.clickhouse_port = clickhouse_port
        self.clickhouse_user = clickhouse_user
        self.clickhouse_password = clickhouse_password
        self.clickhouse_database = clickhouse_database
        self.binance_symbol = binance_symbol
        self.polymarket_prefix = polymarket_prefix
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self) -> "TimeAligner":
        """Async context manager entry."""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=300),
            connector=aiohttp.TCPConnector(limit=10),
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._session:
            await self._session.close()
    
    async def _execute_query(self, query: str) -> str:
        """
        Execute a ClickHouse query and return the result.
        
        Args:
            query: SQL query to execute
            
        Returns:
            Query result as string
        """
        url = f"http://{self.clickhouse_host}:{self.clickhouse_port}/"
        params = {
            "query": query,
            "user": self.clickhouse_user,
            "password": self.clickhouse_password,
            "database": self.clickhouse_database,
        }
        
        try:
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    error_text = await response.text()
                    raise Exception(f"ClickHouse query failed: HTTP {response.status}: {error_text}")
        except aiohttp.ClientError as e:
            raise Exception(f"ClickHouse connection error: {e}")
    
    def _build_asof_join_query(
        self,
        start_time: datetime,
        end_time: datetime,
        time_window_ms: int = 1000,
        limit: Optional[int] = None,
    ) -> str:
        """
        Build ASOF JOIN query for time alignment.
        
        The query finds the closest Binance trade for each Polymarket trade
        within the specified time window.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            time_window_ms: Maximum time difference for matching (milliseconds)
            limit: Optional limit on number of results
            
        Returns:
            SQL query string
        """
        start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
        end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # ASOF JOIN query
        # For each Polymarket trade, find the closest Binance trade
        # that occurred at or before the Polymarket trade
        query = f"""
        SELECT 
            poly.ts AS poly_ts,
            binance.ts AS binance_ts,
            toFloat64(poly.ts - binance.ts) * 1000 AS delta_ms,
            poly.price AS poly_price,
            binance.price AS binance_price,
            poly.volume AS poly_volume,
            binance.volume AS binance_volume,
            poly.side AS poly_side,
            binance.side AS binance_side
        FROM (
            SELECT ts, price, volume, side
            FROM {self.clickhouse_database}.market_data
            WHERE source = 'polymarket'
                AND ts >= '{start_str}'
                AND ts < '{end_str}'
            ORDER BY ts
        ) AS poly
        ASOF LEFT JOIN (
            SELECT ts, price, volume, side
            FROM {self.clickhouse_database}.market_data
            WHERE source = 'binance'
                AND symbol = '{self.binance_symbol}'
                AND ts >= '{start_str}'
                AND ts < '{end_str}'
            ORDER BY ts
        ) AS binance
        ON poly.ts >= binance.ts
        WHERE binance.ts IS NOT NULL
            AND toFloat64(poly.ts - binance.ts) * 1000 <= {time_window_ms}
        """
        
        if limit:
            query += f"\nLIMIT {limit}"
        
        query += "\nORDER BY poly.ts"
        
        return query
    
    def _build_count_query(
        self,
        start_time: datetime,
        end_time: datetime,
        source: str,
        symbol: Optional[str] = None,
    ) -> str:
        """
        Build count query for a data source.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            source: Data source ('binance' or 'polymarket')
            symbol: Optional symbol filter
            
        Returns:
            SQL query string
        """
        start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
        end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        
        query = f"""
        SELECT count() AS count
        FROM {self.clickhouse_database}.market_data
        WHERE source = '{source}'
            AND ts >= '{start_str}'
            AND ts < '{end_str}'
        """
        
        if symbol:
            query += f"\nAND symbol = '{symbol}'"
        
        return query
    
    async def get_data_counts(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> Tuple[int, int]:
        """
        Get counts of Polymarket and Binance records in time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            Tuple of (polymarket_count, binance_count)
        """
        # Get Polymarket count
        poly_query = self._build_count_query(start_time, end_time, "polymarket")
        poly_result = await self._execute_query(poly_query)
        poly_count = int(poly_result.strip())
        
        # Get Binance count
        binance_query = self._build_count_query(
            start_time, end_time, "binance", self.binance_symbol
        )
        binance_result = await self._execute_query(binance_query)
        binance_count = int(binance_result.strip())
        
        return poly_count, binance_count
    
    def _parse_query_results(self, result_text: str) -> List[MatchedPair]:
        """
        Parse ASOF JOIN query results into MatchedPair objects.
        
        Args:
            result_text: Raw query result text
            
        Returns:
            List of MatchedPair objects
        """
        pairs = []
        lines = result_text.strip().split("\n")
        
        for line in lines:
            if not line.strip():
                continue
            
            parts = line.split("\t")
            if len(parts) < 9:
                continue
            
            try:
                # Parse timestamps
                poly_ts = datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S.%f")
                binance_ts = datetime.strptime(parts[1], "%Y-%m-%d %H:%M:%S.%f")
                
                pair = MatchedPair(
                    poly_ts=poly_ts,
                    binance_ts=binance_ts,
                    delta_ms=float(parts[2]),
                    poly_price=float(parts[3]),
                    binance_price=float(parts[4]),
                    poly_volume=float(parts[5]),
                    binance_volume=float(parts[6]),
                    poly_side=parts[7],
                    binance_side=parts[8],
                )
                pairs.append(pair)
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse line '{line}': {e}")
                continue
        
        return pairs
    
    def _calculate_statistics(self, pairs: List[MatchedPair]) -> TimeDeltaStats:
        """
        Calculate statistics from matched pairs.
        
        Args:
            pairs: List of matched pairs
            
        Returns:
            TimeDeltaStats object
        """
        if not pairs:
            raise ValueError("No pairs to calculate statistics")
        
        deltas = [p.delta_ms for p in pairs]
        sorted_deltas = sorted(deltas)
        
        count = len(deltas)
        mean = statistics.mean(deltas)
        median = statistics.median(deltas)
        
        # Standard deviation
        if count > 1:
            std_dev = statistics.stdev(deltas)
        else:
            std_dev = 0.0
        
        # Percentiles
        def percentile(data: List[float], p: float) -> float:
            """Calculate percentile using linear interpolation."""
            if not data:
                return 0.0
            k = (len(data) - 1) * p / 100.0
            f = int(k)
            c = f + 1 if f + 1 < len(data) else f
            return data[f] + (k - f) * (data[c] - data[f])
        
        return TimeDeltaStats(
            count=count,
            mean_ms=mean,
            median_ms=median,
            std_dev_ms=std_dev,
            min_ms=min(deltas),
            max_ms=max(deltas),
            p25_ms=percentile(sorted_deltas, 25),
            p75_ms=percentile(sorted_deltas, 75),
            p95_ms=percentile(sorted_deltas, 95),
        )
    
    async def align_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        time_window_ms: int = 1000,
        limit: Optional[int] = None,
    ) -> AlignmentResult:
        """
        Align Polymarket and Binance data for a time range using ASOF JOIN.
        
        This method calculates Delta_T = Poly_TS - Binance_TS for each
        matched pair of trades.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            time_window_ms: Maximum time difference for matching (milliseconds)
            limit: Optional limit on number of results
            
        Returns:
            AlignmentResult with statistics and match counts
        """
        logger.info(
            f"Aligning time range: {start_time} to {end_time}, "
            f"window={time_window_ms}ms"
        )
        
        try:
            # Get counts
            poly_count, binance_count = await self.get_data_counts(
                start_time, end_time
            )
            logger.info(
                f"Data counts: Polymarket={poly_count}, Binance={binance_count}"
            )
            
            # Execute ASOF JOIN query
            query = self._build_asof_join_query(
                start_time, end_time, time_window_ms, limit
            )
            logger.debug(f"Executing query:\n{query}")
            
            result_text = await self._execute_query(query)
            
            # Parse results
            pairs = self._parse_query_results(result_text)
            matched_count = len(pairs)
            
            logger.info(f"Matched {matched_count} pairs")
            
            # Calculate statistics
            if pairs:
                stats = self._calculate_statistics(pairs)
                logger.info(f"\n{stats}")
            else:
                stats = None
                logger.warning("No matched pairs found")
            
            # Calculate unmatched counts (approximate)
            unmatched_poly = max(0, poly_count - matched_count)
            unmatched_binance = max(0, binance_count - matched_count)
            
            return AlignmentResult(
                success=True,
                stats=stats,
                matched_pairs=matched_count,
                unmatched_poly=unmatched_poly,
                unmatched_binance=unmatched_binance,
                time_window_ms=time_window_ms,
            )
            
        except Exception as e:
            logger.error(f"Alignment failed: {e}")
            return AlignmentResult(
                success=False,
                error=str(e),
                time_window_ms=time_window_ms,
            )
    
    async def get_raw_pairs(
        self,
        start_time: datetime,
        end_time: datetime,
        time_window_ms: int = 1000,
        limit: Optional[int] = None,
    ) -> List[MatchedPair]:
        """
        Get raw matched pairs for a time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            time_window_ms: Maximum time difference for matching
            limit: Optional limit on number of results
            
        Returns:
            List of MatchedPair objects
        """
        query = self._build_asof_join_query(
            start_time, end_time, time_window_ms, limit
        )
        result_text = await self._execute_query(query)
        return self._parse_query_results(result_text)
    
    async def store_alignment_results(
        self,
        pairs: List[MatchedPair],
        table_name: str = "time_alignment",
    ) -> int:
        """
        Store alignment results in ClickHouse for analysis.
        
        Creates a table if it doesn't exist and inserts the matched pairs.
        
        Args:
            pairs: List of matched pairs to store
            table_name: Name of the table to store results
            
        Returns:
            Number of rows inserted
        """
        if not pairs:
            return 0
        
        # Create table if not exists
        create_query = f"""
        CREATE TABLE IF NOT EXISTS {self.clickhouse_database}.{table_name}
        (
            poly_ts DateTime64(3),
            binance_ts DateTime64(3),
            delta_ms Float64,
            poly_price Float64,
            binance_price Float64,
            poly_volume Float64,
            binance_volume Float64,
            poly_side String,
            binance_side String,
            created_at DateTime DEFAULT now()
        )
        ENGINE = MergeTree()
        ORDER BY (poly_ts, binance_ts)
        """
        await self._execute_query(create_query)
        
        # Insert data
        insert_query = f"""
        INSERT INTO {self.clickhouse_database}.{table_name}
        (poly_ts, binance_ts, delta_ms, poly_price, binance_price,
         poly_volume, binance_volume, poly_side, binance_side)
        FORMAT JSONEachRow
        """
        
        # Build JSON payload
        payload_lines = []
        for pair in pairs:
            payload_lines.append(
                f'{{"poly_ts":"{pair.poly_ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]}",'
                f'"binance_ts":"{pair.binance_ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]}",'
                f'"delta_ms":{pair.delta_ms},'
                f'"poly_price":{pair.poly_price},'
                f'"binance_price":{pair.binance_price},'
                f'"poly_volume":{pair.poly_volume},'
                f'"binance_volume":{pair.binance_volume},'
                f'"poly_side":"{pair.poly_side}",'
                f'"binance_side":"{pair.binance_side}"}}'
            )
        
        payload = "\n".join(payload_lines)
        
        url = f"http://{self.clickhouse_host}:{self.clickhouse_port}/"
        params = {
            "query": insert_query,
            "user": self.clickhouse_user,
            "password": self.clickhouse_password,
            "database": self.clickhouse_database,
        }
        
        async with self._session.post(
            url,
            params=params,
            data=payload,
            headers={"Content-Type": "application/x-ndjson"},
        ) as response:
            if response.status == 200:
                logger.info(f"Stored {len(pairs)} alignment results")
                return len(pairs)
            else:
                error_text = await response.text()
                raise Exception(f"Failed to store results: {error_text}")


async def main(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    hours: int = 1,
    time_window_ms: int = 1000,
    binance_symbol: str = "BTCUSDT",
    store_results: bool = False,
) -> AlignmentResult:
    """
    CLI entry point for time alignment.
    
    Args:
        start_time: Start time in YYYY-MM-DD HH:MM:SS format
        end_time: End time in YYYY-MM-DD HH:MM:SS format
        hours: Number of hours to process (default: 1)
        time_window_ms: Maximum time difference for matching
        binance_symbol: Binance symbol to match
        store_results: Whether to store results in ClickHouse
        
    Returns:
        AlignmentResult with statistics
    """
    # Parse time range
    if start_time:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    else:
        # Default to yesterday at midnight
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        start_dt = today - timedelta(days=1)
    
    if end_time:
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    else:
        end_dt = start_dt + timedelta(hours=hours)
    
    logger.info(f"Time alignment: {start_dt} to {end_dt}")
    
    async with TimeAligner(binance_symbol=binance_symbol) as aligner:
        # Run alignment
        result = await aligner.align_time_range(
            start_time=start_dt,
            end_time=end_dt,
            time_window_ms=time_window_ms,
        )
        
        if result.success and store_results and result.matched_pairs > 0:
            # Get raw pairs and store them
            pairs = await aligner.get_raw_pairs(
                start_time=start_dt,
                end_time=end_dt,
                time_window_ms=time_window_ms,
            )
            await aligner.store_alignment_results(pairs)
        
        return result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="ASOF JOIN Time Aligner for market data synchronization"
    )
    parser.add_argument(
        "--start-time",
        type=str,
        help="Start time in YYYY-MM-DD HH:MM:SS format",
    )
    parser.add_argument(
        "--end-time",
        type=str,
        help="End time in YYYY-MM-DD HH:MM:SS format",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=1,
        help="Number of hours to process (default: 1)",
    )
    parser.add_argument(
        "--time-window-ms",
        type=int,
        default=1000,
        help="Maximum time difference for matching in ms (default: 1000)",
    )
    parser.add_argument(
        "--binance-symbol",
        type=str,
        default="BTCUSDT",
        help="Binance symbol to match (default: BTCUSDT)",
    )
    parser.add_argument(
        "--store-results",
        action="store_true",
        help="Store alignment results in ClickHouse",
    )
    
    args = parser.parse_args()
    
    result = asyncio.run(
        main(
            start_time=args.start_time,
            end_time=args.end_time,
            hours=args.hours,
            time_window_ms=args.time_window_ms,
            binance_symbol=args.binance_symbol,
            store_results=args.store_results,
        )
    )
    
    if result.success:
        print(f"\nAlignment successful!")
        print(f"Matched pairs: {result.matched_pairs}")
        print(f"Time window: {result.time_window_ms}ms")
        if result.stats:
            print(f"\n{result.stats}")
    else:
        print(f"\nAlignment failed: {result.error}")
        exit(1)
