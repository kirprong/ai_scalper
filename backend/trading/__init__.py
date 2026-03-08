"""
Trading Module.

This module provides trading functionality including paper trading simulation,
order execution, and position management.

Components:
- PaperTradingSimulator: Simulates trading with slippage and latency
- SlippageEngine: Calculates realistic slippage
- FeeCalculator: Calculates trading fees
"""

from .paper_trading import PaperTradingSimulator, PaperTradingConfig
from .slippage import SlippageEngine, SlippageConfig
from .fees import FeeCalculator, FeeConfig

__all__ = [
    "PaperTradingSimulator",
    "PaperTradingConfig",
    "SlippageEngine",
    "SlippageConfig",
    "FeeCalculator",
    "FeeConfig",
]
