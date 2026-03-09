"""
Socket.io data emitters for real-time communication.

This module provides functions to emit various events from the server
to connected clients for real-time data streaming.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from .socketio_server import sio, get_market_subscribers, get_connected_clients

# Configure logging
logger = logging.getLogger(__name__)


async def emit_price_update(
    market_id: str,
    price_data: Dict[str, Any],
    broadcast: bool = True,
) -> int:
    """
    Emit a price update event to subscribers of a market.
    
    Args:
        market_id: The market identifier.
        price_data: Dictionary containing price information:
            - price: Current price (float)
            - bid: Current bid price (float, optional)
            - ask: Current ask price (float, optional)
            - volume: Current volume (float, optional)
            - change_24h: 24-hour price change (float, optional)
            - high_24h: 24-hour high (float, optional)
            - low_24h: 24-hour low (float, optional)
        broadcast: If True, broadcast to all subscribers. If False, only emit to specific session.
    
    Returns:
        Number of clients the event was sent to.
    """
    event_data = {
        "market_id": market_id,
        "timestamp": datetime.utcnow().isoformat(),
        **price_data,
    }
    
    if broadcast:
        subscribers = get_market_subscribers(market_id)
        if not subscribers:
            logger.debug("No subscribers for market %s", market_id)
            return 0
        
        for session_id in subscribers:
            await sio.emit("price_update", event_data, to=session_id)
        
        logger.debug(
            "Price update sent to %d subscribers for market %s",
            len(subscribers),
            market_id,
        )
        return len(subscribers)
    else:
        await sio.emit("price_update", event_data)
        return 1


async def emit_signal_detected(
    signal_data: Dict[str, Any],
    market_id: Optional[str] = None,
) -> int:
    """
    Emit a trading signal detection event.
    
    Args:
        signal_data: Dictionary containing signal information:
            - signal_type: Type of signal (e.g., "golden_rectangle", "lead_lag")
            - direction: "buy" or "sell"
            - confidence: Signal confidence (0.0 to 1.0)
            - entry_price: Suggested entry price
            - target_price: Target price (optional)
            - stop_loss: Stop loss price (optional)
            - metadata: Additional signal metadata (optional)
        market_id: Optional market ID to send only to subscribers.
    
    Returns:
        Number of clients the event was sent to.
    """
    event_data = {
        "timestamp": datetime.utcnow().isoformat(),
        **signal_data,
    }
    
    if market_id:
        subscribers = get_market_subscribers(market_id)
        if not subscribers:
            logger.debug("No subscribers for market %s", market_id)
            return 0
        
        for session_id in subscribers:
            await sio.emit("signal_detected", event_data, to=session_id)
        
        logger.info(
            "Signal %s sent to %d subscribers for market %s",
            signal_data.get("signal_type", "unknown"),
            len(subscribers),
            market_id,
        )
        return len(subscribers)
    else:
        # Broadcast to all connected clients
        await sio.emit("signal_detected", event_data)
        client_count = len(get_connected_clients())
        logger.info(
            "Signal %s broadcast to %d clients",
            signal_data.get("signal_type", "unknown"),
            client_count,
        )
        return client_count


async def emit_position_update(
    position_data: Dict[str, Any],
    session_id: Optional[str] = None,
) -> int:
    """
    Emit a position update event.
    
    Args:
        position_data: Dictionary containing position information:
            - position_id: Unique position identifier
            - market_id: Market identifier
            - side: "long" or "short"
            - size: Position size
            - entry_price: Entry price
            - current_price: Current market price
            - unrealized_pnl: Unrealized profit/loss
            - realized_pnl: Realized profit/loss (if closed)
            - status: "open", "closed", "liquidated"
            - timestamp: Position timestamp
        session_id: Optional specific session to send to.
            If None, broadcasts to all clients.
    
    Returns:
        Number of clients the event was sent to.
    """
    event_data = {
        "timestamp": datetime.utcnow().isoformat(),
        **position_data,
    }
    
    if session_id:
        await sio.emit("position_update", event_data, to=session_id)
        logger.debug("Position update sent to client %s", session_id)
        return 1
    else:
        await sio.emit("position_update", event_data)
        client_count = len(get_connected_clients())
        logger.debug("Position update broadcast to %d clients", client_count)
        return client_count


async def emit_metrics_update(
    metrics_data: Dict[str, Any],
    session_id: Optional[str] = None,
) -> int:
    """
    Emit a system metrics update event.
    
    Args:
        metrics_data: Dictionary containing metrics:
            - total_pnl: Total profit/loss
            - win_rate: Win rate percentage
            - sharpe_ratio: Sharpe ratio
            - max_drawdown: Maximum drawdown
            - open_positions: Number of open positions
            - daily_trades: Number of trades today
            - latency_ms: System latency in milliseconds
            - uptime_seconds: System uptime in seconds
            - model_accuracy: Current model accuracy (optional)
        session_id: Optional specific session to send to.
            If None, broadcasts to all clients.
    
    Returns:
        Number of clients the event was sent to.
    """
    event_data = {
        "timestamp": datetime.utcnow().isoformat(),
        **metrics_data,
    }
    
    if session_id:
        await sio.emit("metrics_update", event_data, to=session_id)
        logger.debug("Metrics update sent to client %s", session_id)
        return 1
    else:
        await sio.emit("metrics_update", event_data)
        client_count = len(get_connected_clients())
        logger.debug("Metrics update broadcast to %d clients", client_count)
        return client_count


async def emit_panic_alert(
    alert_data: Dict[str, Any],
) -> int:
    """
    Emit a panic/kill switch alert event.
    
    This is a high-priority event that should be broadcast to all
    connected clients immediately.
    
    Args:
        alert_data: Dictionary containing alert information:
            - alert_type: Type of alert (e.g., "kill_switch", "panic", "circuit_breaker")
            - severity: Severity level ("critical", "warning", "info")
            - message: Human-readable alert message
            - triggered_by: What triggered the alert
            - action_taken: What action was taken (optional)
            - timestamp: When the alert was triggered
    
    Returns:
        Number of clients the event was sent to.
    """
    event_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "priority": "high",
        **alert_data,
    }
    
    # Always broadcast panic alerts to all clients
    await sio.emit("panic_alert", event_data)
    client_count = len(get_connected_clients())
    
    logger.warning(
        "Panic alert '%s' broadcast to %d clients: %s",
        alert_data.get("alert_type", "unknown"),
        client_count,
        alert_data.get("message", "No message"),
    )
    
    return client_count


async def broadcast_to_all(
    event: str,
    data: Dict[str, Any],
) -> int:
    """
    Broadcast an event to all connected clients.
    
    Args:
        event: The event name to emit.
        data: The data to send.
    
    Returns:
        Number of clients the event was sent to.
    """
    await sio.emit(event, data)
    client_count = len(get_connected_clients())
    logger.debug("Event '%s' broadcast to %d clients", event, client_count)
    return client_count


async def emit_order_update(
    order_data: Dict[str, Any],
    session_id: Optional[str] = None,
) -> int:
    """
    Emit an order status update event.
    
    Args:
        order_data: Dictionary containing order information:
            - order_id: Unique order identifier
            - market_id: Market identifier
            - side: "buy" or "sell"
            - order_type: "market", "limit", "stop", etc.
            - size: Order size
            - price: Order price (for limit orders)
            - status: "pending", "filled", "partial", "cancelled", "rejected"
            - filled_size: Amount filled (for partial fills)
            - average_fill_price: Average fill price
            - fees: Trading fees
            - timestamp: Order timestamp
        session_id: Optional specific session to send to.
    
    Returns:
        Number of clients the event was sent to.
    """
    event_data = {
        "timestamp": datetime.utcnow().isoformat(),
        **order_data,
    }
    
    if session_id:
        await sio.emit("order_update", event_data, to=session_id)
        logger.debug("Order update sent to client %s", session_id)
        return 1
    else:
        await sio.emit("order_update", event_data)
        client_count = len(get_connected_clients())
        logger.debug("Order update broadcast to %d clients", client_count)
        return client_count


async def emit_system_status(
    status_data: Dict[str, Any],
) -> int:
    """
    Emit a system status update event.
    
    Args:
        status_data: Dictionary containing system status:
            - status: "online", "degraded", "offline", "maintenance"
            - message: Status message
            - components: Dictionary of component statuses
            - version: System version
            - last_update: Last update timestamp
    
    Returns:
        Number of clients the event was sent to.
    """
    event_data = {
        "timestamp": datetime.utcnow().isoformat(),
        **status_data,
    }
    
    await sio.emit("system_status", event_data)
    client_count = len(get_connected_clients())
    logger.info("System status '%s' broadcast to %d clients", status_data.get("status"), client_count)
    return client_count


async def emit_model_update(
    model_data: Dict[str, Any],
) -> int:
    """
    Emit a model update event (for hot-reload notifications).
    
    Args:
        model_data: Dictionary containing model information:
            - model_type: Type of model (e.g., "xgboost", "lstm")
            - version: Model version
            - accuracy: Model accuracy metrics
            - trained_at: When the model was trained
            - features: List of features used
    
    Returns:
        Number of clients the event was sent to.
    """
    event_data = {
        "timestamp": datetime.utcnow().isoformat(),
        **model_data,
    }
    
    await sio.emit("model_update", event_data)
    client_count = len(get_connected_clients())
    logger.info("Model update broadcast to %d clients", client_count)
    return client_count


async def emit_error(
    error_data: Dict[str, Any],
    session_id: Optional[str] = None,
) -> int:
    """
    Emit an error event to a client or all clients.
    
    Args:
        error_data: Dictionary containing error information:
            - error_code: Error code
            - error_message: Human-readable error message
            - details: Additional error details
            - recoverable: Whether the error is recoverable
        session_id: Optional specific session to send to.
    
    Returns:
        Number of clients the event was sent to.
    """
    event_data = {
        "timestamp": datetime.utcnow().isoformat(),
        **error_data,
    }
    
    if session_id:
        await sio.emit("error", event_data, to=session_id)
        logger.debug("Error sent to client %s: %s", session_id, error_data.get("error_message"))
        return 1
    else:
        await sio.emit("error", event_data)
        client_count = len(get_connected_clients())
        logger.debug("Error broadcast to %d clients: %s", client_count, error_data.get("error_message"))
        return client_count
