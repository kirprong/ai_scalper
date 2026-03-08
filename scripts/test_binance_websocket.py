#!/usr/bin/env python3
"""
Test script for Binance WebSocket client.
Outputs 10 seconds of markPrice stream to console.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.streaming.binance_websocket import (
    BinanceWebSocketClient,
    MarkPriceData,
)


async def main():
    """Run WebSocket test for 10 seconds."""
    print("=" * 60)
    print("Binance Futures WebSocket Test")
    print("=" * 60)
    print("Streaming markPrice data for BTCUSDT for 10 seconds...")
    print("=" * 60)
    print()
    
    message_count = 0
    
    async def on_mark_price(data: MarkPriceData):
        nonlocal message_count
        message_count += 1
        print(f"[{message_count:3d}] {data.symbol}:")
        print(f"      Mark Price  = ${data.mark_price:,.2f}")
        print(f"      Index Price = ${data.index_price:,.2f}")
        print(f"      Funding Rate = {data.funding_rate:.6f}")
        print()
    
    client = BinanceWebSocketClient()
    client.on_mark_price = on_mark_price
    
    try:
        # Subscribe BEFORE connecting (this adds stream to manager)
        await client.subscribe_mark_price("BTCUSDT", interval_1s=True)
        
        # Start connection in background
        connect_task = asyncio.create_task(client.connect())
        
        # Wait a bit for connection to establish
        await asyncio.sleep(2)
        
        # Stream for 10 seconds
        await asyncio.sleep(10)
        
        print("=" * 60)
        print(f"Test complete. Received {message_count} messages.")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
