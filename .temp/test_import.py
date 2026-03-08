#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from backend.streaming.binance_websocket import BinanceWebSocketClient

print('Import successful!')
print('BinanceWebSocketClient class exists:', hasattr(BinanceWebSocketClient, '__init__'))
print('Methods:', [m for m in dir(BinanceWebSocketClient) if not m.startswith('_')])
