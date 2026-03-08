"""
Binance Futures Historical Data Parser (AggTrades)

Downloads and processes historical AggTrades data from Binance Vision
and inserts into ClickHouse database.

AggTrades CSV format:
- aggregate_trade_id: Unique identifier for the aggregated trade
- price: Trade price
- quantity: Trade quantity
- first_trade_id: First trade ID in the aggregation
- last_trade_id: Last trade ID in the aggregation
- timestamp: Unix timestamp in milliseconds
- is_buyer_maker: Whether the buyer is the maker
- was_best_match: Whether the trade was the best match
"""

import asyncio
import csv
import gzip
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import AsyncIterator, List, Optional
from urllib.parse import urljoin

import aiofiles
import aiohttp
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Constants
BINANCE_VISION_BASE_URL = "https://data.binance.vision/"
BINANCE_FUTURES_URL = "data/futures/um/daily/aggTrades/"
BATCH_SIZE = 100_000  # Insert in batches of 100k rows
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_HTTP_PORT = os.getenv("CLICKHOUSE_HTTP_PORT", "8123")
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "admin")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "admin123")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "market_data")


class TradeSide(str, Enum):
    """Trade side enum matching ClickHouse schema."""
    BUY = "buy"
    SELL = "sell"


@dataclass
class AggTrade:
    """Parsed AggTrade record."""
    aggregate_trade_id: int
    price: float
    quantity: float
    first_trade_id: int
    last_trade_id: int
    timestamp: datetime
    is_buyer_maker: bool
    was_best_match: bool

    @classmethod
    def from_csv_row(cls, row: List[str]) -> "AggTrade":
        """Parse AggTrade from CSV row.
        
        CSV format: aggregate_trade_id, price, quantity, first_trade_id, 
                    last_trade_id, timestamp, is_buyer_maker, was_best_match
        """
        return cls(
            aggregate_trade_id=int(row[0]),
            price=float(row[1]),
            quantity=float(row[2]),
            first_trade_id=int(row[3]),
            last_trade_id=int(row[4]),
            timestamp=datetime.utcfromtimestamp(int(row[5]) / 1000),
            is_buyer_maker=row[6].lower() == "true",
            was_best_match=row[7].lower() == "true",
        )

    def to_market_data(self, symbol: str) -> dict:
        """Transform to market_data schema."""
        return {
            "symbol": symbol,
            "ts": self.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "price": self.price,
            "volume": self.quantity,
            "side": TradeSide.SELL.value if self.is_buyer_maker else TradeSide.BUY.value,
            "source": "binance",
        }


class DownloadResult(BaseModel):
    """Result of a download operation."""
    success: bool
    file_path: Optional[Path] = None
    error: Optional[str] = None
    rows_downloaded: int = 0


class InsertResult(BaseModel):
    """Result of a database insert operation."""
    success: bool
    rows_inserted: int = 0
    error: Optional[str] = None


class BinanceHistoricalParser:
    """Parser for Binance Futures historical AggTrades data."""

    def __init__(
        self,
        symbol: str = "BTCUSDT",
        clickhouse_host: str = CLICKHOUSE_HOST,
        clickhouse_port: str = CLICKHOUSE_HTTP_PORT,
        clickhouse_user: str = CLICKHOUSE_USER,
        clickhouse_password: str = CLICKHOUSE_PASSWORD,
        clickhouse_database: str = CLICKHOUSE_DATABASE,
        batch_size: int = BATCH_SIZE,
        max_retries: int = MAX_RETRIES,
    ):
        self.symbol = symbol.upper()
        self.clickhouse_host = clickhouse_host
        self.clickhouse_port = clickhouse_port
        self.clickhouse_user = clickhouse_user
        self.clickhouse_password = clickhouse_password
        self.clickhouse_database = clickhouse_database
        self.batch_size = batch_size
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "BinanceHistoricalParser":
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

    def _get_download_url(self, date: datetime) -> str:
        """Generate the download URL for a specific date.
        
        URL format: https://data.binance.vision/data/futures/um/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-03-08.zip
        """
        date_str = date.strftime("%Y-%m-%d")
        filename = f"{self.symbol}-aggTrades-{date_str}.zip"
        return urljoin(
            BINANCE_VISION_BASE_URL,
            f"{BINANCE_FUTURES_URL}{self.symbol}/{filename}"
        )

    async def _download_with_retry(self, url: str) -> bytes:
        """Download file with retry logic."""
        last_error = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Downloading {url} (attempt {attempt}/{self.max_retries})")
                async with self._session.get(url) as response:
                    if response.status == 200:
                        data = await response.read()
                        logger.info(f"Downloaded {len(data)} bytes from {url}")
                        return data
                    elif response.status == 404:
                        raise FileNotFoundError(f"Data not found for URL: {url}")
                    else:
                        raise aiohttp.ClientError(
                            f"HTTP {response.status}: {await response.text()}"
                        )
            except (aiohttp.ClientError, FileNotFoundError) as e:
                last_error = e
                logger.warning(f"Download failed (attempt {attempt}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(RETRY_DELAY * attempt)
        
        raise last_error or Exception("Download failed after retries")

    async def download_date(self, date: datetime, output_dir: Optional[Path] = None) -> DownloadResult:
        """Download AggTrades data for a specific date.
        
        Args:
            date: The date to download data for
            output_dir: Optional directory to save the file (uses temp dir if not provided)
        
        Returns:
            DownloadResult with success status and file path
        """
        url = self._get_download_url(date)
        date_str = date.strftime("%Y-%m-%d")
        
        try:
            # Download the zip file
            zip_data = await self._download_with_retry(url)
            
            # Create output directory if needed
            if output_dir is None:
                output_dir = Path(tempfile.mkdtemp(prefix="binance_"))
            else:
                output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save zip file
            zip_path = output_dir / f"{self.symbol}-aggTrades-{date_str}.zip"
            async with aiofiles.open(zip_path, "wb") as f:
                await f.write(zip_data)
            
            logger.info(f"Saved zip file to {zip_path}")
            
            # Extract CSV from zip (zipfile is sync, so we run in executor)
            csv_path = await asyncio.get_event_loop().run_in_executor(
                None, self._extract_csv, zip_path
            )
            
            # Count rows
            row_count = await self._count_csv_rows(csv_path)
            
            return DownloadResult(
                success=True,
                file_path=csv_path,
                rows_downloaded=row_count,
            )
            
        except Exception as e:
            logger.error(f"Failed to download data for {date_str}: {e}")
            return DownloadResult(
                success=False,
                error=str(e),
            )

    def _extract_csv(self, zip_path: Path) -> Path:
        """Extract CSV from zip file (sync operation)."""
        import zipfile
        
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Find CSV file in the archive
            csv_files = [f for f in zf.namelist() if f.endswith(".csv")]
            if not csv_files:
                raise ValueError(f"No CSV file found in {zip_path}")
            
            # Extract to same directory
            zf.extractall(zip_path.parent)
            csv_path = zip_path.parent / csv_files[0]
            logger.info(f"Extracted CSV to {csv_path}")
            return csv_path

    async def _count_csv_rows(self, csv_path: Path) -> int:
        """Count rows in CSV file."""
        count = 0
        async with aiofiles.open(csv_path, "r") as f:
            async for _ in f:
                count += 1
        # Subtract header row if present
        return max(0, count - 1)

    async def _parse_csv_chunks(
        self, csv_path: Path
    ) -> AsyncIterator[List[dict]]:
        """Parse CSV file and yield chunks of market data records."""
        batch = []
        
        # Use sync file reading with asyncio for CSV parsing
        # (aiofiles doesn't work well with csv module)
        def read_csv():
            with open(csv_path, "r", newline="") as f:
                reader = csv.reader(f)
                header = next(reader, None)  # Skip header
                for row in reader:
                    if row:
                        yield row
        
        # Run CSV reading in executor to avoid blocking
        loop = asyncio.get_event_loop()
        csv_iterator = await loop.run_in_executor(None, lambda: list(read_csv()))
        
        for row in csv_iterator:
            try:
                agg_trade = AggTrade.from_csv_row(row)
                market_data = agg_trade.to_market_data(self.symbol)
                batch.append(market_data)
                
                if len(batch) >= self.batch_size:
                    yield batch
                    batch = []
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse row {row}: {e}")
                continue
        
        # Yield remaining records
        if batch:
            yield batch

    async def _insert_batch(self, batch: List[dict]) -> InsertResult:
        """Insert a batch of records into ClickHouse."""
        if not batch:
            return InsertResult(success=True, rows_inserted=0)
        
        # Build INSERT query
        query = f"""
        INSERT INTO {self.clickhouse_database}.market_data
        (symbol, ts, price, volume, side, source)
        FORMAT JSONEachRow
        """
        
        # Build JSON payload
        payload = "\n".join(
            '{"symbol":"%s","ts":"%s","price":%s,"volume":%s,"side":"%s","source":"%s"}' % (
                row["symbol"],
                row["ts"],
                row["price"],
                row["volume"],
                row["side"],
                row["source"],
            )
            for row in batch
        )
        
        url = f"http://{self.clickhouse_host}:{self.clickhouse_port}/"
        params = {
            "query": query,
            "user": self.clickhouse_user,
            "password": self.clickhouse_password,
            "database": self.clickhouse_database,
        }
        
        try:
            async with self._session.post(
                url,
                params=params,
                data=payload,
                headers={"Content-Type": "application/x-ndjson"},
            ) as response:
                if response.status == 200:
                    return InsertResult(success=True, rows_inserted=len(batch))
                else:
                    error_text = await response.text()
                    logger.error(f"ClickHouse insert failed: {error_text}")
                    return InsertResult(
                        success=False,
                        error=f"HTTP {response.status}: {error_text}",
                    )
        except aiohttp.ClientError as e:
            logger.error(f"ClickHouse connection error: {e}")
            return InsertResult(success=False, error=str(e))

    async def process_csv(self, csv_path: Path) -> InsertResult:
        """Process CSV file and insert into ClickHouse.
        
        Args:
            csv_path: Path to the CSV file
        
        Returns:
            InsertResult with total rows inserted
        """
        total_inserted = 0
        batch_num = 0
        
        logger.info(f"Processing CSV file: {csv_path}")
        
        async for batch in self._parse_csv_chunks(csv_path):
            batch_num += 1
            logger.info(
                f"Inserting batch {batch_num} "
                f"({len(batch)} records, total so far: {total_inserted})"
            )
            
            # Retry insert
            for attempt in range(1, self.max_retries + 1):
                result = await self._insert_batch(batch)
                if result.success:
                    total_inserted += result.rows_inserted
                    break
                else:
                    logger.warning(
                        f"Insert failed (attempt {attempt}/{self.max_retries}): "
                        f"{result.error}"
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(RETRY_DELAY * attempt)
            else:
                logger.error(
                    f"Failed to insert batch {batch_num} after {self.max_retries} attempts"
                )
                return InsertResult(
                    success=False,
                    rows_inserted=total_inserted,
                    error=f"Failed to insert batch {batch_num}",
                )
        
        logger.info(f"Successfully inserted {total_inserted} records")
        return InsertResult(success=True, rows_inserted=total_inserted)

    async def download_and_process(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        cleanup: bool = True,
    ) -> dict:
        """Download and process data for a date range.
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive), defaults to start_date
            cleanup: Whether to delete downloaded files after processing
        
        Returns:
            Dictionary with processing results
        """
        if end_date is None:
            end_date = start_date
        
        results = {
            "symbol": self.symbol,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "days_processed": 0,
            "total_rows_inserted": 0,
            "errors": [],
        }
        
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            logger.info(f"Processing date: {date_str}")
            
            # Download
            download_result = await self.download_date(current_date)
            if not download_result.success:
                results["errors"].append({
                    "date": date_str,
                    "error": download_result.error,
                })
                current_date += timedelta(days=1)
                continue
            
            # Process
            insert_result = await self.process_csv(download_result.file_path)
            if insert_result.success:
                results["days_processed"] += 1
                results["total_rows_inserted"] += insert_result.rows_inserted
            else:
                results["errors"].append({
                    "date": date_str,
                    "error": insert_result.error,
                })
            
            # Cleanup
            if cleanup and download_result.file_path:
                try:
                    csv_path = download_result.file_path
                    zip_path = csv_path.with_suffix(".zip")
                    if csv_path.exists():
                        csv_path.unlink()
                    if zip_path.exists():
                        zip_path.unlink()
                    # Try to remove the parent directory if empty
                    try:
                        csv_path.parent.rmdir()
                    except OSError:
                        pass
                    logger.info(f"Cleaned up temporary files for {date_str}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup: {e}")
            
            current_date += timedelta(days=1)
        
        return results


async def main(
    symbol: str = "BTCUSDT",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: int = 1,
) -> dict:
    """Main entry point for CLI.
    
    Args:
        symbol: Trading pair symbol (default: BTCUSDT)
        start_date: Start date in YYYY-MM-DD format (default: yesterday)
        end_date: End date in YYYY-MM-DD format (default: same as start_date)
        days: Number of days to process (default: 1)
    
    Returns:
        Dictionary with processing results
    """
    # Parse dates
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        # Default to yesterday
        start = datetime.utcnow() - timedelta(days=1)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        end = start + timedelta(days=days - 1)
    
    logger.info(
        f"Starting Binance historical data parser for {symbol} "
        f"from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
    )
    
    async with BinanceHistoricalParser(symbol=symbol) as parser:
        results = await parser.download_and_process(start, end)
    
    logger.info(f"Processing complete: {results}")
    return results


def run_cli():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Download and process Binance Futures historical AggTrades data"
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default="BTCUSDT",
        help="Trading pair symbol (default: BTCUSDT)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date in YYYY-MM-DD format (default: yesterday)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date in YYYY-MM-DD format (default: same as start-date)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of days to process (default: 1)",
    )
    
    args = parser.parse_args()
    
    # Run async main
    results = asyncio.run(
        main(
            symbol=args.symbol,
            start_date=args.start_date,
            end_date=args.end_date,
            days=args.days,
        )
    )
    
    # Print summary
    print("\n" + "=" * 60)
    print("PROCESSING SUMMARY")
    print("=" * 60)
    print(f"Symbol: {results['symbol']}")
    print(f"Date Range: {results['start_date']} to {results['end_date']}")
    print(f"Days Processed: {results['days_processed']}")
    print(f"Total Rows Inserted: {results['total_rows_inserted']}")
    if results["errors"]:
        print(f"\nErrors: {len(results['errors'])}")
        for error in results["errors"]:
            print(f"  - {error['date']}: {error['error']}")
    print("=" * 60)
    
    return 0 if not results["errors"] else 1


if __name__ == "__main__":
    exit(run_cli())
