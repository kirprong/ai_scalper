"""
Basic Feature Engineering Metrics for Market Data

This module provides on-the-fly calculation of basic metrics from market data.
All metrics are calculated in real-time for use in trading signal generation.

Metrics:
- std_dev_price: Rolling standard deviation of price
- velocity: Rate of change (momentum indicator)
- order_book_imbalance: (bid_volume - ask_volume) / (bid_volume + ask_volume)
- taker_buy_sell_ratio: buy_volume / sell_volume
- distance_to_target: Delta between current price and Polymarket target
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class FeatureConfig:
    """Configuration for feature calculations."""
    std_dev_window: int = 20
    velocity_window: int = 10
    default_target_price: float = 0.5


# Default configuration
DEFAULT_CONFIG = FeatureConfig()


def calculate_std_dev_price(
    df: pd.DataFrame,
    price_column: str = "price",
    window: int = DEFAULT_CONFIG.std_dev_window,
    min_periods: int = 1
) -> pd.Series:
    """
    Calculate rolling standard deviation of price.

    This metric measures price volatility over a configurable window.
    Higher values indicate more volatile price movements.

    Args:
        df: DataFrame containing market data
        price_column: Name of the price column (default: "price")
        window: Rolling window size (default: 20)
        min_periods: Minimum number of observations required (default: 1)

    Returns:
        pd.Series: Rolling standard deviation of price

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({"price": [100, 101, 102, 101, 100]})
        >>> std_dev = calculate_std_dev_price(df, window=3)
    """
    if price_column not in df.columns:
        raise ValueError(f"Column '{price_column}' not found in DataFrame")

    if len(df) == 0:
        return pd.Series(dtype=float)

    return df[price_column].rolling(
        window=window,
        min_periods=min_periods
    ).std()


def calculate_velocity(
    df: pd.DataFrame,
    price_column: str = "price",
    time_column: str = "ts",
    window: int = DEFAULT_CONFIG.velocity_window
) -> pd.Series:
    """
    Calculate price velocity (rate of change per unit time).

    Velocity measures the momentum of price movements, calculated as
    the price change divided by the time elapsed.

    Formula: velocity = (price[t] - price[t-window]) / (time[t] - time[t-window])

    Args:
        df: DataFrame containing market data
        price_column: Name of the price column (default: "price")
        time_column: Name of the timestamp column (default: "ts")
        window: Number of periods to look back (default: 10)

    Returns:
        pd.Series: Price velocity (price change per second)

    Example:
        >>> import pandas as pd
        >>> from datetime import datetime, timedelta
        >>> times = [datetime(2026, 3, 8, 10, 0, i) for i in range(5)]
        >>> df = pd.DataFrame({"price": [100, 101, 103, 102, 104], "ts": times})
        >>> velocity = calculate_velocity(df, window=2)
    """
    if price_column not in df.columns:
        raise ValueError(f"Column '{price_column}' not found in DataFrame")

    if time_column not in df.columns:
        raise ValueError(f"Column '{time_column}' not found in DataFrame")

    if len(df) == 0:
        return pd.Series(dtype=float)

    # Ensure time column is datetime
    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df[time_column]):
        df[time_column] = pd.to_datetime(df[time_column])

    # Calculate price difference
    price_diff = df[price_column].diff(window)

    # Calculate time difference in seconds
    time_diff = df[time_column].diff(window).dt.total_seconds()

    # Avoid division by zero
    time_diff = time_diff.replace(0, np.nan)

    # Calculate velocity (price change per second)
    velocity = price_diff / time_diff

    return velocity


def calculate_order_book_imbalance(
    df: pd.DataFrame,
    bid_volume_column: str = "bid_volume",
    ask_volume_column: str = "ask_volume"
) -> pd.Series:
    """
    Calculate order book imbalance.

    Order book imbalance measures the pressure between buyers and sellers
    in the order book. Values range from -1 (heavy sell pressure) to +1
    (heavy buy pressure).

    Formula: imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)

    Args:
        df: DataFrame containing order book data
        bid_volume_column: Name of the bid volume column (default: "bid_volume")
        ask_volume_column: Name of the ask volume column (default: "ask_volume")

    Returns:
        pd.Series: Order book imbalance (-1 to 1)

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     "bid_volume": [100, 150, 80],
        ...     "ask_volume": [80, 100, 120]
        ... })
        >>> imbalance = calculate_order_book_imbalance(df)
        >>> # First row: (100-80)/(100+80) = 0.111
    """
    if bid_volume_column not in df.columns:
        raise ValueError(f"Column '{bid_volume_column}' not found in DataFrame")

    if ask_volume_column not in df.columns:
        raise ValueError(f"Column '{ask_volume_column}' not found in DataFrame")

    if len(df) == 0:
        return pd.Series(dtype=float)

    bid_volume = df[bid_volume_column]
    ask_volume = df[ask_volume_column]

    # Calculate total volume
    total_volume = bid_volume + ask_volume

    # Avoid division by zero
    total_volume = total_volume.replace(0, np.nan)

    # Calculate imbalance
    imbalance = (bid_volume - ask_volume) / total_volume

    return imbalance


def calculate_taker_buy_sell_ratio(
    df: pd.DataFrame,
    buy_volume_column: str = "buy_volume",
    sell_volume_column: str = "sell_volume"
) -> pd.Series:
    """
    Calculate taker buy/sell ratio.

    This metric indicates market pressure from taker orders.
    Values > 1 indicate buying pressure, values < 1 indicate selling pressure.

    Formula: ratio = buy_volume / sell_volume

    Args:
        df: DataFrame containing trade data
        buy_volume_column: Name of the buy volume column (default: "buy_volume")
        sell_volume_column: Name of the sell volume column (default: "sell_volume")

    Returns:
        pd.Series: Taker buy/sell ratio

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     "buy_volume": [100, 150, 80],
        ...     "sell_volume": [80, 100, 120]
        ... })
        >>> ratio = calculate_taker_buy_sell_ratio(df)
        >>> # First row: 100/80 = 1.25
    """
    if buy_volume_column not in df.columns:
        raise ValueError(f"Column '{buy_volume_column}' not found in DataFrame")

    if sell_volume_column not in df.columns:
        raise ValueError(f"Column '{sell_volume_column}' not found in DataFrame")

    if len(df) == 0:
        return pd.Series(dtype=float)

    buy_volume = df[buy_volume_column]
    sell_volume = df[sell_volume_column]

    # Avoid division by zero
    sell_volume_safe = sell_volume.replace(0, np.nan)

    # Calculate ratio
    ratio = buy_volume / sell_volume_safe

    return ratio


def calculate_distance_to_target(
    df: pd.DataFrame,
    price_column: str = "price",
    target_price: Optional[float] = None,
    target_column: Optional[str] = None
) -> pd.DataFrame:
    """
    Calculate distance to target price.

    This metric measures how far the current price is from a target price
    (e.g., Polymarket prediction market target).

    Returns both absolute distance and percentage distance.

    Args:
        df: DataFrame containing price data
        price_column: Name of the price column (default: "price")
        target_price: Target price value (optional, uses default if not provided)
        target_column: Name of column containing target prices (optional)

    Returns:
        pd.DataFrame: DataFrame with columns:
            - distance_absolute: Absolute price difference
            - distance_percentage: Percentage distance from target

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({"price": [0.45, 0.48, 0.52]})
        >>> distance = calculate_distance_to_target(df, target_price=0.5)
        >>> # distance_percentage: [-0.10, -0.04, 0.04]
    """
    if price_column not in df.columns:
        raise ValueError(f"Column '{price_column}' not found in DataFrame")

    if len(df) == 0:
        return pd.DataFrame(columns=["distance_absolute", "distance_percentage"])

    # Get target price
    if target_column is not None:
        if target_column not in df.columns:
            raise ValueError(f"Column '{target_column}' not found in DataFrame")
        target = df[target_column]
    elif target_price is not None:
        target = target_price
    else:
        target = DEFAULT_CONFIG.default_target_price
        logger.debug(f"Using default target price: {target}")

    price = df[price_column]

    # Calculate absolute distance
    distance_absolute = price - target

    # Calculate percentage distance
    # Avoid division by zero
    target_safe = target if isinstance(target, (int, float)) else target.replace(0, np.nan)
    distance_percentage = (price - target) / target_safe

    return pd.DataFrame({
        "distance_absolute": distance_absolute,
        "distance_percentage": distance_percentage
    })


def calculate_features(
    df: pd.DataFrame,
    config: Optional[FeatureConfig] = None,
    price_column: str = "price",
    time_column: str = "ts",
    bid_volume_column: str = "bid_volume",
    ask_volume_column: str = "ask_volume",
    buy_volume_column: str = "buy_volume",
    sell_volume_column: str = "sell_volume",
    target_price: Optional[float] = None,
    target_column: Optional[str] = None
) -> pd.DataFrame:
    """
    Calculate all basic features on-the-fly.

    This is the main entry point for feature engineering, calculating
    all metrics in a single call.

    Args:
        df: DataFrame containing market data
        config: Feature configuration (optional)
        price_column: Name of the price column
        time_column: Name of the timestamp column
        bid_volume_column: Name of the bid volume column
        ask_volume_column: Name of the ask volume column
        buy_volume_column: Name of the buy volume column
        sell_volume_column: Name of the sell volume column
        target_price: Target price for distance calculation
        target_column: Column containing target prices

    Returns:
        pd.DataFrame: DataFrame with all calculated features:
            - std_dev_price: Rolling standard deviation
            - velocity: Price velocity
            - order_book_imbalance: Order book pressure
            - taker_buy_sell_ratio: Taker buy/sell ratio
            - distance_absolute: Absolute distance to target
            - distance_percentage: Percentage distance to target

    Example:
        >>> import pandas as pd
        >>> from datetime import datetime
        >>> df = pd.DataFrame({
        ...     "price": [100, 101, 102, 101, 100],
        ...     "ts": [datetime(2026, 3, 8, 10, 0, i) for i in range(5)],
        ...     "bid_volume": [100, 120, 80, 90, 110],
        ...     "ask_volume": [80, 100, 120, 110, 90],
        ...     "buy_volume": [50, 60, 40, 45, 55],
        ...     "sell_volume": [40, 50, 60, 55, 45]
        ... })
        >>> features = calculate_features(df)
    """
    if config is None:
        config = DEFAULT_CONFIG

    if len(df) == 0:
        return pd.DataFrame(columns=[
            "std_dev_price",
            "velocity",
            "order_book_imbalance",
            "taker_buy_sell_ratio",
            "distance_absolute",
            "distance_percentage"
        ])

    # Create result DataFrame
    result = pd.DataFrame(index=df.index)

    # Calculate each feature with error handling
    try:
        result["std_dev_price"] = calculate_std_dev_price(
            df,
            price_column=price_column,
            window=config.std_dev_window
        )
    except ValueError as e:
        logger.warning(f"Could not calculate std_dev_price: {e}")
        result["std_dev_price"] = np.nan

    try:
        result["velocity"] = calculate_velocity(
            df,
            price_column=price_column,
            time_column=time_column,
            window=config.velocity_window
        )
    except ValueError as e:
        logger.warning(f"Could not calculate velocity: {e}")
        result["velocity"] = np.nan

    try:
        result["order_book_imbalance"] = calculate_order_book_imbalance(
            df,
            bid_volume_column=bid_volume_column,
            ask_volume_column=ask_volume_column
        )
    except ValueError as e:
        logger.warning(f"Could not calculate order_book_imbalance: {e}")
        result["order_book_imbalance"] = np.nan

    try:
        result["taker_buy_sell_ratio"] = calculate_taker_buy_sell_ratio(
            df,
            buy_volume_column=buy_volume_column,
            sell_volume_column=sell_volume_column
        )
    except ValueError as e:
        logger.warning(f"Could not calculate taker_buy_sell_ratio: {e}")
        result["taker_buy_sell_ratio"] = np.nan

    try:
        distance_df = calculate_distance_to_target(
            df,
            price_column=price_column,
            target_price=target_price,
            target_column=target_column
        )
        result["distance_absolute"] = distance_df["distance_absolute"]
        result["distance_percentage"] = distance_df["distance_percentage"]
    except ValueError as e:
        logger.warning(f"Could not calculate distance_to_target: {e}")
        result["distance_absolute"] = np.nan
        result["distance_percentage"] = np.nan

    logger.info(f"Calculated {len(result.columns)} features for {len(result)} rows")

    return result
