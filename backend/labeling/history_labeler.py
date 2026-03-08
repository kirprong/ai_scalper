"""
Automatic History Labeling for Golden Boxes

This module provides automatic labeling of historical market data
with Is_Golden_Box tags for ML training.

The labeling process:
1. Run Golden Rectangle detector on historical data
2. For each detected rectangle, label all data points within the box:
   - Is_Golden_Box = 1 for timestamps within box boundaries
   - Is_Golden_Box = 0 for timestamps outside boxes
3. Store labels in ClickHouse database

Usage:
    from backend.labeling import run_labeling_pipeline
    
    # Run full labeling pipeline
    results = run_labeling_pipeline(
        symbol="BTCUSDT",
        start_time="2026-01-01",
        end_time="2026-03-01"
    )
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path

import numpy as np
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.detection import find_rectangles, GoldenRectangle, RectangleConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class LabelingConfig:
    """Configuration for history labeling."""
    # Detection settings
    window_minutes: int = 15
    min_height_pct: float = 5.0
    min_touch_count: int = 2
    
    # Batch processing settings
    batch_size: int = 10000  # Number of rows per batch
    chunk_hours: int = 24    # Hours per chunk for detection
    
    # Database settings
    clickhouse_host: str = field(default_factory=lambda: os.getenv('CLICKHOUSE_HOST', 'localhost'))
    clickhouse_port: int = field(default_factory=lambda: int(os.getenv('CLICKHOUSE_HTTP_PORT', '8123')))
    clickhouse_user: str = field(default_factory=lambda: os.getenv('CLICKHOUSE_USER', 'admin'))
    clickhouse_password: str = field(default_factory=lambda: os.getenv('CLICKHOUSE_PASSWORD', 'admin123'))
    clickhouse_database: str = field(default_factory=lambda: os.getenv('CLICKHOUSE_DB', 'market_data'))
    
    # Labeling settings
    label_column: str = "is_golden_box"
    use_separate_table: bool = True  # If True, create separate labels table


@dataclass
class LabelingResult:
    """Result of a labeling operation."""
    symbol: str
    total_rows: int = 0
    labeled_rows: int = 0
    golden_box_rows: int = 0
    rectangles_found: int = 0
    start_time: datetime = None
    end_time: datetime = None
    processing_time_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "symbol": self.symbol,
            "total_rows": self.total_rows,
            "labeled_rows": self.labeled_rows,
            "golden_box_rows": self.golden_box_rows,
            "rectangles_found": self.rectangles_found,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "processing_time_seconds": self.processing_time_seconds,
            "errors": self.errors
        }


def label_data_point(
    ts: datetime, 
    price: float, 
    rectangles: List[GoldenRectangle]
) -> int:
    """
    Label a data point based on whether it falls within a Golden Rectangle.
    
    Args:
        ts: Timestamp of the data point
        price: Price of the data point
        rectangles: List of detected Golden Rectangles
        
    Returns:
        1 if point is inside any golden rectangle, 0 otherwise
        
    Example:
        >>> from datetime import datetime
        >>> from backend.detection import GoldenRectangle
        >>> rect = GoldenRectangle(
        ...     ts_start=datetime(2026, 1, 1, 10, 0),
        ...     ts_end=datetime(2026, 1, 1, 10, 15),
        ...     price_min=100.0,
        ...     price_max=105.0
        ... )
        >>> label_data_point(datetime(2026, 1, 1, 10, 5), 102.0, [rect])
        1
        >>> label_data_point(datetime(2026, 1, 1, 10, 5), 110.0, [rect])
        0
    """
    for rect in rectangles:
        # Check time bounds
        if rect.ts_start and rect.ts_end:
            if not (rect.ts_start <= ts <= rect.ts_end):
                continue
        
        # Check price bounds
        if rect.price_min <= price <= rect.price_max:
            return 1
    
    return 0


def label_data_batch(
    df: pd.DataFrame,
    rectangles: List[GoldenRectangle],
    ts_column: str = "ts",
    price_column: str = "price"
) -> pd.DataFrame:
    """
    Label a batch of data points efficiently.
    
    Args:
        df: DataFrame with timestamp and price columns
        rectangles: List of detected Golden Rectangles
        ts_column: Name of the timestamp column
        price_column: Name of the price column
        
    Returns:
        DataFrame with added 'is_golden_box' column
    """
    if len(df) == 0:
        return df
    
    df = df.copy()
    
    # Initialize all labels to 0
    df['is_golden_box'] = 0
    
    if not rectangles:
        return df
    
    # Convert timestamps to datetime if needed
    if not pd.api.types.is_datetime64_any_dtype(df[ts_column]):
        df[ts_column] = pd.to_datetime(df[ts_column])
    
    # Label each rectangle's data points
    for rect in rectangles:
        if not rect.ts_start or not rect.ts_end:
            continue
            
        # Create mask for this rectangle
        time_mask = (df[ts_column] >= rect.ts_start) & (df[ts_column] <= rect.ts_end)
        price_mask = (df[price_column] >= rect.price_min) & (df[price_column] <= rect.price_max)
        
        # Combine masks and update labels
        combined_mask = time_mask & price_mask
        df.loc[combined_mask, 'is_golden_box'] = 1
    
    return df


class ClickHouseLabelClient:
    """Client for interacting with ClickHouse for labeling operations."""
    
    def __init__(self, config: LabelingConfig):
        self.config = config
        self.base_url = f"http://{config.clickhouse_host}:{config.clickhouse_port}"
        
    def _execute(self, query: str, params: Optional[Dict] = None) -> Optional[str]:
        """Execute a SQL query against ClickHouse."""
        import requests
        from urllib.parse import quote_plus
        
        request_params = {
            'user': self.config.clickhouse_user,
            'password': self.config.clickhouse_password,
            'database': self.config.clickhouse_database,
        }
        
        if params:
            request_params.update({k: str(v) for k, v in params.items()})
        
        try:
            response = requests.post(
                self.base_url,
                params=request_params,
                data=query,
                timeout=60
            )
            response.raise_for_status()
            return response.text.strip() if response.text else None
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def ping(self) -> bool:
        """Check if ClickHouse is reachable."""
        import requests
        try:
            response = requests.get(f"{self.base_url}/ping", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def fetch_data_chunk(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        offset: int = 0,
        limit: int = 10000
    ) -> pd.DataFrame:
        """
        Fetch a chunk of market data for labeling.
        
        Args:
            symbol: Trading pair symbol
            start_time: Start of time range
            end_time: End of time range
            offset: Offset for pagination
            limit: Maximum rows to fetch
            
        Returns:
            DataFrame with market data
        """
        query = f"""
        SELECT 
            symbol,
            ts,
            price,
            volume,
            side,
            source
        FROM market_data
        WHERE symbol = '{symbol}'
            AND ts >= '{start_time.strftime('%Y-%m-%d %H:%M:%S')}'
            AND ts <= '{end_time.strftime('%Y-%m-%d %H:%M:%S')}'
        ORDER BY ts
        LIMIT {limit}
        OFFSET {offset}
        FORMAT JSONEachRow
        """
        
        result = self._execute(query)
        
        if not result:
            return pd.DataFrame()
        
        import json
        rows = [json.loads(line) for line in result.strip().split('\n') if line]
        
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame(rows)
        df['ts'] = pd.to_datetime(df['ts'])
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        
        return df
    
    def count_data_points(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> int:
        """Count data points for a symbol in a time range."""
        where_clauses = [f"symbol = '{symbol}'"]
        
        if start_time:
            where_clauses.append(f"ts >= '{start_time.strftime('%Y-%m-%d %H:%M:%S')}'")
        if end_time:
            where_clauses.append(f"ts <= '{end_time.strftime('%Y-%m-%d %H:%M:%S')}'")
        
        query = f"""
        SELECT COUNT(*) as count
        FROM market_data
        WHERE {' AND '.join(where_clauses)}
        """
        
        result = self._execute(query)
        return int(result.strip()) if result else 0
    
    def insert_labels(
        self,
        df: pd.DataFrame,
        label_column: str = "is_golden_box"
    ) -> int:
        """
        Insert labels into the labels table.
        
        Args:
            df: DataFrame with ts, symbol, and label columns
            label_column: Name of the label column
            
        Returns:
            Number of rows inserted
        """
        if len(df) == 0:
            return 0
        
        # Prepare data for insertion
        values = []
        for _, row in df.iterrows():
            ts_str = row['ts'].strftime('%Y-%m-%d %H:%M:%S.%f')[:23] if pd.notna(row['ts']) else ''
            symbol = row.get('symbol', '')
            label = int(row.get(label_column, 0))
            values.append(f"('{symbol}', '{ts_str}', {label})")
        
        # Insert in batches
        batch_size = 1000
        total_inserted = 0
        
        for i in range(0, len(values), batch_size):
            batch_values = values[i:i + batch_size]
            query = f"""
            INSERT INTO golden_box_labels (symbol, ts, is_golden_box)
            VALUES {','.join(batch_values)}
            """
            self._execute(query)
            total_inserted += len(batch_values)
        
        return total_inserted
    
    def update_labels_in_place(
        self,
        df: pd.DataFrame,
        label_column: str = "is_golden_box"
    ) -> int:
        """
        Update labels directly in market_data table (alternative approach).
        
        Note: ClickHouse doesn't support UPDATE efficiently, so we use
        a different approach with ALTER TABLE UPDATE.
        
        Args:
            df: DataFrame with ts, symbol, and label columns
            label_column: Name of the label column
            
        Returns:
            Number of rows updated
        """
        if len(df) == 0:
            return 0
        
        # Filter only golden box rows (is_golden_box = 1)
        golden_rows = df[df[label_column] == 1]
        
        if len(golden_rows) == 0:
            return 0
        
        # Update each golden box row
        updated = 0
        for _, row in golden_rows.iterrows():
            ts_str = row['ts'].strftime('%Y-%m-%d %H:%M:%S') if pd.notna(row['ts']) else ''
            symbol = row.get('symbol', '')
            
            query = f"""
            ALTER TABLE market_data
            UPDATE is_golden_box = 1
            WHERE symbol = '{symbol}' AND ts = '{ts_str}'
            """
            self._execute(query)
            updated += 1
        
        return updated
    
    def get_label_count(self, symbol: Optional[str] = None) -> int:
        """Get count of labeled golden box data points."""
        if symbol:
            query = f"SELECT COUNT(*) FROM golden_box_labels WHERE symbol = '{symbol}' AND is_golden_box = 1"
        else:
            query = "SELECT COUNT(*) FROM golden_box_labels WHERE is_golden_box = 1"
        
        result = self._execute(query)
        return int(result.strip()) if result else 0
    
    def create_labels_table(self) -> bool:
        """Create the golden_box_labels table if it doesn't exist."""
        query = """
        CREATE TABLE IF NOT EXISTS golden_box_labels
        (
            symbol String,
            ts DateTime64(3),
            is_golden_box UInt8,
            created_at DateTime DEFAULT now(),
            
            INDEX idx_symbol symbol TYPE bloom_filter GRANULARITY 1,
            INDEX idx_ts ts TYPE minmax GRANULARITY 1
        )
        ENGINE = MergeTree()
        ORDER BY (symbol, ts)
        SETTINGS index_granularity = 8192
        """
        
        try:
            self._execute(query)
            logger.info("Created golden_box_labels table")
            return True
        except Exception as e:
            logger.error(f"Failed to create labels table: {e}")
            return False
    
    def add_column_to_market_data(self) -> bool:
        """Add is_golden_box column to market_data table if it doesn't exist."""
        query = """
        ALTER TABLE market_data ADD COLUMN IF NOT EXISTS is_golden_box UInt8 DEFAULT 0
        """
        
        try:
            self._execute(query)
            logger.info("Added is_golden_box column to market_data table")
            return True
        except Exception as e:
            logger.warning(f"Could not add column (may already exist): {e}")
            return True  # Continue even if column exists


class HistoryLabeler:
    """
    Main class for labeling historical market data with Golden Box tags.
    
    This class orchestrates the labeling pipeline:
    1. Fetch historical data from ClickHouse
    2. Detect Golden Rectangles
    3. Label data points
    4. Store labels back to ClickHouse
    
    Example:
        >>> config = LabelingConfig(window_minutes=15, min_height_pct=5.0)
        >>> labeler = HistoryLabeler(config)
        >>> result = labeler.label_symbol("BTCUSDT", "2026-01-01", "2026-03-01")
        >>> print(f"Labeled {result.golden_box_rows} golden box rows")
    """
    
    def __init__(self, config: Optional[LabelingConfig] = None):
        self.config = config or LabelingConfig()
        self.client = ClickHouseLabelClient(self.config)
        
    def _parse_time(self, time_input: Any) -> datetime:
        """Parse time input to datetime."""
        if isinstance(time_input, datetime):
            return time_input
        if isinstance(time_input, str):
            return pd.to_datetime(time_input).to_pydatetime()
        raise ValueError(f"Cannot parse time: {time_input}")
    
    def label_symbol(
        self,
        symbol: str,
        start_time: Any,
        end_time: Any,
        dry_run: bool = False
    ) -> LabelingResult:
        """
        Label all data for a symbol in a time range.
        
        Args:
            symbol: Trading pair symbol
            start_time: Start of time range
            end_time: End of time range
            dry_run: If True, don't write to database
            
        Returns:
            LabelingResult with statistics
        """
        import time
        start_process_time = time.time()
        
        start_dt = self._parse_time(start_time)
        end_dt = self._parse_time(end_time)
        
        result = LabelingResult(
            symbol=symbol,
            start_time=start_dt,
            end_time=end_dt
        )
        
        logger.info(f"Starting labeling for {symbol} from {start_dt} to {end_dt}")
        
        # Check connection
        if not self.client.ping():
            result.errors.append("Cannot connect to ClickHouse")
            return result
        
        # Create labels table if needed
        if not dry_run:
            self.client.create_labels_table()
        
        # Get total count
        total_count = self.client.count_data_points(symbol, start_dt, end_dt)
        result.total_rows = total_count
        logger.info(f"Found {total_count} data points to process")
        
        if total_count == 0:
            logger.warning("No data points found in specified range")
            return result
        
        # Process in chunks
        chunk_duration = timedelta(hours=self.config.chunk_hours)
        current_start = start_dt
        all_rectangles = []
        total_labeled = 0
        total_golden = 0
        
        while current_start < end_dt:
            current_end = min(current_start + chunk_duration, end_dt)
            
            logger.info(f"Processing chunk: {current_start} to {current_end}")
            
            # Fetch data for this chunk
            offset = 0
            chunk_rectangles = []
            
            while True:
                df = self.client.fetch_data_chunk(
                    symbol=symbol,
                    start_time=current_start,
                    end_time=current_end,
                    offset=offset,
                    limit=self.config.batch_size
                )
                
                if len(df) == 0:
                    break
                
                # Detect rectangles in this batch
                detection_config = RectangleConfig(
                    window_minutes=self.config.window_minutes,
                    min_height_pct=self.config.min_height_pct,
                    min_touch_count=self.config.min_touch_count
                )
                
                rectangles = find_rectangles(
                    df=df,
                    window_minutes=self.config.window_minutes,
                    min_height_pct=self.config.min_height_pct,
                    symbol=symbol,
                    config=detection_config
                )
                
                chunk_rectangles.extend(rectangles)
                
                # Label this batch
                labeled_df = label_data_batch(df, rectangles)
                
                # Count golden box rows
                golden_count = (labeled_df['is_golden_box'] == 1).sum()
                total_golden += golden_count
                
                # Store labels
                if not dry_run and len(labeled_df) > 0:
                    inserted = self.client.insert_labels(labeled_df)
                    total_labeled += inserted
                
                offset += self.config.batch_size
                
                # Break if we got less than batch_size (end of data)
                if len(df) < self.config.batch_size:
                    break
            
            all_rectangles.extend(chunk_rectangles)
            logger.info(f"Found {len(chunk_rectangles)} rectangles in chunk")
            
            current_start = current_end
        
        # Remove duplicate rectangles
        unique_rectangles = list({r.box_id: r for r in all_rectangles}.values())
        result.rectangles_found = len(unique_rectangles)
        result.labeled_rows = total_labeled
        result.golden_box_rows = total_golden
        result.processing_time_seconds = time.time() - start_process_time
        
        logger.info(f"Labeling complete: {result.rectangles_found} rectangles, "
                   f"{result.golden_box_rows} golden box rows")
        
        return result
    
    def get_label_statistics(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics about labeled data."""
        golden_count = self.client.get_label_count(symbol)
        
        return {
            "golden_box_count": golden_count,
            "symbol": symbol
        }


def run_labeling_pipeline(
    symbol: str,
    start_time: Any,
    end_time: Any,
    config: Optional[LabelingConfig] = None,
    dry_run: bool = False
) -> LabelingResult:
    """
    Convenience function to run the full labeling pipeline.
    
    Args:
        symbol: Trading pair symbol
        start_time: Start of time range
        end_time: End of time range
        config: Optional labeling configuration
        dry_run: If True, don't write to database
        
    Returns:
        LabelingResult with statistics
        
    Example:
        >>> result = run_labeling_pipeline(
        ...     symbol="BTCUSDT",
        ...     start_time="2026-01-01",
        ...     end_time="2026-03-01"
        ... )
        >>> print(f"Found {result.golden_box_rows} golden box data points")
    """
    labeler = HistoryLabeler(config)
    return labeler.label_symbol(symbol, start_time, end_time, dry_run)


def main():
    """CLI entry point for running labeling."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Label historical data with Golden Box tags')
    parser.add_argument('--symbol', required=True, help='Trading pair symbol (e.g., BTCUSDT)')
    parser.add_argument('--start', required=True, help='Start time (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--end', required=True, help='End time (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--window-minutes', type=int, default=15, help='Detection window in minutes')
    parser.add_argument('--min-height-pct', type=float, default=5.0, help='Minimum box height percentage')
    parser.add_argument('--batch-size', type=int, default=10000, help='Batch size for processing')
    parser.add_argument('--dry-run', action='store_true', help='Run without writing to database')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    config = LabelingConfig(
        window_minutes=args.window_minutes,
        min_height_pct=args.min_height_pct,
        batch_size=args.batch_size
    )
    
    logger.info(f"Starting labeling pipeline for {args.symbol}")
    logger.info(f"Time range: {args.start} to {args.end}")
    logger.info(f"Config: window={args.window_minutes}min, min_height={args.min_height_pct}%")
    
    result = run_labeling_pipeline(
        symbol=args.symbol,
        start_time=args.start,
        end_time=args.end,
        config=config,
        dry_run=args.dry_run
    )
    
    # Print results
    print("\n" + "="*60)
    print("LABELING RESULTS")
    print("="*60)
    print(f"Symbol: {result.symbol}")
    print(f"Time Range: {result.start_time} to {result.end_time}")
    print(f"Total Rows: {result.total_rows}")
    print(f"Rows Labeled: {result.labeled_rows}")
    print(f"Golden Box Rows: {result.golden_box_rows}")
    print(f"Rectangles Found: {result.rectangles_found}")
    print(f"Processing Time: {result.processing_time_seconds:.2f}s")
    
    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"  - {error}")
    
    print("="*60)
    
    return 0 if not result.errors else 1


if __name__ == '__main__':
    sys.exit(main())
