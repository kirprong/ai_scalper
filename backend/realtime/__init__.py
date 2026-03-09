"""
Real-time communication module for Socket.io integration.

This module provides bidirectional real-time communication between
the backend and frontend using Socket.io.
"""

from .socketio_server import sio, socket_app, get_socketio_server
from .event_handlers import register_event_handlers
from .emitters import (
    emit_price_update,
    emit_signal_detected,
    emit_position_update,
    emit_metrics_update,
    emit_panic_alert,
    broadcast_to_all,
    emit_order_update,
    emit_system_status,
    emit_model_update,
    emit_error,
)

__all__ = [
    # Socket.io server
    "sio",
    "socket_app",
    "get_socketio_server",
    # Event handlers
    "register_event_handlers",
    # Emitters
    "emit_price_update",
    "emit_signal_detected",
    "emit_position_update",
    "emit_metrics_update",
    "emit_panic_alert",
    "broadcast_to_all",
    "emit_order_update",
    "emit_system_status",
    "emit_model_update",
    "emit_error",
]
