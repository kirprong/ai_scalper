"""
Golden Rectangle Detector for Market Data

This module provides detection of "Golden Rectangles" - price consolidation
boxes that indicate potential arbitrage opportunities.

A Golden Rectangle is a price consolidation zone where:
- Price oscillates within a defined range (support/resistance)
- The box represents a period of price stability before a breakout
- Target: boxes with >5% price range (arbitrage opportunity)

Algorithm:
1. Rolling Window Analysis (15-minute default)
2. Identify local support and resistance levels
3. Calculate price range percentage
4. Detect boxes with multiple boundary touches
5. Score box quality based on stability metrics
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class RectangleConfig:
    """Configuration for Golden Rectangle detection."""
    window_minutes: int = 15
    min_height_pct: float = 5.0
    min_touch_count: int = 2
    touch_threshold_pct: float = 0.5  # Percentage within boundary to count as touch
    breakout_threshold_pct: float = 1.0  # Price must stay within this % of box
    min_window_samples: int = 10  # Minimum samples in window
    overlap_tolerance: float = 0.3  # Tolerance for overlapping boxes


@dataclass
class GoldenRectangle:
    """Represents a detected Golden Rectangle."""
    box_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    symbol: str = ""
    ts_start: datetime = None
    ts_end: datetime = None
    price_min: float = 0.0
    price_max: float = 0.0
    height_pct: float = 0.0
    touch_count: int = 0
    quality_score: float = 0.0
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "box_id": self.box_id,
            "symbol": self.symbol,
            "ts_start": self.ts_start.isoformat() if self.ts_start else None,
            "ts_end": self.ts_end.isoformat() if self.ts_end else None,
            "price_min": self.price_min,
            "price_max": self.price_max,
            "height_pct": self.height_pct,
            "touch_count": self.touch_count,
            "quality_score": self.quality_score,
            "metadata": self.metadata
        }
    
    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"GoldenRectangle(id={self.box_id}, "
            f"range=[{self.price_min:.4f}, {self.price_max:.4f}], "
            f"height={self.height_pct:.2f}%, "
            f"touches={self.touch_count}, "
            f"quality={self.quality_score:.2f}, "
            f"time=[{self.ts_start}, {self.ts_end}])"
        )


# Default configuration
DEFAULT_CONFIG = RectangleConfig()


def calculate_rolling_bounds(
    df: pd.DataFrame,
    price_column: str = "price",
    window: int = 20
) -> pd.DataFrame:
    """
    Calculate rolling support and resistance levels.
    
    Args:
        df: DataFrame containing price data
        price_column: Name of the price column
        window: Rolling window size
        
    Returns:
        DataFrame with rolling_min, rolling_max, and range_pct columns
    """
    if price_column not in df.columns:
        raise ValueError(f"Column '{price_column}' not found in DataFrame")
    
    if len(df) == 0:
        return pd.DataFrame(columns=["rolling_min", "rolling_max", "range_pct"])
    
    result = pd.DataFrame(index=df.index)
    
    # Calculate rolling min and max
    result["rolling_min"] = df[price_column].rolling(
        window=window, min_periods=1
    ).min()
    result["rolling_max"] = df[price_column].rolling(
        window=window, min_periods=1
    ).max()
    
    # Calculate range percentage
    mid_price = (result["rolling_max"] + result["rolling_min"]) / 2
    result["range_pct"] = (
        (result["rolling_max"] - result["rolling_min"]) / mid_price * 100
    )
    
    return result


def detect_boundary_touches(
    prices: np.ndarray,
    price_min: float,
    price_max: float,
    threshold_pct: float = 0.5
) -> Tuple[int, int]:
    """
    Count touches of support and resistance boundaries.
    
    A touch is counted when price comes within threshold_pct of the boundary.
    
    Args:
        prices: Array of prices
        price_min: Lower boundary (support)
        price_max: Upper boundary (resistance)
        threshold_pct: Percentage within boundary to count as touch
        
    Returns:
        Tuple of (support_touches, resistance_touches)
    """
    if len(prices) == 0 or price_min >= price_max:
        return (0, 0)
    
    # Calculate threshold in price units
    box_height = price_max - price_min
    threshold = box_height * threshold_pct / 100
    
    # Count support touches (near price_min)
    support_touches = np.sum(prices <= (price_min + threshold))
    
    # Count resistance touches (near price_max)
    resistance_touches = np.sum(prices >= (price_max - threshold))
    
    return (int(support_touches), int(resistance_touches))


def check_box_validity(
    prices: np.ndarray,
    price_min: float,
    price_max: float,
    breakout_threshold_pct: float = 1.0
) -> bool:
    """
    Check if prices stay within the box boundaries.
    
    Args:
        prices: Array of prices
        price_min: Lower boundary
        price_max: Upper boundary
        breakout_threshold_pct: Allowed percentage outside boundaries
        
    Returns:
        True if prices stay within valid range
    """
    if len(prices) == 0:
        return False
    
    # Calculate allowed deviation
    box_height = price_max - price_min
    allowed_deviation = box_height * breakout_threshold_pct / 100
    
    # Check for breakouts
    lower_bound = price_min - allowed_deviation
    upper_bound = price_max + allowed_deviation
    
    # All prices should be within extended boundaries
    return bool(np.all((prices >= lower_bound) & (prices <= upper_bound)))


def calculate_quality_score(
    rectangle: GoldenRectangle,
    prices: np.ndarray,
    volumes: Optional[np.ndarray] = None
) -> float:
    """
    Calculate quality score for a Golden Rectangle.
    
    Quality is based on:
    - Number of boundary touches (more is better)
    - Price stability within the box (lower volatility is better)
    - Volume profile (lower volume = more stable)
    - Height percentage (larger = more profit potential)
    
    Args:
        rectangle: The Golden Rectangle to score
        prices: Array of prices within the box
        volumes: Optional array of volumes
        
    Returns:
        Quality score from 0 to 1
    """
    if len(prices) == 0:
        return 0.0
    
    scores = []
    
    # 1. Touch count score (normalized to 0-1, max expected ~10 touches)
    touch_score = min(rectangle.touch_count / 10.0, 1.0)
    scores.append(touch_score)
    
    # 2. Height score (normalized, target 5-15% range)
    height_score = min(rectangle.height_pct / 15.0, 1.0)
    scores.append(height_score)
    
    # 3. Stability score (inverse of coefficient of variation)
    price_std = np.std(prices)
    price_mean = np.mean(prices)
    if price_mean > 0:
        cv = price_std / price_mean
        stability_score = max(0, 1.0 - cv * 10)  # Lower CV is better
    else:
        stability_score = 0
    scores.append(stability_score)
    
    # 4. Volume consistency (if available)
    if volumes is not None and len(volumes) > 0:
        vol_cv = np.std(volumes) / (np.mean(volumes) + 1e-10)
        volume_score = max(0, 1.0 - vol_cv)
        scores.append(volume_score)
    
    # Weighted average
    weights = [0.3, 0.3, 0.25, 0.15] if volumes is not None else [0.35, 0.35, 0.3]
    
    # Ensure weights match scores
    weights = weights[:len(scores)]
    total_weight = sum(weights)
    weights = [w / total_weight for w in weights]
    
    quality = sum(s * w for s, w in zip(scores, weights))
    
    return round(quality, 4)


def find_rectangles(
    df: pd.DataFrame,
    window_minutes: int = 15,
    min_height_pct: float = 5.0,
    price_column: str = "price",
    time_column: str = "ts",
    volume_column: Optional[str] = "volume",
    symbol: str = "",
    config: Optional[RectangleConfig] = None
) -> List[GoldenRectangle]:
    """
    Find Golden Rectangles in price data.
    
    This is the main entry point for Golden Rectangle detection.
    It scans price data in rolling windows and identifies consolidation
    boxes that meet the criteria for arbitrage opportunities.
    
    Args:
        df: DataFrame with columns [ts, price, volume]
        window_minutes: Rolling window size in minutes (default: 15)
        min_height_pct: Minimum box height percentage (default: 5.0)
        price_column: Name of the price column
        time_column: Name of the timestamp column
        volume_column: Name of the volume column (optional)
        symbol: Trading pair symbol
        config: Optional configuration object
        
    Returns:
        List of detected GoldenRectangle objects
        
    Example:
        >>> import pandas as pd
        >>> from datetime import datetime, timedelta
        >>> 
        >>> # Create sample data with consolidation
        >>> times = [datetime(2026, 3, 8, 10, 0) + timedelta(minutes=i) 
        ...          for i in range(30)]
        >>> # Price oscillates between 100 and 105
        >>> prices = [100 + 5 * (i % 2) + np.random.uniform(-0.5, 0.5) 
        ...           for i in range(30)]
        >>> df = pd.DataFrame({"ts": times, "price": prices})
        >>> 
        >>> rectangles = find_rectangles(df, window_minutes=15, min_height_pct=4.0)
    """
    # Use config if provided, otherwise create from parameters
    if config is None:
        config = RectangleConfig(
            window_minutes=window_minutes,
            min_height_pct=min_height_pct
        )
    
    # Validate input
    if price_column not in df.columns:
        raise ValueError(f"Column '{price_column}' not found in DataFrame")
    if time_column not in df.columns:
        raise ValueError(f"Column '{time_column}' not found in DataFrame")
    
    if len(df) < config.min_window_samples:
        logger.warning(f"Insufficient data: {len(df)} rows, need at least {config.min_window_samples}")
        return []
    
    # Ensure time column is datetime
    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df[time_column]):
        df[time_column] = pd.to_datetime(df[time_column])
    
    # Sort by time
    df = df.sort_values(time_column).reset_index(drop=True)
    
    # Calculate window size in number of samples
    time_diffs = df[time_column].diff().dt.total_seconds().median()
    if pd.isna(time_diffs) or time_diffs <= 0:
        time_diffs = 60  # Assume 1 minute default
    
    window_samples = int(config.window_minutes * 60 / time_diffs)
    window_samples = max(window_samples, config.min_window_samples)
    
    logger.info(f"Scanning for Golden Rectangles with window={config.window_minutes}min "
                f"({window_samples} samples), min_height={config.min_height_pct}%")
    
    rectangles = []
    
    # Rolling window analysis
    for i in range(len(df) - window_samples + 1):
        window_df = df.iloc[i:i + window_samples]
        
        # Get window data
        prices = window_df[price_column].values
        times = window_df[time_column].values
        
        # Calculate potential box boundaries
        price_min = np.min(prices)
        price_max = np.max(prices)
        price_mid = (price_min + price_max) / 2
        
        # Calculate height percentage
        if price_mid > 0:
            height_pct = (price_max - price_min) / price_mid * 100
        else:
            continue
        
        # Check minimum height requirement
        if height_pct < config.min_height_pct:
            continue
        
        # Check box validity (no breakouts)
        if not check_box_validity(
            prices, price_min, price_max,
            config.breakout_threshold_pct
        ):
            continue
        
        # Count boundary touches
        support_touches, resistance_touches = detect_boundary_touches(
            prices, price_min, price_max, config.touch_threshold_pct
        )
        total_touches = support_touches + resistance_touches
        
        # Check minimum touch count
        if total_touches < config.min_touch_count:
            continue
        
        # Create rectangle
        rectangle = GoldenRectangle(
            symbol=symbol,
            ts_start=pd.to_datetime(times[0]),
            ts_end=pd.to_datetime(times[-1]),
            price_min=price_min,
            price_max=price_max,
            height_pct=round(height_pct, 4),
            touch_count=total_touches
        )
        
        # Get volumes if available
        volumes = None
        if volume_column and volume_column in df.columns:
            volumes = window_df[volume_column].values
        
        # Calculate quality score
        rectangle.quality_score = calculate_quality_score(
            rectangle, prices, volumes
        )
        
        # Add metadata
        rectangle.metadata = {
            "window_samples": window_samples,
            "support_touches": support_touches,
            "resistance_touches": resistance_touches,
            "price_std": float(np.std(prices)),
            "price_mean": float(np.mean(prices))
        }
        
        rectangles.append(rectangle)
    
    # Remove overlapping rectangles (keep best quality)
    rectangles = _remove_overlapping_rectangles(
        rectangles, config.overlap_tolerance
    )
    
    logger.info(f"Found {len(rectangles)} Golden Rectangles")
    for rect in rectangles:
        logger.info(f"  {rect}")
    
    return rectangles


def _remove_overlapping_rectangles(
    rectangles: List[GoldenRectangle],
    overlap_tolerance: float
) -> List[GoldenRectangle]:
    """
    Remove overlapping rectangles, keeping the highest quality ones.
    
    Args:
        rectangles: List of rectangles to filter
        overlap_tolerance: Tolerance for overlap detection
        
    Returns:
        Filtered list of non-overlapping rectangles
    """
    if len(rectangles) <= 1:
        return rectangles
    
    # Sort by quality score (descending)
    rectangles = sorted(rectangles, key=lambda r: r.quality_score, reverse=True)
    
    filtered = []
    for rect in rectangles:
        # Check if this rectangle overlaps with any already selected
        is_overlapping = False
        for selected in filtered:
            if _rectangles_overlap(rect, selected, overlap_tolerance):
                is_overlapping = True
                break
        
        if not is_overlapping:
            filtered.append(rect)
    
    return filtered


def _rectangles_overlap(
    r1: GoldenRectangle,
    r2: GoldenRectangle,
    tolerance: float
) -> bool:
    """
    Check if two rectangles overlap in time and price.
    
    Args:
        r1: First rectangle
        r2: Second rectangle
        tolerance: Overlap tolerance (0-1)
        
    Returns:
        True if rectangles overlap
    """
    # Check time overlap
    time_overlap = False
    if r1.ts_start and r1.ts_end and r2.ts_start and r2.ts_end:
        latest_start = max(r1.ts_start, r2.ts_start)
        earliest_end = min(r1.ts_end, r2.ts_end)
        
        if latest_start < earliest_end:
            # Calculate overlap percentage
            r1_duration = (r1.ts_end - r1.ts_start).total_seconds()
            overlap_duration = (earliest_end - latest_start).total_seconds()
            
            if r1_duration > 0:
                overlap_pct = overlap_duration / r1_duration
                time_overlap = overlap_pct > tolerance
    
    # Check price overlap
    price_overlap = False
    r1_height = r1.price_max - r1.price_min
    r2_height = r2.price_max - r2.price_min
    
    if r1_height > 0 and r2_height > 0:
        # Check if price ranges overlap
        lower_bound = max(r1.price_min, r2.price_min)
        upper_bound = min(r1.price_max, r2.price_max)
        
        if upper_bound > lower_bound:
            price_overlap = True
    
    return time_overlap and price_overlap


def find_rectangles_in_range(
    df: pd.DataFrame,
    start_time: datetime,
    end_time: datetime,
    **kwargs
) -> List[GoldenRectangle]:
    """
    Find Golden Rectangles within a specific time range.
    
    Args:
        df: DataFrame with price data
        start_time: Start of time range
        end_time: End of time range
        **kwargs: Additional arguments passed to find_rectangles
        
    Returns:
        List of detected rectangles
    """
    # Filter data by time range
    time_column = kwargs.get("time_column", "ts")
    
    if time_column not in df.columns:
        raise ValueError(f"Column '{time_column}' not found in DataFrame")
    
    # Ensure datetime
    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df[time_column]):
        df[time_column] = pd.to_datetime(df[time_column])
    
    mask = (df[time_column] >= start_time) & (df[time_column] <= end_time)
    filtered_df = df[mask]
    
    logger.info(f"Filtering data: {len(filtered_df)} rows in range "
                f"[{start_time}, {end_time}]")
    
    return find_rectangles(filtered_df, **kwargs)


# CLI entry point
def main():
    """CLI entry point for running Golden Rectangle detection on historical data."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(
        description="Detect Golden Rectangles in historical market data"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input CSV file with historical data (columns: ts, price, volume)"
    )
    parser.add_argument(
        "--window", "-w",
        type=int,
        default=15,
        help="Rolling window size in minutes (default: 15)"
    )
    parser.add_argument(
        "--min-height", "-m",
        type=float,
        default=5.0,
        help="Minimum box height percentage (default: 5.0)"
    )
    parser.add_argument(
        "--symbol", "-s",
        default="UNKNOWN",
        help="Trading pair symbol"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output JSON file for detected rectangles"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Load data
    try:
        df = pd.read_csv(args.input)
        logger.info(f"Loaded {len(df)} rows from {args.input}")
    except Exception as e:
        logger.error(f"Failed to load input file: {e}")
        sys.exit(1)
    
    # Run detection
    rectangles = find_rectangles(
        df,
        window_minutes=args.window,
        min_height_pct=args.min_height,
        symbol=args.symbol
    )
    
    # Output results
    if args.output:
        import json
        
        # Custom encoder for numpy types
        class NumpyEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, (np.integer, np.int64, np.int32)):
                    return int(obj)
                if isinstance(obj, (np.floating, np.float64, np.float32)):
                    return float(obj)
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                return super().default(obj)
        
        output_data = [r.to_dict() for r in rectangles]
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2, cls=NumpyEncoder)
        logger.info(f"Saved {len(rectangles)} rectangles to {args.output}")
    else:
        # Print to console
        print(f"\n{'='*60}")
        print(f"Golden Rectangle Detection Results")
        print(f"{'='*60}")
        print(f"Input: {args.input}")
        print(f"Window: {args.window} minutes")
        print(f"Min Height: {args.min_height}%")
        print(f"Symbol: {args.symbol}")
        print(f"{'='*60}")
        print(f"Found {len(rectangles)} Golden Rectangles:")
        print(f"{'='*60}")
        
        for i, rect in enumerate(rectangles, 1):
            print(f"\n[{i}] {rect.box_id}")
            print(f"    Time: {rect.ts_start} -> {rect.ts_end}")
            print(f"    Price Range: [{rect.price_min:.6f}, {rect.price_max:.6f}]")
            print(f"    Height: {rect.height_pct:.2f}%")
            print(f"    Touches: {rect.touch_count}")
            print(f"    Quality: {rect.quality_score:.4f}")
        
        if not rectangles:
            print("\nNo Golden Rectangles found matching criteria.")
        
        print(f"\n{'='*60}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
