# TASK-035: Socket.io Communication

## Overview
Implementation of Socket.io real-time bidirectional communication between the FastAPI backend and React frontend for the Polymarket AI Lead-Lag Scalper.

## Status
**COMPLETED** - 2026-03-09

## Implementation Summary

### Backend Components

#### 1. Socket.io Server Configuration (`backend/realtime/socketio_server.py`)
- Created `create_socketio_server()` function with configurable CORS and async mode
- Implemented client connection tracking with `connected_clients` set
- Implemented market subscription management with `market_subscriptions` and `client_subscriptions` dictionaries
- Added helper functions:
  - `register_client()` / `unregister_client()` - Client lifecycle management
  - `add_subscription()` / `remove_subscription()` - Market subscription management
  - `get_subscription_stats()` - Server statistics

#### 2. Event Handlers (`backend/realtime/event_handlers.py`)
- **Connection Events:**
  - `connect` - Client connection with confirmation
  - `disconnect` - Client disconnection with cleanup

- **Market Events:**
  - `subscribe_market` - Subscribe to market updates
  - `unsubscribe_market` - Unsubscribe from market updates

- **Utility Events:**
  - `get_stats` - Get server statistics
  - `ping_server` - Latency measurement
  - `request_market_data` - Request current market data

- **Error Handling:**
  - `error` - Client error handling
  - `catch_all` - Unrecognized event handler

#### 3. Data Emitters (`backend/realtime/emitters.py`)
- `emit_price_update()` - Real-time price data
- `emit_signal_detected()` - Trading signal alerts
- `emit_position_update()` - Position changes
- `emit_metrics_update()` - System metrics
- `emit_panic_alert()` - Panic/kill switch alerts
- `emit_order_update()` - Order status updates
- `emit_system_status()` - System status broadcasts
- `emit_model_update()` - Model hot-reload notifications
- `emit_error()` - Error notifications
- `broadcast_to_all()` - Generic broadcast function

#### 4. FastAPI Integration (`backend/main.py`)
- Integrated Socket.io with FastAPI using lifespan context manager
- Registered event handlers on startup
- Added background task for periodic status broadcasting
- Implemented panic halt/reset event handlers
- Added REST endpoints:
  - `GET /health` - Health check
  - `GET /api/status` - System status
  - `GET /api/stats` - Socket.io statistics

### Frontend Components

#### Socket.io Context (`frontend/src/context/SocketContext.jsx`)
- **Connection Management:**
  - Automatic connection with reconnection logic
  - Connection state tracking (connected, connecting, error)
  - Reconnection attempt tracking

- **State Management:**
  - System status and server stats
  - Price updates by market
  - Trading signals, positions, orders
  - Metrics and panic alerts

- **Custom Hooks:**
  - `useSocket()` - Main socket context access
  - `useMarketSubscription(marketId)` - Auto-subscribe to market
  - `useSignals()` - Trading signals access
  - `usePositions()` - Positions access
  - `useMetrics()` - Metrics access
  - `usePanicState()` - Panic state management

- **Actions:**
  - `subscribeToMarket()` / `unsubscribeFromMarket()`
  - `requestMarketData()`
  - `getServerStats()` / `pingServer()`
  - `emitPanic()` / `emitReset()`
  - `on()` / `off()` / `emit()` - Low-level API

### Dependencies

#### Backend (`requirements.txt`)
```
python-socketio>=5.10.0
python-engineio>=4.8.0
```

#### Frontend (`package.json`)
```
socket.io-client: ^4.7.2 (already present)
```

## Events Reference

| Event | Direction | Description |
|-------|-----------|-------------|
| `connect` | Client→Server | Client connection |
| `disconnect` | Client→Server | Client disconnection |
| `subscribe_market` | Client→Server | Subscribe to market updates |
| `unsubscribe_market` | Client→Server | Unsubscribe from market |
| `price_update` | Server→Client | Real-time price data |
| `signal_detected` | Server→Client | New trading signal |
| `position_update` | Server→Client | Position change |
| `metrics_update` | Server→Client | System metrics |
| `panic_alert` | Server→Client | Panic/kill switch triggered |
| `order_update` | Server→Client | Order status change |
| `system_status` | Server→Client | System status broadcast |
| `model_update` | Server→Client | Model hot-reload notification |

## File Structure

```
backend/
├── realtime/
│   ├── __init__.py           # Module exports
│   ├── socketio_server.py    # Server configuration
│   ├── event_handlers.py     # Event handlers
│   └── emitters.py           # Data emitters
└── main.py                   # FastAPI integration

frontend/
└── src/
    └── context/
        └── SocketContext.jsx # React context and hooks

tests/
└── test_socketio.py          # Unit and integration tests
```

## Testing

### Unit Tests
- Server configuration tests
- Client registration/deregistration
- Subscription management
- Emitter functions

### Integration Tests
- Full event flow from subscription to emission
- Multiple clients on same market
- Single client on multiple markets

### Running Tests
```bash
pytest tests/test_socketio.py -v
```

## Usage Examples

### Backend - Emit Price Update
```python
from backend.realtime import emit_price_update

await emit_price_update(
    market_id="market_123",
    price_data={
        "price": 0.55,
        "bid": 0.54,
        "ask": 0.56,
        "volume": 10000
    }
)
```

### Backend - Emit Trading Signal
```python
from backend.realtime import emit_signal_detected

await emit_signal_detected({
    "signal_type": "golden_rectangle",
    "direction": "buy",
    "confidence": 0.85,
    "entry_price": 0.55,
    "market_id": "market_123"
})
```

### Frontend - Use Socket Context
```jsx
import { useSocket, useMarketSubscription } from './context/SocketContext'

function TradingComponent({ marketId }) {
  const { connected, systemStatus, emitPanic } = useSocket()
  const priceData = useMarketSubscription(marketId)
  
  if (!connected) return <div>Connecting...</div>
  
  return (
    <div>
      <p>System: {systemStatus}</p>
      <p>Price: {priceData?.price}</p>
      <button onClick={emitPanic}>Panic</button>
    </div>
  )
}
```

## Configuration

### Environment Variables
- `VITE_BACKEND_URL` - Backend URL for frontend (default: http://localhost:8000)

### Socket.io Options
- Transports: websocket, polling
- Reconnection: enabled with infinite attempts
- Reconnection delay: 1-5 seconds with randomization
- Ping timeout: 60 seconds
- Ping interval: 25 seconds

## Security Considerations
- CORS configured for specific origins
- No authentication implemented (to be added)
- All events logged for debugging

## Future Improvements
- Add authentication/authorization
- Implement rate limiting
- Add message compression for large payloads
- Implement room-based broadcasting for scalability
- Add metrics collection for monitoring
