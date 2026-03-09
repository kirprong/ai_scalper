"""
Socket.io server configuration for real-time communication.

This module sets up the Socket.io server with proper CORS configuration,
connection management, and integration with FastAPI.
"""

import logging
from typing import Optional, Set, Dict, Any
from datetime import datetime

import socketio
from engineio.async_drivers import aiohttp

# Configure logging
logger = logging.getLogger(__name__)

# Track connected clients and their subscriptions
connected_clients: Set[str] = set()
market_subscriptions: Dict[str, Set[str]] = {}  # market_id -> set of session_ids
client_subscriptions: Dict[str, Set[str]] = {}  # session_id -> set of market_ids


def create_socketio_server(
    cors_allowed_origins: Optional[list] = None,
    async_mode: str = "aiohttp",
) -> socketio.AsyncServer:
    """
    Create and configure a Socket.io server instance.
    
    Args:
        cors_allowed_origins: List of allowed origins for CORS.
            Defaults to ["*"] for development.
        async_mode: Async mode to use. Defaults to "aiohttp" for FastAPI.
    
    Returns:
        Configured Socket.io AsyncServer instance.
    """
    if cors_allowed_origins is None:
        cors_allowed_origins = ["*"]
    
    sio = socketio.AsyncServer(
        async_mode=async_mode,
        cors_allowed_origins=cors_allowed_origins,
        logger=False,  # Disable Socket.io internal logging
        engineio_logger=False,  # Disable Engine.IO logging
        ping_timeout=60,  # Close connection after 60s without ping response
        ping_interval=25,  # Send ping every 25 seconds
        max_http_buffer_size=1e7,  # 10MB max message size
        allow_upgrades=True,  # Allow WebSocket upgrade
        transports=["polling", "websocket"],  # Support both transports
    )
    
    logger.info("Socket.io server created with async_mode=%s", async_mode)
    return sio


# Create the default Socket.io server instance
sio = create_socketio_server()


def create_socket_app(
    socketio_server: Optional[socketio.AsyncServer] = None,
) -> socketio.ASGIApp:
    """
    Create a Socket.io ASGI app for mounting in FastAPI.
    
    Args:
        socketio_server: Socket.io server instance. Uses default if not provided.
    
    Returns:
        Socket.io ASGI app instance.
    """
    server = socketio_server or sio
    app = socketio.ASGIApp(server, socketio_path="/socket.io")
    logger.info("Socket.io ASGI app created with path=/socket.io")
    return app


# Create the default Socket.io app
socket_app = create_socket_app()


def get_socketio_server() -> socketio.AsyncServer:
    """
    Get the default Socket.io server instance.
    
    Returns:
        The default Socket.io AsyncServer instance.
    """
    return sio


def get_connected_clients() -> Set[str]:
    """
    Get the set of connected client session IDs.
    
    Returns:
        Set of connected session IDs.
    """
    return connected_clients.copy()


def get_market_subscribers(market_id: str) -> Set[str]:
    """
    Get the set of session IDs subscribed to a specific market.
    
    Args:
        market_id: The market identifier.
    
    Returns:
        Set of session IDs subscribed to the market.
    """
    return market_subscriptions.get(market_id, set()).copy()


def add_subscription(session_id: str, market_id: str) -> None:
    """
    Add a market subscription for a client.
    
    Args:
        session_id: The client session ID.
        market_id: The market identifier to subscribe to.
    """
    if market_id not in market_subscriptions:
        market_subscriptions[market_id] = set()
    market_subscriptions[market_id].add(session_id)
    
    if session_id not in client_subscriptions:
        client_subscriptions[session_id] = set()
    client_subscriptions[session_id].add(market_id)
    
    logger.debug("Client %s subscribed to market %s", session_id, market_id)


def remove_subscription(session_id: str, market_id: str) -> None:
    """
    Remove a market subscription for a client.
    
    Args:
        session_id: The client session ID.
        market_id: The market identifier to unsubscribe from.
    """
    if market_id in market_subscriptions:
        market_subscriptions[market_id].discard(session_id)
        if not market_subscriptions[market_id]:
            del market_subscriptions[market_id]
    
    if session_id in client_subscriptions:
        client_subscriptions[session_id].discard(market_id)
        if not client_subscriptions[session_id]:
            del client_subscriptions[session_id]
    
    logger.debug("Client %s unsubscribed from market %s", session_id, market_id)


def remove_all_subscriptions(session_id: str) -> None:
    """
    Remove all subscriptions for a client.
    
    Args:
        session_id: The client session ID.
    """
    if session_id in client_subscriptions:
        for market_id in list(client_subscriptions[session_id]):
            remove_subscription(session_id, market_id)
    
    logger.debug("Removed all subscriptions for client %s", session_id)


def register_client(session_id: str) -> None:
    """
    Register a new connected client.
    
    Args:
        session_id: The client session ID.
    """
    connected_clients.add(session_id)
    logger.info("Client connected: %s (total: %d)", session_id, len(connected_clients))


def unregister_client(session_id: str) -> None:
    """
    Unregister a disconnected client.
    
    Args:
        session_id: The client session ID.
    """
    connected_clients.discard(session_id)
    remove_all_subscriptions(session_id)
    logger.info("Client disconnected: %s (total: %d)", session_id, len(connected_clients))


def get_subscription_stats() -> Dict[str, Any]:
    """
    Get statistics about current subscriptions.
    
    Returns:
        Dictionary with subscription statistics.
    """
    return {
        "connected_clients": len(connected_clients),
        "total_subscriptions": sum(len(subs) for subs in client_subscriptions.values()),
        "markets_with_subscribers": len(market_subscriptions),
        "market_details": {
            market_id: len(subscribers)
            for market_id, subscribers in market_subscriptions.items()
        },
        "timestamp": datetime.utcnow().isoformat(),
    }
