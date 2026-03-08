"""
Time synchronization module for market data alignment.

This module provides ASOF JOIN-based time alignment between
Polymarket and Binance data streams.
"""

from .time_aligner import TimeAligner, TimeDeltaStats

__all__ = ["TimeAligner", "TimeDeltaStats"]
