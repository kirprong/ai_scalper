"""
Polymarket CLOB API Client

Async HTTP client for Polymarket CLOB API with Keep-Alive connections,
rate limiting, and secure order signing.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import aiohttp
from aiohttp import ClientSession, ClientTimeout, TCPConnector

from backend.signing import PolymarketSigner, SignedOrder, OrderSide


logger = logging.getLogger(__name__)


# Polymarket CLOB API endpoints
CLOB_API_URLS = {
    137: "https://clob.polymarket.com",  # Polygon Mainnet
    80002: "https://clob.polymarket.com",  # Amoy Testnet (same API)
}


@dataclass
class Market:
    """Polymarket market data"""
    condition_id: str
    question_id: str
    question: str
    description: str
    outcomes: List[str]
    tokens: List[Dict[str, Any]]
    active: bool


@dataclass
class OrderBook:
    """Polymarket order book"""
    market: str
    asset_id: str
    bids: List[Dict[str, Any]]
    asks: List[Dict[str, Any]]


class PolymarketClient:
    """
    Async HTTP client for Polymarket CLOB API
    
    Features:
    - Keep-Alive connections for low latency
    - Rate limiting and retry logic
    - Secure order signing with EIP-712
    - Integration with Vault for key management
    
    Security:
    - Private keys loaded from vault only
    - Keys never transmitted over network
    - No key leakage to logs
    """
    
    def __init__(
        self,
        signer: PolymarketSigner,
        chain_id: int = 137,
        timeout: float = 30.0,
        max_retries: int = 3,
        rate_limit_delay: float = 0.1
    ):
        """
        Initialize Polymarket client
        
        Args:
            signer: PolymarketSigner instance for order signing
            chain_id: Chain ID (default: 137 for Polygon Mainnet)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            rate_limit_delay: Delay between requests for rate limiting
        """
        self.signer = signer
        self.chain_id = chain_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_delay = rate_limit_delay
        
        # Get API URL
        self.base_url = CLOB_API_URLS.get(chain_id, CLOB_API_URLS[137])
        
        # Session will be created on first use
        self._session: Optional[ClientSession] = None
        self._last_request_time = 0.0
    
    async def _get_session(self) -> ClientSession:
        """Get or create HTTP session with Keep-Alive"""
        if self._session is None or self._session.closed:
            # Configure connection pool with Keep-Alive
            connector = TCPConnector(
                limit=10,  # Max connections
                limit_per_host=5,
                keepalive_timeout=30,  # Keep connections alive
                enable_cleanup_closed=True
            )
            
            timeout = ClientTimeout(total=self.timeout)
            
            self._session = ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            )
        
        return self._session
    
    async def _rate_limit(self):
        """Apply rate limiting between requests"""
        current_time = asyncio.get_event_loop().time()
        elapsed = current_time - self._last_request_time
        
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        
        self._last_request_time = asyncio.get_event_loop().time()
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint (without base URL)
            data: Request body data
            params: Query parameters
            
        Returns:
            Response data
            
        Raises:
            Exception: If request fails after all retries
        """
        await self._rate_limit()
        
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(self.max_retries):
            try:
                async with session.request(
                    method,
                    url,
                    json=data,
                    params=params
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:  # Rate limited
                        retry_after = float(response.headers.get("Retry-After", 1.0))
                        logger.warning(f"Rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        error_text = await response.text()
                        logger.error(f"API error {response.status}: {error_text}")
                        
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(1.0 * (attempt + 1))
                            continue
                        
                        raise Exception(f"API error {response.status}: {error_text}")
                        
            except aiohttp.ClientError as e:
                logger.error(f"Request error (attempt {attempt + 1}): {e}")
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                
                raise
        
        raise Exception("Max retries exceeded")
    
    # ==================== Market Endpoints ====================
    
    async def get_markets(self, active_only: bool = True) -> List[Market]:
        """
        Get list of markets
        
        Args:
            active_only: Only return active markets
            
        Returns:
            List of Market objects
        """
        params = {}
        if active_only:
            params["active"] = "true"
        
        data = await self._request("GET", "/markets", params=params)
        
        markets = []
        for item in data:
            markets.append(Market(
                condition_id=item.get("condition_id", ""),
                question_id=item.get("question_id", ""),
                question=item.get("question", ""),
                description=item.get("description", ""),
                outcomes=item.get("outcomes", []),
                tokens=item.get("tokens", []),
                active=item.get("active", False)
            ))
        
        return markets
    
    async def get_market(self, condition_id: str) -> Market:
        """
        Get specific market by condition ID
        
        Args:
            condition_id: Market condition ID
            
        Returns:
            Market object
        """
        data = await self._request("GET", f"/markets/{condition_id}")
        
        return Market(
            condition_id=data.get("condition_id", ""),
            question_id=data.get("question_id", ""),
            question=data.get("question", ""),
            description=data.get("description", ""),
            outcomes=data.get("outcomes", []),
            tokens=data.get("tokens", []),
            active=data.get("active", False)
        )
    
    # ==================== Order Endpoints ====================
    
    async def post_order(self, signed_order: SignedOrder) -> Dict[str, Any]:
        """
        Submit signed order to Polymarket
        
        Args:
            signed_order: SignedOrder from PolymarketSigner
            
        Returns:
            Order response with order_id
        """
        order_dict = self.signer.to_dict(signed_order)
        
        return await self._request("POST", "/orders", data=order_dict)
    
    async def get_orders(self, address: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get orders for address
        
        Args:
            address: Ethereum address (default: signer address)
            
        Returns:
            List of orders
        """
        if address is None:
            address = self.signer.address
        
        params = {"maker": address}
        
        return await self._request("GET", "/orders", params=params)
    
    async def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get specific order by ID
        
        Args:
            order_id: Order ID
            
        Returns:
            Order data
        """
        return await self._request("GET", f"/orders/{order_id}")
    
    async def delete_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel order by ID
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            Cancellation response
        """
        return await self._request("DELETE", f"/orders/{order_id}")
    
    async def cancel_all_orders(self) -> Dict[str, Any]:
        """
        Cancel all orders for signer address
        
        Returns:
            Cancellation response
        """
        params = {"maker": self.signer.address}
        
        return await self._request("DELETE", "/orders", params=params)
    
    # ==================== Order Book Endpoints ====================
    
    async def get_order_book(self, token_id: str) -> OrderBook:
        """
        Get order book for token
        
        Args:
            token_id: Token ID
            
        Returns:
            OrderBook object
        """
        params = {"token_id": token_id}
        
        data = await self._request("GET", "/book", params=params)
        
        return OrderBook(
            market=data.get("market", ""),
            asset_id=data.get("asset_id", ""),
            bids=data.get("bids", []),
            asks=data.get("asks", [])
        )
    
    # ==================== Helper Methods ====================
    
    async def create_and_submit_order(
        self,
        token_id: str,
        side: OrderSide,
        maker_amount: str,
        taker_amount: str,
        nonce: int,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create signed order and submit to Polymarket
        
        Args:
            token_id: Token ID to trade
            side: BUY or SELL
            maker_amount: Amount maker spends
            taker_amount: Amount taker pays
            nonce: Exchange nonce
            **kwargs: Additional order parameters
            
        Returns:
            Order response
        """
        # Sign order
        signed_order = self.signer.sign_order(
            token_id=token_id,
            side=side,
            maker_amount=maker_amount,
            taker_amount=taker_amount,
            nonce=nonce,
            **kwargs
        )
        
        # Submit to API
        return await self.post_order(signed_order)
    
    async def close(self):
        """Close HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
