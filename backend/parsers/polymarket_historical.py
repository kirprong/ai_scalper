"""
Polymarket Historical Data Parser

Fetches historical trade data from Polymarket APIs and inserts into ClickHouse.
Supports filtering for BTC price target markets.

Polymarket API endpoints:
- CLOB API (https://clob.polymarket.com/):
  - GET /markets - list available markets
  - GET /trades - historical trades (requires auth)
  - GET /market/trades/events/{condition_id} - public trade events

- Gamma API (https://gamma-api.polymarket.com/):
  - GET /markets - list markets with more metadata
  - Supports filtering by tag, active status, etc.

Data is transformed to market_data schema:
- symbol: Market identifier (e.g., 'POLY:BTC_100K')
- ts: Timestamp with millisecond precision
- price: Trade price (0-1 probability scale)
- volume: Trade volume
- side: 'buy' or 'sell'
- source: 'polymarket'

Note: For authenticated endpoints, you need to set up API credentials.
See: https://docs.polymarket.com/
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import AsyncIterator, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Constants
POLYMARKET_CLOB_URL = "https://clob.polymarket.com/"
POLYMARKET_GAMMA_URL = "https://gamma-api.polymarket.com/"
POLYMARKET_DATA_URL = "https://polymarket-data.s3.amazonaws.com/"
BATCH_SIZE = 10_000  # Insert in batches of 10k rows
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_HTTP_PORT = os.getenv("CLICKHOUSE_HTTP_PORT", "8123")
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "admin")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "admin123")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "market_data")

# BTC-related market keywords for filtering
BTC_MARKET_KEYWORDS = [
    "BTC",
    "Bitcoin",
    "bitcoin",
    "100k",
    "100K",
    "100000",
    "150k",
    "150K",
    "150000",
    "200k",
    "200K",
    "200000",
]


class TradeSide(str, Enum):
    """Trade side enum matching ClickHouse schema."""
    BUY = "buy"
    SELL = "sell"


@dataclass
class PolymarketTrade:
    """Parsed Polymarket trade record."""
    trade_id: str
    market_id: str
    token_id: str
    price: float  # 0-1 probability scale
    volume: float
    side: TradeSide
    timestamp: datetime
    outcome: str  # 'Yes' or 'No'


@dataclass
class PolymarketMarket:
    """Polymarket market information."""
    condition_id: str
    token_a_id: str  # Yes token
    token_b_id: str  # No token
    question: str
    description: str
    active: bool
    closed: bool


class DownloadResult(BaseModel):
    """Result of a download operation."""
    success: bool
    data: Optional[List[dict]] = None
    error: Optional[str] = None
    rows_downloaded: int = 0


class InsertResult(BaseModel):
    """Result of a database insert operation."""
    success: bool
    rows_inserted: int = 0
    error: Optional[str] = None


class MarketInfo(BaseModel):
    """Market information from Polymarket API."""
    condition_id: str
    question_id: str = ""
    question: str = ""
    description: str = ""
    tokens: List[dict] = Field(default_factory=list)
    active: bool = True
    closed: bool = False
    minimum_tick_size: float = 0.01
    minimum_order_size: float = 1.0


class PolymarketHistoricalParser:
    """Parser for Polymarket historical trade data."""

    def __init__(
        self,
        market_filter: Optional[str] = None,
        clickhouse_host: str = CLICKHOUSE_HOST,
        clickhouse_port: str = CLICKHOUSE_HTTP_PORT,
        clickhouse_user: str = CLICKHOUSE_USER,
        clickhouse_password: str = CLICKHOUSE_PASSWORD,
        clickhouse_database: str = CLICKHOUSE_DATABASE,
        batch_size: int = BATCH_SIZE,
        max_retries: int = MAX_RETRIES,
    ):
        self.market_filter = market_filter
        self.clickhouse_host = clickhouse_host
        self.clickhouse_port = clickhouse_port
        self.clickhouse_user = clickhouse_user
        self.clickhouse_password = clickhouse_password
        self.clickhouse_database = clickhouse_database
        self.batch_size = batch_size
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None
        self._markets_cache: Dict[str, MarketInfo] = {}
        self._btc_markets: List[str] = []

    async def __aenter__(self) -> "PolymarketHistoricalParser":
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

    def _get_api_url(self, endpoint: str) -> str:
        """Generate the full API URL for an endpoint."""
        return urljoin(POLYMARKET_CLOB_URL, endpoint.lstrip("/"))

    async def _fetch_with_retry(
        self,
        url: str,
        params: Optional[dict] = None
    ) -> dict:
        """Fetch data from URL with retry logic."""
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"Fetching {url} (attempt {attempt}/{self.max_retries})")
                async with self._session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    elif response.status == 404:
                        raise FileNotFoundError(f"Data not found for URL: {url}")
                    else:
                        text = await response.text()
                        raise aiohttp.ClientError(
                            f"HTTP {response.status}: {text[:200]}"
                        )
            except (aiohttp.ClientError, FileNotFoundError) as e:
                last_error = e
                logger.warning(f"Fetch failed (attempt {attempt}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(RETRY_DELAY * attempt)

        raise last_error or Exception("Fetch failed after retries")

    def _get_gamma_url(self, endpoint: str) -> str:
        """Generate the full Gamma API URL for an endpoint."""
        return urljoin(POLYMARKET_GAMMA_URL, endpoint.lstrip("/"))

    async def fetch_markets(self) -> List[MarketInfo]:
        """Fetch all available markets from Polymarket CLOB API."""
        url = self._get_api_url("/markets")
        logger.info(f"Fetching markets from {url}")

        try:
            response = await self._fetch_with_retry(url)
            # Handle the response format: {"data": [...], "next_cursor": ...}
            if isinstance(response, dict) and "data" in response:
                data = response["data"]
            else:
                data = response if isinstance(response, list) else [response]

            markets = []

            for item in data:
                try:
                    market = MarketInfo(
                        condition_id=item.get("condition_id", ""),
                        question_id=item.get("question_id", ""),
                        question=item.get("question", ""),
                        description=item.get("description", ""),
                        tokens=item.get("tokens", []),
                        active=item.get("active", True),
                        closed=item.get("closed", False),
                        minimum_tick_size=item.get("minimum_tick_size", 0.01),
                        minimum_order_size=item.get("minimum_order_size", 1.0),
                    )
                    markets.append(market)
                    self._markets_cache[market.condition_id] = market
                except Exception as e:
                    logger.warning(f"Failed to parse market: {e}")
                    continue

            logger.info(f"Fetched {len(markets)} markets")
            return markets

        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []

    async def fetch_markets_gamma(
        self,
        tag: Optional[str] = None,
        active_only: bool = True,
        limit: int = 100,
    ) -> List[MarketInfo]:
        """Fetch markets from Gamma API with more metadata.

        The Gamma API provides more detailed market information and
        supports filtering by tags.

        Args:
            tag: Filter by tag (e.g., "Crypto", "Politics")
            active_only: Only return active markets
            limit: Maximum number of markets to return

        Returns:
            List of MarketInfo objects
        """
        url = self._get_gamma_url("markets")
        params = {"limit": limit}
        if tag:
            params["tag"] = tag
        if active_only:
            params["active"] = "true"

        logger.info(f"Fetching markets from Gamma API: {url} with params {params}")

        try:
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    markets = []

                    for item in data:
                        try:
                            # Gamma API has different field names
                            condition_id = item.get("conditionId", item.get("condition_id", ""))
                            
                            # Parse clobTokenIds if present
                            tokens = []
                            clob_token_ids = item.get("clobTokenIds", "[]")
                            if isinstance(clob_token_ids, str):
                                import json
                                try:
                                    clob_token_ids = json.loads(clob_token_ids)
                                except:
                                    clob_token_ids = []
                            
                            outcomes = item.get("outcomes", "[]")
                            if isinstance(outcomes, str):
                                import json
                                try:
                                    outcomes = json.loads(outcomes)
                                except:
                                    outcomes = []
                            
                            for i, token_id in enumerate(clob_token_ids):
                                tokens.append({
                                    "token_id": token_id,
                                    "outcome": outcomes[i] if i < len(outcomes) else f"Outcome_{i}",
                                })

                            market = MarketInfo(
                                condition_id=condition_id,
                                question_id=item.get("questionId", ""),
                                question=item.get("question", ""),
                                description=item.get("description", ""),
                                tokens=tokens,
                                active=item.get("active", True),
                                closed=item.get("closed", False),
                                minimum_tick_size=item.get("minimum_tick_size", 0.01),
                                minimum_order_size=item.get("minimum_order_size", 1.0),
                            )
                            markets.append(market)
                            self._markets_cache[condition_id] = market
                        except Exception as e:
                            logger.warning(f"Failed to parse Gamma market: {e}")
                            continue

                    logger.info(f"Fetched {len(markets)} markets from Gamma API")
                    return markets
                else:
                    logger.error(f"Gamma API error: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch markets from Gamma API: {e}")
            return []

    async def find_btc_markets(self) -> List[MarketInfo]:
        """Find BTC-related markets using both CLOB and Gamma APIs."""
        if self._btc_markets:
            return [self._markets_cache[m] for m in self._btc_markets if m in self._markets_cache]

        # Try Gamma API first (better metadata)
        gamma_markets = await self.fetch_markets_gamma(tag="Crypto", limit=500)
        
        # Also fetch from CLOB API for completeness
        clob_markets = await self.fetch_markets()
        
        # Combine markets (deduplicate by condition_id)
        all_markets = {m.condition_id: m for m in gamma_markets}
        for m in clob_markets:
            if m.condition_id and m.condition_id not in all_markets:
                all_markets[m.condition_id] = m
        
        markets = list(all_markets.values())
        btc_markets = []

        for market in markets:
            # Check if market question contains BTC-related keywords
            question_lower = market.question.lower()
            description_lower = market.description.lower()

            is_btc_related = any(
                kw.lower() in question_lower or kw.lower() in description_lower
                for kw in BTC_MARKET_KEYWORDS
            )

            if is_btc_related:
                btc_markets.append(market)
                if market.condition_id:
                    self._btc_markets.append(market.condition_id)
                logger.info(
                    f"Found BTC market: {market.question[:50]}... "
                    f"(condition_id: {market.condition_id})"
                )

        logger.info(f"Found {len(btc_markets)} BTC-related markets")
        return btc_markets

    async def fetch_trades(
        self,
        condition_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        before: Optional[int] = None,
        after: Optional[int] = None,
    ) -> List[dict]:
        """Fetch historical trades from Polymarket.

        Args:
            condition_id: The condition ID (market) to filter trades by
            asset_id: The token ID to filter trades by
            before: Unix timestamp to filter trades before this time
            after: Unix timestamp to filter trades after this time

        Returns:
            List of trade records
        """
        url = self._get_api_url("/trades")
        params = {}

        if condition_id:
            params["market"] = condition_id
        if asset_id:
            params["asset_id"] = asset_id
        if before:
            params["before"] = before
        if after:
            params["after"] = after

        logger.info(f"Fetching trades with params: {params}")

        try:
            data = await self._fetch_with_retry(url, params)

            if isinstance(data, list):
                logger.info(f"Fetched {len(data)} trades")
                return data
            else:
                logger.warning(f"Unexpected trades data format: {type(data)}")
                return []

        except FileNotFoundError:
            logger.warning(f"No trades found")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch trades: {e}")
            return []

    async def fetch_market_trades_events(
        self,
        condition_id: str,
    ) -> List[dict]:
        """Fetch public market trade events for a specific condition ID.

        Args:
            condition_id: The condition ID of the market

        Returns:
            List of trade event records
        """
        url = self._get_api_url(f"/market/trades/events/{condition_id}")
        logger.info(f"Fetching market trade events for condition {condition_id}")

        try:
            data = await self._fetch_with_retry(url)

            if isinstance(data, list):
                logger.info(f"Fetched {len(data)} trade events for condition {condition_id}")
                return data
            else:
                logger.warning(f"Unexpected trade events data format: {type(data)}")
                return []

        except FileNotFoundError:
            logger.warning(f"No trade events found for condition {condition_id}")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch market trade events: {e}")
            return []

    async def fetch_price_history(
        self,
        token_id: str,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        fidelity: int = 1,
    ) -> List[dict]:
        """Fetch historical price data for a token.

        Note: This endpoint may not be available on all Polymarket API versions.
        Use fetch_trades() for more reliable historical data.

        Args:
            token_id: The token ID to fetch prices for
            start_ts: Start timestamp (Unix seconds)
            end_ts: End timestamp (Unix seconds)
            fidelity: Data fidelity (1 = minute, 60 = hour)

        Returns:
            List of price data points
        """
        url = self._get_api_url("/prices")
        params = {
            "token_id": token_id,
            "fidelity": fidelity,
        }

        if start_ts:
            params["start_ts"] = start_ts
        if end_ts:
            params["end_ts"] = end_ts

        logger.info(f"Fetching price history for token {token_id}")

        try:
            data = await self._fetch_with_retry(url, params)

            if isinstance(data, list):
                logger.info(f"Fetched {len(data)} price points for token {token_id}")
                return data
            else:
                logger.warning(f"Unexpected price data format: {type(data)}")
                return []

        except FileNotFoundError:
            logger.warning(f"No price history found for token {token_id}")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch price history: {e}")
            return []

    async def fetch_orderbook_history(
        self,
        token_id: str,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
    ) -> List[dict]:
        """Fetch orderbook history for a token.

        Args:
            token_id: The token ID to fetch orderbook for
            start_ts: Start timestamp (Unix seconds)
            end_ts: End timestamp (Unix seconds)

        Returns:
            List of orderbook snapshots
        """
        url = self._get_api_url(f"/orderbook/{token_id}/history")
        params = {}

        if start_ts:
            params["start_ts"] = start_ts
        if end_ts:
            params["end_ts"] = end_ts

        logger.info(f"Fetching orderbook history for token {token_id}")

        try:
            data = await self._fetch_with_retry(url, params)

            if isinstance(data, list):
                logger.info(f"Fetched {len(data)} orderbook snapshots for token {token_id}")
                return data
            elif isinstance(data, dict) and "history" in data:
                return data["history"]
            else:
                logger.warning(f"Unexpected orderbook data format: {type(data)}")
                return []

        except FileNotFoundError:
            logger.warning(f"No orderbook history found for token {token_id}")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch orderbook history: {e}")
            return []

    def _transform_price_to_trade(
        self,
        price_data: dict,
        market: MarketInfo,
        token_id: str,
        outcome: str,
    ) -> Optional[PolymarketTrade]:
        """Transform price data point to trade record.

        Price data format from API:
        {
            "t": timestamp (Unix seconds),
            "p": price (0-1 scale),
            "v": volume (optional)
        }
        """
        try:
            ts = price_data.get("t")
            price = price_data.get("p")
            volume = price_data.get("v", 1.0)

            if ts is None or price is None:
                return None

            # Generate a synthetic trade ID
            trade_id = f"{market.condition_id}_{token_id}_{ts}"

            return PolymarketTrade(
                trade_id=trade_id,
                market_id=market.condition_id,
                token_id=token_id,
                price=float(price),
                volume=float(volume),
                side=TradeSide.BUY,  # Price increases = buying
                timestamp=datetime.utcfromtimestamp(ts),
                outcome=outcome,
            )
        except Exception as e:
            logger.warning(f"Failed to transform price data: {e}")
            return None

    def _transform_trade_data(
        self,
        trade_data: dict,
        market: MarketInfo,
        token_id: str,
        outcome: str,
    ) -> Optional[PolymarketTrade]:
        """Transform trade data to trade record.

        Trade data format from API:
        {
            "id": trade_id,
            "transaction_hash": "...",
            "timestamp": Unix timestamp,
            "price": price (0-1 scale),
            "size": size,
            "side": "BUY" or "SELL",
            ...
        }
        """
        try:
            trade_id = trade_data.get("id", trade_data.get("transaction_hash", ""))
            ts = trade_data.get("timestamp") or trade_data.get("block_timestamp")
            price = trade_data.get("price") or trade_data.get("match_price")
            volume = trade_data.get("size") or trade_data.get("amount")
            side_str = trade_data.get("side", "BUY").upper()

            if ts is None or price is None:
                return None

            # Handle different timestamp formats
            if isinstance(ts, str):
                ts = float(ts)
            if ts > 1e12:  # Milliseconds
                ts = ts / 1000
            elif ts > 1e9 and ts < 2e9:  # Already seconds
                pass

            return PolymarketTrade(
                trade_id=str(trade_id),
                market_id=market.condition_id,
                token_id=token_id,
                price=float(price),
                volume=float(volume) if volume else 1.0,
                side=TradeSide.BUY if side_str == "BUY" else TradeSide.SELL,
                timestamp=datetime.utcfromtimestamp(ts),
                outcome=outcome,
            )
        except Exception as e:
            logger.warning(f"Failed to transform trade data: {e}")
            return None

    def _trade_to_market_data(self, trade: PolymarketTrade) -> dict:
        """Transform PolymarketTrade to market_data schema."""
        # Create a symbol that identifies the market and outcome
        # Format: POLY:<market_hash>:<outcome>
        symbol = f"POLY:{trade.market_id[:8]}:{trade.outcome}"

        return {
            "symbol": symbol,
            "ts": trade.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "price": trade.price,
            "volume": trade.volume,
            "side": trade.side.value,
            "source": "polymarket",
        }

    async def _parse_price_chunks(
        self,
        price_data: List[dict],
        market: MarketInfo,
        token_id: str,
        outcome: str,
    ) -> AsyncIterator[List[dict]]:
        """Parse price data and yield chunks of market data records."""
        batch = []

        for price_point in price_data:
            trade = self._transform_price_to_trade(price_point, market, token_id, outcome)
            if trade:
                market_data = self._trade_to_market_data(trade)
                batch.append(market_data)

                if len(batch) >= self.batch_size:
                    yield batch
                    batch = []

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

    async def process_market_data(
        self,
        market: MarketInfo,
        start_date: datetime,
        end_date: datetime,
    ) -> InsertResult:
        """Process historical data for a single market.

        Args:
            market: Market to process
            start_date: Start date
            end_date: End date

        Returns:
            InsertResult with total rows inserted
        """
        total_inserted = 0
        batch_num = 0

        start_ts = int(start_date.timestamp())
        end_ts = int(end_date.timestamp())

        logger.info(f"Processing market: {market.question[:50]}...")

        # Process each token (Yes and No outcomes)
        for token in market.tokens:
            token_id = token.get("token_id") or token.get("clob_token_ids", [None])[0]
            outcome = token.get("outcome", "Unknown")

            if not token_id:
                logger.warning(f"No token ID found for outcome {outcome}")
                continue

            # Fetch price history
            price_data = await self.fetch_price_history(
                token_id,
                start_ts=start_ts,
                end_ts=end_ts,
                fidelity=1,  # Minute-level data
            )

            if not price_data:
                logger.warning(f"No price data for token {token_id}")
                continue

            # Process and insert
            async for batch in self._parse_price_chunks(price_data, market, token_id, outcome):
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

        logger.info(f"Successfully inserted {total_inserted} records for market {market.condition_id}")
        return InsertResult(success=True, rows_inserted=total_inserted)

    async def download_and_process(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        btc_only: bool = True,
    ) -> dict:
        """Download and process data for a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive), defaults to start_date
            btc_only: Whether to only process BTC-related markets

        Returns:
            Dictionary with processing results
        """
        if end_date is None:
            end_date = start_date

        results = {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "markets_processed": 0,
            "total_rows_inserted": 0,
            "errors": [],
        }

        # Find markets to process
        if btc_only:
            markets = await self.find_btc_markets()
        else:
            markets = await self.fetch_markets()

        if not markets:
            logger.warning("No markets found to process")
            return results

        # Process each market
        for market in markets:
            try:
                insert_result = await self.process_market_data(
                    market, start_date, end_date
                )
                if insert_result.success:
                    results["markets_processed"] += 1
                    results["total_rows_inserted"] += insert_result.rows_inserted
                else:
                    results["errors"].append({
                        "market": market.condition_id,
                        "error": insert_result.error,
                    })
            except Exception as e:
                logger.error(f"Failed to process market {market.condition_id}: {e}")
                results["errors"].append({
                    "market": market.condition_id,
                    "error": str(e),
                })

        return results


async def main(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: int = 1,
    btc_only: bool = True,
) -> dict:
    """Main entry point for CLI.

    Args:
        start_date: Start date in YYYY-MM-DD format (default: yesterday)
        end_date: End date in YYYY-MM-DD format (default: same as start_date)
        days: Number of days to process (default: 1)
        btc_only: Whether to only process BTC-related markets (default: True)

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
        f"Starting Polymarket historical data parser "
        f"from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
    )

    async with PolymarketHistoricalParser() as parser:
        results = await parser.download_and_process(start, end, btc_only=btc_only)

    logger.info(f"Processing complete: {results}")
    return results


def run_cli():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download and process Polymarket historical trade data"
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
    parser.add_argument(
        "--all-markets",
        action="store_true",
        help="Process all markets, not just BTC-related ones",
    )

    args = parser.parse_args()

    # Run async main
    results = asyncio.run(
        main(
            start_date=args.start_date,
            end_date=args.end_date,
            days=args.days,
            btc_only=not args.all_markets,
        )
    )

    # Print summary
    print("\n" + "=" * 60)
    print("PROCESSING SUMMARY")
    print("=" * 60)
    print(f"Date Range: {results['start_date']} to {results['end_date']}")
    print(f"Markets Processed: {results['markets_processed']}")
    print(f"Total Rows Inserted: {results['total_rows_inserted']}")
    if results["errors"]:
        print(f"\nErrors: {len(results['errors'])}")
        for error in results["errors"]:
            print(f" - {error['market']}: {error['error']}")
    print("=" * 60)

    return 0 if not results["errors"] else 1


if __name__ == "__main__":
    exit(run_cli())
