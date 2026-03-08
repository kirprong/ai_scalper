"""
Polymarket AI Lead-Lag Scalper - Main FastAPI Application
"""
import os
import logging
import asyncio
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
from dotenv import load_dotenv

from backend.safety.panic_switch import PanicSwitch, PanicSwitchConfig
from backend.safety.kill_switch import install_kill_switch

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Polymarket AI Lead-Lag Scalper",
    description="AI-powered trading system for Polymarket lead-lag scalping strategies",
    version="1.0.0",
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Socket.io server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=['http://localhost:3000', 'http://localhost:5173']
)
socket_app = socketio.ASGIApp(sio, app)

# Initialize Panic Switch
panic_config = PanicSwitchConfig(
    telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
    telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    enable_telegram=bool(os.getenv("TELEGRAM_BOT_TOKEN"))
)
panic_switch = PanicSwitch(panic_config)

# Initialize Polymarket client (will be set when available)
polymarket_client = None

# Initialize Hardware Kill-Switch
kill_switch = install_kill_switch(
    polymarket_client=polymarket_client,
    panic_switch=panic_switch
)


@app.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint.
    Returns 200 OK with status message.
    """
    return {"status": "ok"}


@app.get("/api/status")
async def get_status() -> dict:
    """
    Get system status including panic switch state.
    """
    return panic_switch.get_statistics()


# Socket.io Event Handlers

@sio.event
async def connect(sid, environ):
    """Handle client connection"""
    logger.info(f"Client connected: {sid}")
    # Send current system status
    await sio.emit('system_status', {
        'status': panic_switch.status.value,
        'statistics': panic_switch.get_statistics()
    }, room=sid)


@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {sid}")


@sio.event
async def panic_halt(sid):
    """
    Handle panic halt command from UI.
    Triggers emergency halt and cancels all orders.
    """
    logger.critical(f"🚨 PANIC HALT triggered from UI by {sid}")
    
    try:
        # Halt the system
        await panic_switch.halt_system()
        
        # Cancel all orders via Polymarket client
        if polymarket_client:
            try:
                result = await polymarket_client.cancel_all_orders()
                cancelled_count = result.get("cancelled", 0) if isinstance(result, dict) else 0
                logger.critical(f"✅ Cancelled {cancelled_count} orders via API")
            except Exception as e:
                logger.error(f"❌ Failed to cancel orders: {e}")
        else:
            logger.warning("⚠️  No Polymarket client - orders not cancelled")
        
        # Broadcast halt to all connected clients
        await sio.emit('panic_triggered', {
            'status': 'HALTED',
            'message': 'Emergency halt activated - all orders cancelled',
            'timestamp': str(datetime.now())
        })
        
        logger.info("✅ Panic halt completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Panic halt failed: {e}")
        await sio.emit('error', {
            'message': f'Panic halt failed: {str(e)}'
        }, room=sid)


@sio.event
async def panic_reset(sid):
    """
    Handle panic reset command from UI.
    Resumes trading operations.
    """
    logger.info(f"🔄 Panic RESET triggered from UI by {sid}")
    
    try:
        # Reset the panic switch
        await panic_switch.reset()
        
        # Broadcast reset to all connected clients
        await sio.emit('panic_reset', {
            'status': 'ACTIVE',
            'message': 'Trading operations resumed',
            'timestamp': str(asyncio.datetime.now())
        })
        
        logger.info("✅ Panic reset completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Panic reset failed: {e}")
        await sio.emit('error', {
            'message': f'Panic reset failed: {str(e)}'
        }, room=sid)


@sio.event
async def get_system_status(sid):
    """Send current system status to requesting client"""
    await sio.emit('system_status', {
        'status': panic_switch.status.value,
        'statistics': panic_switch.get_statistics()
    }, room=sid)


# Background task to broadcast status periodically
async def broadcast_status():
    """Broadcast system status to all connected clients every 5 seconds"""
    while True:
        await sio.sleep(5)
        await sio.emit('system_status', {
            'status': panic_switch.status.value,
            'statistics': panic_switch.get_statistics()
        })


# Start background task on startup
@sio.event
async def startup():
    """Initialize background tasks"""
    sio.start_background_task(broadcast_status)


# For running with uvicorn
if __name__ == "__main__":
    import uvicorn
    import asyncio
    
    # Note: Use socket_app instead of app for Socket.io support
    uvicorn.run(socket_app, host="0.0.0.0", port=8000)
