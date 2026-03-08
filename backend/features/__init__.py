"""
Feature Engineering Module for Market Data

This module provides on-the-fly calculation of basic metrics from market data,
including price standard deviation, velocity, order book imbalance, and more.
"""

from backend.features.basic_metrics import (
    calculate_std_dev_price,
    calculate_velocity,
    calculate_order_book_imbalance,
    calculate_taker_buy_sell_ratio,
    calculate_distance_to_target,
    calculate_features,
)

__all__ = [
    "calculate_std_dev_price",
    "calculate_velocity",
    "calculate_order_book_imbalance",
    "calculate_taker_buy_sell_ratio",
    "calculate_distance_to_target",
    "calculate_features",
]
