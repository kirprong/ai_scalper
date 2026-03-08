"""
Binance Futures WebSocket Client.

This module provides a live WebSocket client for streaming real-time
market data from Binance Futures, including mark price and order book depth.

Features:
- Async WebSocket client using websockets library
- Fast JSON parsing using ujson
- Auto-reconnect on disconnect
- Ping/pong handling
- Dynamic subscribe/unsubscribe to streams
- Callback-based message handling
- Error handling and logging
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

try:
    import ujson as json
except ImportError:
    import json  # type: ignore

import websockets
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed, ConnectionClosedError

logger = logging.getLogger(__name__)


class StreamType(Enum):
    """Binance WebSocket stream types."""
    MARK_PRICE = "markPrice"
    MARK_PRICE_1S = "markPrice@1s"
    DEPTH5 = "depth5"
    DEPTH5_100MS = "depth5@100ms"


@dataclass
class MarkPriceData:
    """Mark price stream data model."""
    symbol: str
    mark_price: float
    index_price: float
    estimated_settle_price: float
    funding_rate: float
    next_funding_time: int
    event_time: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarkPriceData":
        """Create MarkPriceData from dictionary."""
        return cls(
            symbol=data.get("s", ""),
            mark_price=float(data.get("p", 0)),
            index_price=float(data.get("i", 0)),
            estimated_settle_price=float(data.get("P", 0)),
            funding_rate=float(data.get("r", 0)),
            next_funding_time=int(data.get("T", 0)),
            event_time=int(data.get("E", 0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "markPrice": self.mark_price,
            "indexPrice": self.index_price,
            "estimatedSettlePrice": self.estimated_settle_price,
            "fundingRate": self.funding_rate,
            "nextFundingTime": self.next_funding_time,
            "eventTime": self.event_time,
        }


@dataclass
class DepthData:
    """Order book depth stream data model."""
    symbol: str
    bids: List[List[float]]  # [[price, qty], ...]
    asks: List[List[float]]  # [[price, qty], ...]
    last_update_id: int
    event_time: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DepthData":
        """Create DepthData from dictionary."""
        # Parse bids and asks to float
        bids = [[float(p), float(q)] for p, q in data.get("b", [])]
        asks = [[float(p), float(q)] for p, q in data.get("a", [])]
        
        return cls(
            symbol=data.get("s", ""),
            bids=bids,
            asks=asks,
            last_update_id=int(data.get("lastUpdateId", 0)),
            event_time=int(data.get("E", 0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "bids": self.bids,
            "asks": self.asks,
            "lastUpdateId": self.last_update_id,
            "eventTime": self.event_time,
        }


class MarkPriceHandler:
    """Handler for mark price messages."""

    def __init__(self, callback: Optional[Callable[[MarkPriceData], Any]] = None):
        """
        Initialize mark price handler.

        Args:
            callback: Async or sync callback function for mark price data
        """
        self.callback = callback

    async def handle(self, data: Dict[str, Any]) -> MarkPriceData:
        """
        Handle mark price message.

        Args:
            data: Raw message data

        Returns:
            Parsed MarkPriceData object
        """
        mark_price_data = MarkPriceData.from_dict(data)
        
        if self.callback:
            result = self.callback(mark_price_data)
            if asyncio.iscoroutine(result):
                await result
        
        return mark_price_data


class DepthHandler:
    """Handler for depth messages."""

    def __init__(self, callback: Optional[Callable[[DepthData], Any]] = None):
        """
        Initialize depth handler.

        Args:
            callback: Async or sync callback function for depth data
        """
        self.callback = callback

    async def handle(self, data: Dict[str, Any]) -> DepthData:
        """
        Handle depth message.

        Args:
            data: Raw message data

        Returns:
            Parsed DepthData object
        """
        depth_data = DepthData.from_dict(data)
        
        if self.callback:
            result = self.callback(depth_data)
            if asyncio.iscoroutine(result):
                await result
        
        return depth_data


class BinanceStreamManager:
    """Manages multiple stream subscriptions."""

    def __init__(self):
        """Initialize stream manager."""
        self._active_streams: Dict[str, Set[str]] = {}  # symbol -> set of stream types
        self._stream_handlers: Dict[str, Any] = {}  # stream_name -> handler

    def add_stream(self, symbol: str, stream_type: StreamType) -> str:
        """
        Add a stream subscription.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            stream_type: Type of stream

        Returns:
            Stream name
        """
        stream_name = f"{symbol.lower()}@{stream_type.value}"
        
        if symbol not in self._active_streams:
            self._active_streams[symbol] = set()
        
        self._active_streams[symbol].add(stream_type.value)
        
        return stream_name

    def remove_stream(self, symbol: str, stream_type: StreamType) -> str:
        """
        Remove a stream subscription.

        Args:
            symbol: Trading symbol
            stream_type: Type of stream

        Returns:
            Stream name
        """
        stream_name = f"{symbol.lower()}@{stream_type.value}"
        
        if symbol in self._active_streams:
            self._active_streams[symbol].discard(stream_type.value)
            if not self._active_streams[symbol]:
                del self._active_streams[symbol]
        
        return stream_name

    def get_stream_names(self) -> List[str]:
        """
        Get all active stream names.

        Returns:
            List of stream names
        """
        streams = []
        for symbol, stream_types in self._active_streams.items():
            for stream_type in stream_types:
                streams.append(f"{symbol.lower()}@{stream_type}")
        return streams

    def get_combined_url(self, base_url: str = "wss://fstream.binance.com/stream") -> str:
        """
        Get combined stream URL.

        Args:
            base_url: Base WebSocket URL

        Returns:
            Combined stream URL
        """
        streams = self.get_stream_names()
        if not streams:
            return base_url
        
        stream_str = "/".join(streams)
        return f"{base_url}?streams={stream_str}"

    def is_empty(self) -> bool:
        """Check if no streams are active."""
        return len(self._active_streams) == 0

    def clear(self) -> None:
        """Clear all stream subscriptions."""
        self._active_streams.clear()


class BinanceWebSocketClient:
    """
    Binance Futures WebSocket Client.

    This client connects to Binance Futures WebSocket API and streams
    real-time market data including mark price and order book depth.

    Example:
        ```python
        async def on_mark_price(data):
            print(f"Mark Price: {data.mark_price}")

        async def on_depth(data):
            print(f"Top Bid: {data.bids[0]}, Top Ask: {data.asks[0]}")

        client = BinanceWebSocketClient()
        client.on_mark_price = on_mark_price
        client.on_depth = on_depth

        await client.connect()
        await client.subscribe_mark_price("BTCUSDT")
        await client.subscribe_depth("BTCUSDT")
        ```
    """

    BASE_URL = "wss://fstream.binance.com/ws"
    COMBINED_URL = "wss://fstream.binance.com/stream"

    def __init__(
        self,
        ping_interval: float = 20,
        ping_timeout: float = 20,
        reconnect_delay: float = 5,
        max_reconnect_attempts: int = 10,
    ):
        """
        Initialize WebSocket client.

        Args:
            ping_interval: Interval between ping messages
            ping_timeout: Timeout for pong response
            reconnect_delay: Delay before reconnect attempt
            max_reconnect_attempts: Maximum reconnect attempts
        """
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts

        self._ws: Optional[WebSocketClientProtocol] = None
        self._stream_manager = BinanceStreamManager()
        self._handlers: Dict[str, Any] = {}
        self._running = False
        self._reconnect_count = 0
        self._receive_task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_mark_price: Optional[Callable[[MarkPriceData], Any]] = None
        self._on_depth: Optional[Callable[[DepthData], Any]] = None
        self._on_connect: Optional[Callable[[], Any]] = None
        self._on_disconnect: Optional[Callable[[], Any]] = None
        self._on_error: Optional[Callable[[Exception], Any]] = None

    @property
    def on_mark_price(self) -> Optional[Callable[[MarkPriceData], Any]]:
        """Get mark price callback."""
        return self._on_mark_price

    @on_mark_price.setter
    def on_mark_price(self, callback: Optional[Callable[[MarkPriceData], Any]]):
        """Set mark price callback."""
        self._on_mark_price = callback
        self._handlers["markPrice"] = MarkPriceHandler(callback)

    @property
    def on_depth(self) -> Optional[Callable[[DepthData], Any]]:
        """Get depth callback."""
        return self._on_depth

    @on_depth.setter
    def on_depth(self, callback: Optional[Callable[[DepthData], Any]]):
        """Set depth callback."""
        self._on_depth = callback
        self._handlers["depth"] = DepthHandler(callback)

    @property
    def on_connect(self) -> Optional[Callable[[], Any]]:
        """Get connect callback."""
        return self._on_connect

    @on_connect.setter
    def on_connect(self, callback: Optional[Callable[[], Any]]):
        """Set connect callback."""
        self._on_connect = callback

    @property
    def on_disconnect(self) -> Optional[Callable[[], Any]]:
        """Get disconnect callback."""
        return self._on_disconnect

    @on_disconnect.setter
    def on_disconnect(self, callback: Optional[Callable[[], Any]]):
        """Set disconnect callback."""
        self._on_disconnect = callback

    @property
    def on_error(self) -> Optional[Callable[[Exception], Any]]:
        """Get error callback."""
        return self._on_error

    @on_error.setter
    def on_error(self, callback: Optional[Callable[[Exception], Any]]):
        """Set error callback."""
        self._on_error = callback

    async def connect(self) -> None:
        """
        Connect to Binance WebSocket.

        Raises:
            ConnectionError: If connection fails after max attempts
        """
        self._running = True
        await self._connect_with_reconnect()

    async def _connect_with_reconnect(self) -> None:
        """Connect with auto-reconnect logic."""
        while self._running and self._reconnect_count < self.max_reconnect_attempts:
            try:
                await self._connect_internal()
                # Reset reconnect count on successful connection
                self._reconnect_count = 0
                # Connection successful, exit the reconnect loop
                return
            except Exception as e:
                logger.error(f"Connection error: {e}")
                
                if self._on_error:
                    result = self._on_error(e)
                    if asyncio.iscoroutine(result):
                        await result
                
                if self._running and self._reconnect_count < self.max_reconnect_attempts:
                    self._reconnect_count += 1
                    logger.info(
                        f"Reconnecting in {self.reconnect_delay}s "
                        f"(attempt {self._reconnect_count}/{self.max_reconnect_attempts})"
                    )
                    await asyncio.sleep(self.reconnect_delay)
                else:
                    raise ConnectionError(f"Failed to connect after {self._reconnect_count} attempts")

    async def _connect_internal(self) -> None:
        """Internal connection logic."""
        url = self._get_connection_url()
        logger.info(f"Connecting to {url}")
        
        self._ws = await websockets.connect(
            url,
            ping_interval=self.ping_interval,
            ping_timeout=self.ping_timeout,
            close_timeout=1,
        )
        
        logger.info("WebSocket connected")
        
        if self._on_connect:
            result = self._on_connect()
            if asyncio.iscoroutine(result):
                await result
        
        # Start receiving messages in background task
        self._receive_task = asyncio.create_task(self._receive_messages())
        
        # Give receive task time to start
        await asyncio.sleep(0)
        
        # Don't wait for receive task - let it run in background

    def _get_connection_url(self) -> str:
        """Get connection URL based on active streams."""
        streams = self._stream_manager.get_stream_names()
        if streams:
            stream_str = "/".join(streams)
            return f"{self.COMBINED_URL}?streams={stream_str}"
        return self.BASE_URL

    async def _receive_messages(self) -> None:
        """Receive and process messages from WebSocket."""
        if not self._ws:
            return
        
        try:
            while self._running and self._ws.state.name == 'OPEN':
                try:
                    message = await asyncio.wait_for(self._ws.recv(), timeout=1.0)
                    await self._handle_message(message)
                except asyncio.TimeoutError:
                    # No message received in 1 second, continue
                    pass
                except Exception as e:
                    logger.error(f"Error receiving message: {e}")
                    raise
        except ConnectionClosed as e:
            logger.warning(f"Connection closed: {e}")
            
            if self._on_disconnect:
                result = self._on_disconnect()
                if asyncio.iscoroutine(result):
                    await result
            
            # Trigger reconnect if still running
            if self._running:
                raise

    async def _handle_message(self, message: str) -> None:
        """
        Handle incoming WebSocket message.

        Args:
            message: Raw JSON message
        """
        data = json.loads(message)
        
        # Handle combined stream format
        if "stream" in data:
            stream = data["stream"]
            data = data["data"]
        
        # Determine message type and route to handler
        event_type = data.get("e", "")
        
        if event_type == "markPriceUpdate":
            await self._handle_mark_price(data)
        elif "b" in data and "a" in data:  # Depth update
            await self._handle_depth(data)

    async def _handle_mark_price(self, data: Dict[str, Any]) -> None:
        """Handle mark price message."""
        handler = self._handlers.get("markPrice")
        if handler:
            await handler.handle(data)

    async def _handle_depth(self, data: Dict[str, Any]) -> None:
        """Handle depth message."""
        handler = self._handlers.get("depth")
        if handler:
            await handler.handle(data)

    async def subscribe_mark_price(
        self,
        symbol: str,
        interval_1s: bool = False,
    ) -> None:
        """
        Subscribe to mark price stream.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            interval_1s: Use 1-second update interval
        """
        stream_type = StreamType.MARK_PRICE_1S if interval_1s else StreamType.MARK_PRICE
        stream_name = self._stream_manager.add_stream(symbol, stream_type)
        logger.info(f"Subscribed to mark price stream: {stream_name}")
        
        # Reconnect if already connected to update subscriptions
        if self._ws and self._ws.state.name == 'OPEN':
            await self._reconnect()

    async def unsubscribe_mark_price(
        self,
        symbol: str,
        interval_1s: bool = False,
    ) -> None:
        """
        Unsubscribe from mark price stream.

        Args:
            symbol: Trading symbol
            interval_1s: Was using 1-second interval
        """
        stream_type = StreamType.MARK_PRICE_1S if interval_1s else StreamType.MARK_PRICE
        stream_name = self._stream_manager.remove_stream(symbol, stream_type)
        logger.info(f"Unsubscribed from mark price stream: {stream_name}")
        
        if self._ws and self._ws.state.name == 'OPEN':
            await self._reconnect()

    async def subscribe_depth(
        self,
        symbol: str,
        interval_100ms: bool = False,
    ) -> None:
        """
        Subscribe to depth stream.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            interval_100ms: Use 100ms update interval
        """
        stream_type = StreamType.DEPTH5_100MS if interval_100ms else StreamType.DEPTH5
        stream_name = self._stream_manager.add_stream(symbol, stream_type)
        logger.info(f"Subscribed to depth stream: {stream_name}")
        
        if self._ws and self._ws.state.name == 'OPEN':
            await self._reconnect()

    async def unsubscribe_depth(
        self,
        symbol: str,
        interval_100ms: bool = False,
    ) -> None:
        """
        Unsubscribe from depth stream.

        Args:
            symbol: Trading symbol
            interval_100ms: Was using 100ms interval
        """
        stream_type = StreamType.DEPTH5_100MS if interval_100ms else StreamType.DEPTH5
        stream_name = self._stream_manager.remove_stream(symbol, stream_type)
        logger.info(f"Unsubscribed from depth stream: {stream_name}")
        
        if self._ws and self._ws.state.name == 'OPEN':
            await self._reconnect()

    async def _reconnect(self) -> None:
        """Reconnect to WebSocket with new subscriptions."""
        # Cancel old receive task if running
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        
        await self._connect_internal()

    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        self._running = False
        
        if self._ws:
            try:
                await self._ws.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
        
        self._stream_manager.clear()
        logger.info("WebSocket disconnected")

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._ws is not None and self._ws.state.name == 'OPEN'


async def test_websocket_10_seconds():
    """
    Test script that outputs 10 seconds of markPrice stream.
    
    This function demonstrates the WebSocket client by streaming
    mark price data for BTCUSDT for 10 seconds.
    """
    import time
    
    print("Starting Binance WebSocket test...")
    print("Streaming markPrice data for 10 seconds...\n")
    
    message_count = 0
    
    async def on_mark_price(data: MarkPriceData):
        nonlocal message_count
        message_count += 1
        print(f"[{message_count}] {data.symbol}: Mark Price = {data.mark_price:.2f}")
        print(f"    Index Price = {data.index_price:.2f}")
        print(f"    Funding Rate = {data.funding_rate:.6f}")
        print(f"    Next Funding Time = {data.next_funding_time}")
        print()
    
    client = BinanceWebSocketClient()
    client.on_mark_price = on_mark_price
    
    try:
        # Start connection in background
        connect_task = asyncio.create_task(client.connect())
        
        # Wait for connection
        await asyncio.sleep(1)
        
        # Subscribe to mark price
        await client.subscribe_mark_price("BTCUSDT", interval_1s=True)
        
        # Stream for 10 seconds
        await asyncio.sleep(10)
        
        print(f"\nTest complete. Received {message_count} messages.")
        
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_websocket_10_seconds())

