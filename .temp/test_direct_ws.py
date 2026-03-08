#!/usr/bin/env python3
"""Direct WebSocket test - connect to stream URL immediately."""

import asyncio
import sys
sys.path.insert(0, '.')

try:
    import ujson as json
except ImportError:
    import json

import websockets


async def main():
    """Test direct connection to Binance stream."""
    # Direct URL for BTCUSDT markPrice@1s stream
    url = "wss://fstream.binance.com/stream?streams=btcusdt@markPrice@1s"
    
    print("=" * 60)
    print("Direct WebSocket Test")
    print("=" * 60)
    print(f"Connecting to: {url}")
    print("=" * 60)
    print()
    
    message_count = 0
    
    try:
        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
            print("Connected! Waiting for messages...")
            print()
            
            # Receive messages for 10 seconds
            for i in range(10):
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    data = json.loads(message)
                    message_count += 1
                    
                    # Parse the data
                    if "stream" in data:
                        stream = data["stream"]
                        msg_data = data["data"]
                        event_type = msg_data.get("e", "")
                        
                        if event_type == "markPriceUpdate":
                            symbol = msg_data.get("s", "")
                            mark_price = float(msg_data.get("p", 0))
                            index_price = float(msg_data.get("i", 0))
                            funding_rate = float(msg_data.get("r", 0))
                            
                            print(f"[{message_count:3d}] {symbol}:")
                            print(f"      Mark Price  = ${mark_price:,.2f}")
                            print(f"      Index Price = ${index_price:,.2f}")
                            print(f"      Funding Rate = {funding_rate:.6f}")
                            print()
                except asyncio.TimeoutError:
                    # No message received in 1 second, continue
                    pass
                    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 60)
    print(f"Test complete. Received {message_count} messages.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
