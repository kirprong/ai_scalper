"""
Socket.io event handlers for real-time communication.

This module defines all event handlers for bidirectional communication
between the backend server and frontend clients.
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime

from .socketio_server import (
    sio,
    register_client,
    unregister_client,
    add_subscription,
    remove_subscription,
    get_subscription_stats,
    get_market_subscribers,
)

# Configure logging
logger = logging.getLogger(__name__)


def register_event_handlers() -> None:
    """
    Register all Socket.io event handlers.
    
    This function should be called during application startup to
    attach all event handlers to the Socket.io server.
    """
    logger.info("Registering Socket.io event handlers...")
    
    # Connection events
    @sio.event
    async def connect(sid: str, environ: dict, auth: Optional[dict] = None) -> bool:
        """
        Handle client connection.
        
        Args:
            sid: Session ID of the connecting client.
            environ: WSGI/ASGI environment dictionary.
            auth: Optional authentication data from client.
        
        Returns:
            True to accept connection, False to reject.
        """
        logger.info("Client attempting connection: sid=%s", sid)
        
        # Register the client
        register_client(sid)
        
        # Send connection confirmation
        await sio.emit(
            "connection_established",
            {
                "session_id": sid,
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Successfully connected to trading server",
            },
            to=sid,
        )
        
        # Send current subscription stats
        stats = get_subscription_stats()
        await sio.emit("server_stats", stats, to=sid)
        
        logger.info("Client connected successfully: sid=%s", sid)
        return True
    
    @sio.event
    async def disconnect(sid: str) -> None:
        """
        Handle client disconnection.
        
        Args:
            sid: Session ID of the disconnecting client.
        """
        logger.info("Client disconnecting: sid=%s", sid)
        
        # Unregister the client and clean up subscriptions
        unregister_client(sid)
        
        logger.info("Client disconnected: sid=%s", sid)
    
    # Market subscription events
    @sio.event
    async def subscribe_market(sid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle market subscription request.
        
        Args:
            sid: Session ID of the client.
            data: Dictionary containing 'market_id' and optional 'options'.
        
        Returns:
            Confirmation dictionary with subscription status.
        """
        market_id = data.get("market_id")
        
        if not market_id:
            logger.warning("Subscribe request missing market_id: sid=%s", sid)
            return {
                "success": False,
                "error": "market_id is required",
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        # Add subscription
        add_subscription(sid, market_id)
        
        logger.info("Client %s subscribed to market %s", sid, market_id)
        
        return {
            "success": True,
            "market_id": market_id,
            "message": f"Subscribed to market {market_id}",
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    @sio.event
    async def unsubscribe_market(sid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle market unsubscription request.
        
        Args:
            sid: Session ID of the client.
            data: Dictionary containing 'market_id'.
        
        Returns:
            Confirmation dictionary with unsubscription status.
        """
        market_id = data.get("market_id")
        
        if not market_id:
            logger.warning("Unsubscribe request missing market_id: sid=%s", sid)
            return {
                "success": False,
                "error": "market_id is required",
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        # Remove subscription
        remove_subscription(sid, market_id)
        
        logger.info("Client %s unsubscribed from market %s", sid, market_id)
        
        return {
            "success": True,
            "market_id": market_id,
            "message": f"Unsubscribed from market {market_id}",
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    # Client request events
    @sio.event
    async def get_stats(sid: str) -> Dict[str, Any]:
        """
        Handle request for server statistics.
        
        Args:
            sid: Session ID of the client.
        
        Returns:
            Dictionary with current server statistics.
        """
        stats = get_subscription_stats()
        stats["requesting_session"] = sid
        return stats
    
    @sio.event
    async def ping_server(sid: str) -> Dict[str, Any]:
        """
        Handle ping request for latency measurement.
        
        Args:
            sid: Session ID of the client.
        
        Returns:
            Pong response with timestamp.
        """
        return {
            "pong": True,
            "server_time": datetime.utcnow().isoformat(),
            "session_id": sid,
        }
    
    @sio.event
    async def request_market_data(sid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle request for current market data.
        
        Args:
            sid: Session ID of the client.
            data: Dictionary containing 'market_id'.
        
        Returns:
            Current market data if available.
        """
        market_id = data.get("market_id")
        
        if not market_id:
            return {
                "success": False,
                "error": "market_id is required",
            }
        
        # This would typically fetch from a data store
        # For now, return a placeholder response
        return {
            "success": True,
            "market_id": market_id,
            "message": "Market data request acknowledged",
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    # Error handling
    @sio.event
    async def error(sid: str, error_message: str) -> None:
        """
        Handle error events from clients.
        
        Args:
            sid: Session ID of the client.
            error_message: Error message from the client.
        """
        logger.error("Client error from %s: %s", sid, error_message)
    
    # Catch-all for unhandled events
    @sio.event
    async def catch_all(sid: str, data: Any) -> Dict[str, Any]:
        """
        Catch-all handler for unrecognized events.
        
        Args:
            sid: Session ID of the client.
            data: Any data sent with the event.
        
        Returns:
            Error response indicating unrecognized event.
        """
        logger.warning("Unhandled event from %s: %s", sid, str(data)[:100])
        return {
            "success": False,
            "error": "Unrecognized event type",
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    logger.info("Socket.io event handlers registered successfully")


# Additional helper functions for external use
async def emit_to_market_subscribers(market_id: str, event: str, data: Dict[str, Any]) -> int:
    """
    Emit an event to all subscribers of a specific market.
    
    Args:
        market_id: The market identifier.
        event: The event name to emit.
        data: The data to send.
    
    Returns:
        Number of clients the event was sent to.
    """
    subscribers = get_market_subscribers(market_id)
    
    if not subscribers:
        return 0
    
    for session_id in subscribers:
        await sio.emit(event, data, to=session_id)
    
    return len(subscribers)


async def emit_to_client(session_id: str, event: str, data: Dict[str, Any]) -> bool:
    """
    Emit an event to a specific client.
    
    Args:
        session_id: The client session ID.
        event: The event name to emit.
        data: The data to send.
    
    Returns:
        True if emission was successful, False otherwise.
    """
    try:
        await sio.emit(event, data, to=session_id)
        return True
    except Exception as e:
        logger.error("Failed to emit to client %s: %s", session_id, e)
        return False
