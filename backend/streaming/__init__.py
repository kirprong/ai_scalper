"""
Binance WebSocket streaming module.

This module provides live WebSocket clients for streaming real-time
market data from Binance Futures.
"""

from .binance_websocket import (
    BinanceWebSocketClient,
    BinanceStreamManager,
    MarkPriceHandler,
    DepthHandler,
)

__all__ = [
    "BinanceWebSocketClient",
    "BinanceStreamManager",
    "MarkPriceHandler",
    "DepthHandler",
]
