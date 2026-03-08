"""
Advanced Feature Engineering Metrics for Market Data

This module provides advanced statistical metrics for mean-reversion analysis,
including Hurst Exponent and EMA Zero Crossings calculations.

Metrics:
- Hurst Exponent: Measures long-term memory of time series
- EMA Zero Crossings: Counts price crosses of EMA within a window
- Mean-Reversion Score: Combined metric for mean-reversion characteristics
"""

import logging
from dataclasses import dataclass
from typing import Optional, Tuple, List

import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class AdvancedMetricsConfig:
    """Configuration for advanced metrics calculations."""
    hurst_window: int = 100
    ema_period: int = 20
    crossing_window: int = 100
    min_hurst_periods: int = 20


# Default configuration
DEFAULT_CONFIG = AdvancedMetricsConfig()


def calculate_hurst_exponent(
    series: np.ndarray,
    min_periods: int = DEFAULT_CONFIG.min_hurst_periods
) -> float:
    """
    Calculate the Hurst Exponent using Rescaled Range (R/S) analysis.
    
    The Hurst Exponent measures the long-term memory of a time series:
    - H < 0.5: Mean-reverting series (anti-persistent)
    - H = 0.5: Random walk (Brownian motion)
    - H > 0.5: Trending series (persistent)
    
    Method: R/S Analysis
    1. Divide the series into sub-periods
    2. For each sub-period, calculate the cumulative deviations from mean
    3. Calculate the range R = max - min of cumulative deviations
    4. Calculate the standard deviation S
    5. Compute R/S ratio
    6. H = slope of log(R/S) vs log(n)
    
    Args:
        series: 1D numpy array of price or return values
        min_periods: Minimum number of periods required for calculation
        
    Returns:
        float: Hurst Exponent value (0 to 1)
        
    Raises:
        ValueError: If series is too short or contains invalid values
        
    Example:
        >>> import numpy as np
        >>> # Random noise should have H ≈ 0.5
        >>> np.random.seed(42)
        >>> noise = np.random.randn(1000)
        >>> h = calculate_hurst_exponent(noise)
        >>> 0.4 < h < 0.6  # Should be close to 0.5
        True
        >>> # Trending series should have H > 0.5
        >>> trend = np.cumsum(np.ones(1000) * 0.01) + np.random.randn(1000) * 0.1
        >>> h_trend = calculate_hurst_exponent(trend)
        >>> h_trend > 0.5
        True
    """
    # Validate input
    if series is None or len(series) < min_periods:
        raise ValueError(f"Series must have at least {min_periods} periods")
    
    series = np.asarray(series, dtype=float)
    
    # Remove NaN values
    series = series[~np.isnan(series)]
    
    if len(series) < min_periods:
        raise ValueError(f"Series must have at least {min_periods} valid periods after removing NaN")
    
    n = len(series)
    
    # Calculate R/S for different sub-period sizes
    # Use powers of 2 for sub-period sizes
    max_k = int(np.floor(np.log2(n)))
    if max_k < 2:
        raise ValueError("Series too short for R/S analysis")
    
    rs_values = []
    n_values = []
    
    for k in range(2, max_k + 1):
        sub_period_size = 2 ** k
        
        # Number of sub-periods
        num_sub_periods = n // sub_period_size
        
        if num_sub_periods < 1:
            continue
        
        rs_list = []
        
        for i in range(num_sub_periods):
            start_idx = i * sub_period_size
            end_idx = start_idx + sub_period_size
            sub_series = series[start_idx:end_idx]
            
            # Calculate mean
            mean = np.mean(sub_series)
            
            # Calculate cumulative deviations from mean
            cum_dev = np.cumsum(sub_series - mean)
            
            # Calculate range R
            r = np.max(cum_dev) - np.min(cum_dev)
            
            # Calculate standard deviation S
            s = np.std(sub_series, ddof=1)
            
            # Avoid division by zero
            if s > 0 and r > 0:
                rs = r / s
                rs_list.append(rs)
        
        if rs_list:
            # Use mean of R/S values for this sub-period size
            rs_values.append(np.mean(rs_list))
            n_values.append(sub_period_size)
    
    if len(rs_values) < 2:
        # Fall back to simpler calculation for short series
        return _calculate_hurst_simple(series)
    
    # Calculate Hurst exponent as slope of log(R/S) vs log(n)
    log_n = np.log(n_values)
    log_rs = np.log(rs_values)
    
    # Linear regression to find slope
    slope, _ = np.polyfit(log_n, log_rs, 1)
    
    # Clamp to valid range [0, 1]
    hurst = np.clip(slope, 0.0, 1.0)
    
    return float(hurst)


def _calculate_hurst_simple(returns: np.ndarray) -> float:
    """
    Simple Hurst calculation for short series.
    
    Uses a simplified R/S calculation on the entire series.
    
    Args:
        returns: Array of return values
        
    Returns:
        float: Hurst Exponent estimate
    """
    n = len(returns)
    
    # Calculate mean
    mean = np.mean(returns)
    
    # Calculate cumulative deviations from mean
    cum_dev = np.cumsum(returns - mean)
    
    # Calculate range R
    r = np.max(cum_dev) - np.min(cum_dev)
    
    # Calculate standard deviation S
    s = np.std(returns, ddof=1)
    
    if s == 0 or r == 0:
        return 0.5  # Return random walk value for degenerate cases
    
    # R/S ratio
    rs = r / s
    
    # Estimate Hurst from single R/S value
    # log(R/S) = H * log(n)
    # H = log(R/S) / log(n)
    hurst = np.log(rs) / np.log(n)
    
    # Clamp to valid range [0, 1]
    return float(np.clip(hurst, 0.0, 1.0))


def calculate_hurst_exponent_rolling(
    df: pd.DataFrame,
    price_column: str = "price",
    window: int = DEFAULT_CONFIG.hurst_window,
    min_periods: int = DEFAULT_CONFIG.min_hurst_periods
) -> pd.Series:
    """
    Calculate rolling Hurst Exponent for a price series.
    
    This function applies the Hurst Exponent calculation over a rolling window,
    useful for detecting changes in market regime (trending vs mean-reverting).
    
    Args:
        df: DataFrame containing price data
        price_column: Name of the price column (default: "price")
        window: Rolling window size (default: 100)
        min_periods: Minimum periods required for calculation
        
    Returns:
        pd.Series: Rolling Hurst Exponent values
        
    Example:
        >>> import pandas as pd
        >>> import numpy as np
        >>> np.random.seed(42)
        >>> prices = pd.Series(np.cumsum(np.random.randn(200)) + 100)
        >>> df = pd.DataFrame({"price": prices})
        >>> hurst_series = calculate_hurst_exponent_rolling(df, window=100)
    """
    if price_column not in df.columns:
        raise ValueError(f"Column '{price_column}' not found in DataFrame")
    
    if len(df) == 0:
        return pd.Series(dtype=float)
    
    prices = df[price_column].values
    
    # Calculate rolling Hurst
    hurst_values = []
    
    for i in range(len(prices)):
        if i < min_periods:
            hurst_values.append(np.nan)
        else:
            start_idx = max(0, i - window + 1)
            window_data = prices[start_idx:i + 1]
            
            try:
                h = calculate_hurst_exponent(window_data, min_periods=min_periods)
                hurst_values.append(h)
            except ValueError:
                hurst_values.append(np.nan)
    
    return pd.Series(hurst_values, index=df.index)


def calculate_ema_crossings(
    df: pd.DataFrame,
    price_column: str = "price",
    ema_period: int = DEFAULT_CONFIG.ema_period,
    window: Optional[int] = None
) -> pd.DataFrame:
    """
    Calculate EMA Zero Crossings within a window.
    
    This metric counts how many times the price crosses its EMA within a window.
    - High crossing count (10-15+): Indicates ranging/box market (mean-reverting)
    - Low crossing count: Indicates trending market
    
    Args:
        df: DataFrame containing price data
        price_column: Name of the price column (default: "price")
        ema_period: EMA period (default: 20)
        window: Window size for crossing count (optional, uses entire series if None)
        
    Returns:
        pd.DataFrame: DataFrame with columns:
            - ema: The EMA values
            - price_ema_diff: Price minus EMA
            - crossing: Binary indicator of crossing (1 at crossing points)
            - crossing_count: Cumulative crossing count
            - crossing_rate: Crossing count per window
            
    Example:
        >>> import pandas as pd
        >>> import numpy as np
        >>> np.random.seed(42)
        >>> # Generate ranging market data
        >>> prices = pd.Series(100 + np.sin(np.linspace(0, 10*np.pi, 200)) * 2 + np.random.randn(200) * 0.5)
        >>> df = pd.DataFrame({"price": prices})
        >>> crossings = calculate_ema_crossings(df, ema_period=20, window=100)
        >>> # Ranging market should have high crossing count
        >>> crossings['crossing_count'].iloc[-1] > 5
        True
    """
    if price_column not in df.columns:
        raise ValueError(f"Column '{price_column}' not found in DataFrame")
    
    if len(df) == 0:
        return pd.DataFrame(columns=[
            "ema", "price_ema_diff", "crossing", "crossing_count", "crossing_rate"
        ])
    
    prices = df[price_column]
    
    # Calculate EMA
    ema = prices.ewm(span=ema_period, adjust=False).mean()
    
    # Calculate price - EMA difference
    price_ema_diff = prices - ema
    
    # Detect crossings (sign changes)
    # A crossing occurs when price_ema_diff changes sign
    sign = np.sign(price_ema_diff)
    
    # Handle zero values (price exactly at EMA)
    sign = sign.replace(0, np.nan).ffill().fillna(0)
    
    # Crossing occurs when sign changes
    crossing = (sign.diff() != 0).astype(int)
    
    # First value can't be a crossing
    crossing.iloc[0] = 0
    
    # Cumulative crossing count
    crossing_count = crossing.cumsum()
    
    # Calculate crossing rate (crossings per window)
    if window is not None:
        crossing_rate = crossing.rolling(window=window, min_periods=1).sum()
    else:
        # Rate per 100 periods
        crossing_rate = crossing_count / (np.arange(len(df)) + 1) * 100
    
    result = pd.DataFrame({
        "ema": ema,
        "price_ema_diff": price_ema_diff,
        "crossing": crossing,
        "crossing_count": crossing_count,
        "crossing_rate": crossing_rate
    }, index=df.index)
    
    return result


def calculate_ema_crossings_count(
    df: pd.DataFrame,
    price_column: str = "price",
    ema_period: int = DEFAULT_CONFIG.ema_period,
    window: int = DEFAULT_CONFIG.crossing_window
) -> pd.Series:
    """
    Calculate rolling EMA crossing count.
    
    This is a convenience function that returns just the crossing count
    within each rolling window.
    
    Args:
        df: DataFrame containing price data
        price_column: Name of the price column (default: "price")
        ema_period: EMA period (default: 20)
        window: Window size for crossing count (default: 100)
        
    Returns:
        pd.Series: Rolling crossing count within window
        
    Example:
        >>> import pandas as pd
        >>> import numpy as np
        >>> np.random.seed(42)
        >>> prices = pd.Series(100 + np.cumsum(np.random.randn(200)))
        >>> df = pd.DataFrame({"price": prices})
        >>> crossing_count = calculate_ema_crossings_count(df, window=50)
    """
    crossings_df = calculate_ema_crossings(df, price_column, ema_period, window)
    return crossings_df["crossing_rate"]


def calculate_mean_reversion_score(
    df: pd.DataFrame,
    price_column: str = "price",
    hurst_window: int = DEFAULT_CONFIG.hurst_window,
    ema_period: int = DEFAULT_CONFIG.ema_period,
    crossing_window: int = DEFAULT_CONFIG.crossing_window,
    hurst_weight: float = 0.5
) -> pd.DataFrame:
    """
    Calculate a combined mean-reversion score.
    
    This score combines Hurst Exponent and EMA crossing metrics to provide
    a single indicator of mean-reversion characteristics.
    
    Score interpretation:
    - High score (>0.6): Strong mean-reversion (ranging market)
    - Medium score (0.4-0.6): Neutral/transitioning
    - Low score (<0.4): Trending market
    
    Formula:
        score = hurst_weight * (1 - H) + (1 - hurst_weight) * normalized_crossings
        
    Where:
    - H is the Hurst Exponent (lower = more mean-reverting)
    - normalized_crossings is the crossing rate scaled to [0, 1]
    
    Args:
        df: DataFrame containing price data
        price_column: Name of the price column (default: "price")
        hurst_window: Window for Hurst calculation (default: 100)
        ema_period: EMA period (default: 20)
        crossing_window: Window for crossing count (default: 100)
        hurst_weight: Weight for Hurst component (default: 0.5)
        
    Returns:
        pd.DataFrame: DataFrame with columns:
            - hurst_exponent: Rolling Hurst Exponent
            - crossing_rate: EMA crossing rate
            - mean_reversion_score: Combined score
            
    Example:
        >>> import pandas as pd
        >>> import numpy as np
        >>> np.random.seed(42)
        >>> # Generate ranging market
        >>> prices = pd.Series(100 + np.sin(np.linspace(0, 8*np.pi, 200)) * 2)
        >>> df = pd.DataFrame({"price": prices})
        >>> scores = calculate_mean_reversion_score(df)
        >>> # Ranging market should have high mean reversion score
        >>> scores['mean_reversion_score'].iloc[-1] > 0.5
        True
    """
    if price_column not in df.columns:
        raise ValueError(f"Column '{price_column}' not found in DataFrame")
    
    if len(df) == 0:
        return pd.DataFrame(columns=[
            "hurst_exponent", "crossing_rate", "mean_reversion_score"
        ])
    
    # Calculate Hurst Exponent
    hurst = calculate_hurst_exponent_rolling(
        df,
        price_column=price_column,
        window=hurst_window
    )
    
    # Calculate EMA crossings
    crossings_df = calculate_ema_crossings(
        df,
        price_column=price_column,
        ema_period=ema_period,
        window=crossing_window
    )
    crossing_rate = crossings_df["crossing_rate"]
    
    # Normalize crossing rate
    # Assume 10-15 crossings per 100 periods is "high" for a ranging market
    # Scale: 0 crossings = 0, 15+ crossings = 1
    max_expected_crossings = 15.0
    normalized_crossings = np.clip(crossing_rate / max_expected_crossings, 0, 1)
    
    # Calculate mean reversion score
    # Lower Hurst = more mean-reverting, so we use (1 - H)
    # Higher crossings = more mean-reverting
    crossing_weight = 1 - hurst_weight
    mean_reversion_score = (
        hurst_weight * (1 - hurst) + 
        crossing_weight * normalized_crossings
    )
    
    # Handle NaN values
    mean_reversion_score = mean_reversion_score.fillna(0.5)  # Neutral for missing data
    
    result = pd.DataFrame({
        "hurst_exponent": hurst,
        "crossing_rate": crossing_rate,
        "mean_reversion_score": mean_reversion_score
    }, index=df.index)
    
    return result


def calculate_advanced_features(
    df: pd.DataFrame,
    config: Optional[AdvancedMetricsConfig] = None,
    price_column: str = "price"
) -> pd.DataFrame:
    """
    Calculate all advanced features on-the-fly.
    
    This is the main entry point for advanced feature engineering,
    calculating all mean-reversion metrics in a single call.
    
    Args:
        df: DataFrame containing market data
        config: Advanced metrics configuration (optional)
        price_column: Name of the price column
        
    Returns:
        pd.DataFrame: DataFrame with all calculated features:
            - hurst_exponent: Rolling Hurst Exponent
            - ema: EMA values
            - price_ema_diff: Price minus EMA
            - crossing_count: Cumulative EMA crossing count
            - crossing_rate: EMA crossing rate per window
            - mean_reversion_score: Combined mean-reversion score
            
    Example:
        >>> import pandas as pd
        >>> import numpy as np
        >>> np.random.seed(42)
        >>> prices = pd.Series(100 + np.cumsum(np.random.randn(200)))
        >>> df = pd.DataFrame({"price": prices})
        >>> features = calculate_advanced_features(df)
    """
    if config is None:
        config = DEFAULT_CONFIG
    
    if len(df) == 0:
        return pd.DataFrame(columns=[
            "hurst_exponent",
            "ema",
            "price_ema_diff",
            "crossing_count",
            "crossing_rate",
            "mean_reversion_score"
        ])
    
    # Calculate mean reversion score (includes Hurst and crossings)
    try:
        mr_scores = calculate_mean_reversion_score(
            df,
            price_column=price_column,
            hurst_window=config.hurst_window,
            ema_period=config.ema_period,
            crossing_window=config.crossing_window
        )
    except ValueError as e:
        logger.warning(f"Could not calculate mean reversion score: {e}")
        return pd.DataFrame(columns=[
            "hurst_exponent",
            "ema",
            "price_ema_diff",
            "crossing_count",
            "crossing_rate",
            "mean_reversion_score"
        ], index=df.index)
    
    # Get EMA crossing details
    try:
        crossings_df = calculate_ema_crossings(
            df,
            price_column=price_column,
            ema_period=config.ema_period,
            window=config.crossing_window
        )
    except ValueError as e:
        logger.warning(f"Could not calculate EMA crossings: {e}")
        crossings_df = pd.DataFrame(
            index=df.index,
            columns=["ema", "price_ema_diff", "crossing_count", "crossing_rate"]
        )
    
    # Combine results
    result = pd.DataFrame({
        "hurst_exponent": mr_scores["hurst_exponent"],
        "ema": crossings_df["ema"],
        "price_ema_diff": crossings_df["price_ema_diff"],
        "crossing_count": crossings_df["crossing_count"],
        "crossing_rate": mr_scores["crossing_rate"],
        "mean_reversion_score": mr_scores["mean_reversion_score"]
    }, index=df.index)
    
    logger.info(f"Calculated {len(result.columns)} advanced features for {len(result)} rows")
    
    return result
