"""
Polymarket AI Lead-Lag Scalper - Main FastAPI Application
"""
from fastapi import FastAPI

app = FastAPI(
    title="Polymarket AI Lead-Lag Scalper",
    description="AI-powered trading system for Polymarket lead-lag scalping strategies",
    version="1.0.0",
)


@app.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint.
    Returns 200 OK with status message.
    """
    return {"status": "ok"}
