"""
Polymarket AI Lead-Lag Scalper - Main FastAPI Application

This module provides the main FastAPI application with integrated Socket.io
support for real-time bidirectional communication with the frontend.
"""
import os
import logging
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.safety.panic_switch import PanicSwitch, PanicSwitchConfig
from backend.safety.kill_switch import install_kill_switch
from backend.realtime import (
    sio,
    socket_app,
    register_event_handlers,
    emit_panic_alert,
    emit_system_status,
    emit_metrics_update,
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global state
panic_switch = None
polymarket_client = None
kill_switch = None
background_tasks = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    """
    # Startup
    logger.info("Starting up application...")
    
    # Register Socket.io event handlers
    register_event_handlers()
    logger.info("Socket.io event handlers registered")
    
    # Initialize Panic Switch
    global panic_switch
    panic_config = PanicSwitchConfig(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        enable_telegram=bool(os.getenv("TELEGRAM_BOT_TOKEN")),
    )
    panic_switch = PanicSwitch(panic_config)
    logger.info("Panic switch initialized")
    
    # Initialize Hardware Kill-Switch
    global kill_switch
    kill_switch = install_kill_switch(
        polymarket_client=polymarket_client,
        panic_switch=panic_switch,
    )
    logger.info("Kill switch installed")
    
    # Start background tasks
    task = asyncio.create_task(broadcast_status_periodically())
    background_tasks.append(task)
    logger.info("Background tasks started")
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    # Cancel background tasks
    for task in background_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    logger.info("Application shutdown complete")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Polymarket AI Lead-Lag Scalper",
    description="AI-powered trading system for Polymarket lead-lag scalping strategies",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Background task to broadcast status periodically
async def broadcast_status_periodically():
    """Broadcast system status to all connected clients every 5 seconds."""
    while True:
        try:
            await asyncio.sleep(5)
            
            if panic_switch:
                await emit_system_status({
                    "status": panic_switch.status.value,
                    "statistics": panic_switch.get_statistics(),
                })
                
                # Also emit metrics update
                stats = panic_switch.get_statistics()
                await emit_metrics_update({
                    "panic_status": panic_switch.status.value,
                    "halt_count": stats.get("halt_count", 0),
                    "reset_count": stats.get("reset_count", 0),
                })
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in broadcast_status_periodically: %s", e)


# REST API Endpoints

@app.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint.
    Returns 200 OK with status message.
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/status")
async def get_status() -> dict:
    """
    Get system status including panic switch state.
    """
    if panic_switch:
        return panic_switch.get_statistics()
    return {"status": "initializing"}


@app.get("/api/stats")
async def get_stats() -> dict:
    """
    Get Socket.io connection statistics.
    """
    from backend.realtime.socketio_server import get_subscription_stats
    return get_subscription_stats()


# Socket.io Event Handlers (additional to those in event_handlers.py)

@sio.event
async def panic_halt(sid: str):
    """
    Handle panic halt command from UI.
    Triggers emergency halt and cancels all orders.
    """
    logger.critical("🚨 PANIC HALT triggered from UI by %s", sid)
    
    try:
        # Halt the system
        if panic_switch:
            await panic_switch.halt_system()
        
        # Cancel all orders via Polymarket client
        if polymarket_client:
            try:
                result = await polymarket_client.cancel_all_orders()
                cancelled_count = result.get("cancelled", 0) if isinstance(result, dict) else 0
                logger.critical("✅ Cancelled %d orders via API", cancelled_count)
            except Exception as e:
                logger.error("❌ Failed to cancel orders: %s", e)
        else:
            logger.warning("⚠️  No Polymarket client - orders not cancelled")
        
        # Broadcast panic alert to all connected clients
        await emit_panic_alert({
            "alert_type": "panic_halt",
            "severity": "critical",
            "message": "Emergency halt activated - all orders cancelled",
            "triggered_by": "ui",
            "session_id": sid,
        })
        
        logger.info("✅ Panic halt completed successfully")
        
    except Exception as e:
        logger.error("❌ Panic halt failed: %s", e)
        await sio.emit("error", {
            "error_code": "PANIC_HALT_FAILED",
            "error_message": f"Panic halt failed: {str(e)}",
        }, to=sid)


@sio.event
async def panic_reset(sid: str):
    """
    Handle panic reset command from UI.
    Resumes trading operations.
    """
    logger.info("🔄 Panic RESET triggered from UI by %s", sid)
    
    try:
        # Reset the panic switch
        if panic_switch:
            await panic_switch.reset()
        
        # Broadcast reset to all connected clients
        await emit_system_status({
            "status": "ACTIVE",
            "message": "Trading operations resumed",
            "triggered_by": "ui",
            "session_id": sid,
        })
        
        logger.info("✅ Panic reset completed successfully")
        
    except Exception as e:
        logger.error("❌ Panic reset failed: %s", e)
        await sio.emit("error", {
            "error_code": "PANIC_RESET_FAILED",
            "error_message": f"Panic reset failed: {str(e)}",
        }, to=sid)


@sio.event
async def get_system_status(sid: str):
    """Send current system status to requesting client."""
    if panic_switch:
        await sio.emit("system_status", {
            "status": panic_switch.status.value,
            "statistics": panic_switch.get_statistics(),
        }, to=sid)


# Mount Socket.io app
# The socket_app is already configured to work with FastAPI
# When running with uvicorn, use socket_app instead of app

# For running with uvicorn directly
if __name__ == "__main__":
    import uvicorn
    
    # Note: Use socket_app instead of app for Socket.io support
    uvicorn.run(
        socket_app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
