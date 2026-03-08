"""
Feature Engineering Module for Market Data

This module provides on-the-fly calculation of basic metrics from market data,
including price standard deviation, velocity, order book imbalance, and more.

Advanced metrics include Hurst Exponent and EMA Zero Crossings for mean-reversion analysis.
"""

from backend.features.basic_metrics import (
    calculate_std_dev_price,
    calculate_velocity,
    calculate_order_book_imbalance,
    calculate_taker_buy_sell_ratio,
    calculate_distance_to_target,
    calculate_features,
)

from backend.features.advanced_metrics import (
    calculate_hurst_exponent,
    calculate_hurst_exponent_rolling,
    calculate_ema_crossings,
    calculate_ema_crossings_count,
    calculate_mean_reversion_score,
    calculate_advanced_features,
)

__all__ = [
    # Basic metrics
    "calculate_std_dev_price",
    "calculate_velocity",
    "calculate_order_book_imbalance",
    "calculate_taker_buy_sell_ratio",
    "calculate_distance_to_target",
    "calculate_features",
    # Advanced metrics
    "calculate_hurst_exponent",
    "calculate_hurst_exponent_rolling",
    "calculate_ema_crossings",
    "calculate_ema_crossings_count",
    "calculate_mean_reversion_score",
    "calculate_advanced_features",
]
