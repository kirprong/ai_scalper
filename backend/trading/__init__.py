"""
Trading Module.

This module provides trading functionality including paper trading simulation,
order execution, position management, and multi-account support.

Components:
- PaperTradingSimulator: Simulates trading with slippage and latency
- SlippageEngine: Calculates realistic slippage
- FeeCalculator: Calculates trading fees
- AccountManager: Manages multiple Polymarket accounts with rotation and failover
"""

from .paper_trading import PaperTradingSimulator, PaperTradingConfig
from .slippage import SlippageEngine, SlippageConfig
from .fees import FeeCalculator, FeeConfig
from .account_manager import (
    AccountManager,
    AccountState,
    RotationStrategy,
    FailoverResult,
)

__all__ = [
    "PaperTradingSimulator",
    "PaperTradingConfig",
    "SlippageEngine",
    "SlippageConfig",
    "FeeCalculator",
    "FeeConfig",
    "AccountManager",
    "AccountState",
    "RotationStrategy",
    "FailoverResult",
]
