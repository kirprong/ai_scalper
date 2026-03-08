"""
Console UI Module - Rich Terminal Dashboard for AI Lead Scalper
"""

from .dashboard import Dashboard
from .widgets import (
    PnLWidget,
    MLStatusWidget,
    TradingStatsWidget,
    SystemStatusWidget
)

__all__ = [
    'Dashboard',
    'PnLWidget',
    'MLStatusWidget',
    'TradingStatsWidget',
    'SystemStatusWidget'
]
