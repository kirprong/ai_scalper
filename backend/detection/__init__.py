"""
Detection Module for Market Pattern Recognition

This module provides pattern detection algorithms for identifying
trading opportunities in market data.

Modules:
- golden_rectangle: Detector for Golden Rectangle consolidation boxes
"""

from .golden_rectangle import (
    find_rectangles,
    GoldenRectangle,
    RectangleConfig,
)

__all__ = [
    "find_rectangles",
    "GoldenRectangle",
    "RectangleConfig",
]
