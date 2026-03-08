"""
Unit tests for Basic Feature Engineering Metrics

These tests verify the feature engineering module logic using mock DataFrames.
"""

import unittest
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.features.basic_metrics import (
    FeatureConfig,
    calculate_std_dev_price,
    calculate_velocity,
    calculate_order_book_imbalance,
    calculate_taker_buy_sell_ratio,
    calculate_distance_to_target,
    calculate_features,
)


class TestFeatureConfig(unittest.TestCase):
    """Test FeatureConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = FeatureConfig()
        self.assertEqual(config.std_dev_window, 20)
        self.assertEqual(config.velocity_window, 10)
        self.assertEqual(config.default_target_price, 0.5)

    def test_custom_config(self):
        """Test custom configuration values."""
        config = FeatureConfig(
            std_dev_window=50,
            velocity_window=5,
            default_target_price=0.75
        )
        self.assertEqual(config.std_dev_window, 50)
        self.assertEqual(config.velocity_window, 5)
        self.assertEqual(config.default_target_price, 0.75)


class TestCalculateStdDevPrice(unittest.TestCase):
    """Test calculate_std_dev_price function."""

    def test_basic_calculation(self):
        """Test basic standard deviation calculation."""
        df = pd.DataFrame({"price": [100, 101, 102, 101, 100]})
        result = calculate_std_dev_price(df, window=3)
        
        # Check that result is a Series
        self.assertIsInstance(result, pd.Series)
        
        # Check length
        self.assertEqual(len(result), len(df))
        
        # First value should be NaN (no prior data for rolling window)
        self.assertTrue(np.isnan(result.iloc[0]))
        
        # Check that we get valid values after window fills
        self.assertFalse(np.isnan(result.iloc[2]))

    def test_constant_price(self):
        """Test with constant price (std should be 0)."""
        df = pd.DataFrame({"price": [100, 100, 100, 100, 100]})
        result = calculate_std_dev_price(df, window=3)
        
        # After window fills, std should be 0
        self.assertEqual(result.iloc[2], 0.0)
        self.assertEqual(result.iloc[4], 0.0)

    def test_custom_window(self):
        """Test with custom window size."""
        df = pd.DataFrame({"price": range(1, 21)})  # 1 to 20
        result = calculate_std_dev_price(df, window=10, min_periods=10)
        
        # Check length
        self.assertEqual(len(result), len(df))
        
        # First 9 values should be NaN (window not filled)
        for i in range(9):
            self.assertTrue(np.isnan(result.iloc[i]))
        
        # 10th value onwards should have values
        self.assertFalse(np.isnan(result.iloc[9]))

    def test_custom_price_column(self):
        """Test with custom price column name."""
        df = pd.DataFrame({"close": [100, 101, 102, 101, 100]})
        result = calculate_std_dev_price(df, price_column="close", window=3)
        
        self.assertEqual(len(result), len(df))

    def test_missing_column(self):
        """Test with missing price column."""
        df = pd.DataFrame({"volume": [100, 200, 300]})
        
        with self.assertRaises(ValueError) as context:
            calculate_std_dev_price(df, price_column="price")
        
        self.assertIn("not found", str(context.exception))

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame()
        
        # Should raise ValueError for missing column
        with self.assertRaises(ValueError):
            calculate_std_dev_price(df)

    def test_min_periods(self):
        """Test with min_periods parameter."""
        df = pd.DataFrame({"price": [100, 101, 102]})
        result = calculate_std_dev_price(df, window=5, min_periods=1)
        
        # With min_periods=1, we should get values even with small data
        self.assertEqual(len(result), len(df))


class TestCalculateVelocity(unittest.TestCase):
    """Test calculate_velocity function."""

    def test_basic_calculation(self):
        """Test basic velocity calculation."""
        times = [datetime(2026, 3, 8, 10, 0, i) for i in range(5)]
        df = pd.DataFrame({
            "price": [100, 101, 103, 102, 104],
            "ts": times
        })
        result = calculate_velocity(df, window=1)
        
        # Check that result is a Series
        self.assertIsInstance(result, pd.Series)
        
        # Check length
        self.assertEqual(len(result), len(df))
        
        # First value should be NaN (no prior data)
        self.assertTrue(np.isnan(result.iloc[0]))

    def test_velocity_value(self):
        """Test velocity value calculation."""
        times = [
            datetime(2026, 3, 8, 10, 0, 0),
            datetime(2026, 3, 8, 10, 0, 1),  # 1 second later
        ]
        df = pd.DataFrame({
            "price": [100.0, 102.0],  # 2 units change
            "ts": times
        })
        result = calculate_velocity(df, window=1)
        
        # Velocity should be 2 units per second
        self.assertAlmostEqual(result.iloc[1], 2.0, places=5)

    def test_negative_velocity(self):
        """Test negative velocity (price decreasing)."""
        times = [
            datetime(2026, 3, 8, 10, 0, 0),
            datetime(2026, 3, 8, 10, 0, 2),  # 2 seconds later
        ]
        df = pd.DataFrame({
            "price": [100.0, 96.0],  # -4 units change
            "ts": times
        })
        result = calculate_velocity(df, window=1)
        
        # Velocity should be -2 units per second
        self.assertAlmostEqual(result.iloc[1], -2.0, places=5)

    def test_custom_window(self):
        """Test with custom window size."""
        times = [datetime(2026, 3, 8, 10, 0, i) for i in range(10)]
        df = pd.DataFrame({
            "price": range(100, 110),
            "ts": times
        })
        result = calculate_velocity(df, window=5)
        
        # Check length
        self.assertEqual(len(result), len(df))
        
        # First 5 values should be NaN
        for i in range(5):
            self.assertTrue(np.isnan(result.iloc[i]))

    def test_missing_columns(self):
        """Test with missing columns."""
        df = pd.DataFrame({"price": [100, 101, 102]})
        
        with self.assertRaises(ValueError) as context:
            calculate_velocity(df)
        
        self.assertIn("ts", str(context.exception))

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame()
        
        # Should raise ValueError for missing column
        with self.assertRaises(ValueError):
            calculate_velocity(df)


class TestCalculateOrderBookImbalance(unittest.TestCase):
    """Test calculate_order_book_imbalance function."""

    def test_basic_calculation(self):
        """Test basic order book imbalance calculation."""
        df = pd.DataFrame({
            "bid_volume": [100, 150, 80],
            "ask_volume": [80, 100, 120]
        })
        result = calculate_order_book_imbalance(df)
        
        # Check that result is a Series
        self.assertIsInstance(result, pd.Series)
        
        # Check length
        self.assertEqual(len(result), len(df))
        
        # First row: (100-80)/(100+80) = 20/180 = 0.111...
        self.assertAlmostEqual(result.iloc[0], 0.1111, places=3)
        
        # Second row: (150-100)/(150+100) = 50/250 = 0.2
        self.assertAlmostEqual(result.iloc[1], 0.2, places=3)
        
        # Third row: (80-120)/(80+120) = -40/200 = -0.2
        self.assertAlmostEqual(result.iloc[2], -0.2, places=3)

    def test_perfect_buy_pressure(self):
        """Test with only bid volume (max buy pressure)."""
        df = pd.DataFrame({
            "bid_volume": [100, 0],
            "ask_volume": [0, 100]
        })
        result = calculate_order_book_imbalance(df)
        
        # First row: (100-0)/(100+0) = 1.0
        self.assertEqual(result.iloc[0], 1.0)
        
        # Second row: (0-100)/(0+100) = -1.0
        self.assertEqual(result.iloc[1], -1.0)

    def test_balanced_book(self):
        """Test with balanced order book."""
        df = pd.DataFrame({
            "bid_volume": [100, 50],
            "ask_volume": [100, 50]
        })
        result = calculate_order_book_imbalance(df)
        
        # Should be 0 for balanced book
        self.assertEqual(result.iloc[0], 0.0)
        self.assertEqual(result.iloc[1], 0.0)

    def test_zero_total_volume(self):
        """Test with zero total volume."""
        df = pd.DataFrame({
            "bid_volume": [0],
            "ask_volume": [0]
        })
        result = calculate_order_book_imbalance(df)
        
        # Should be NaN when total volume is 0
        self.assertTrue(np.isnan(result.iloc[0]))

    def test_custom_columns(self):
        """Test with custom column names."""
        df = pd.DataFrame({
            "bids": [100, 150],
            "asks": [80, 100]
        })
        result = calculate_order_book_imbalance(
            df,
            bid_volume_column="bids",
            ask_volume_column="asks"
        )
        
        self.assertEqual(len(result), len(df))

    def test_missing_columns(self):
        """Test with missing columns."""
        df = pd.DataFrame({"bid_volume": [100, 150]})
        
        with self.assertRaises(ValueError) as context:
            calculate_order_book_imbalance(df)
        
        self.assertIn("ask_volume", str(context.exception))

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame()
        
        # Should raise ValueError for missing column
        with self.assertRaises(ValueError):
            calculate_order_book_imbalance(df)


class TestCalculateTakerBuySellRatio(unittest.TestCase):
    """Test calculate_taker_buy_sell_ratio function."""

    def test_basic_calculation(self):
        """Test basic taker buy/sell ratio calculation."""
        df = pd.DataFrame({
            "buy_volume": [100, 150, 80],
            "sell_volume": [80, 100, 120]
        })
        result = calculate_taker_buy_sell_ratio(df)
        
        # Check that result is a Series
        self.assertIsInstance(result, pd.Series)
        
        # Check length
        self.assertEqual(len(result), len(df))
        
        # First row: 100/80 = 1.25
        self.assertAlmostEqual(result.iloc[0], 1.25, places=3)
        
        # Second row: 150/100 = 1.5
        self.assertAlmostEqual(result.iloc[1], 1.5, places=3)
        
        # Third row: 80/120 = 0.667
        self.assertAlmostEqual(result.iloc[2], 0.6667, places=3)

    def test_equal_volumes(self):
        """Test with equal buy and sell volumes."""
        df = pd.DataFrame({
            "buy_volume": [100, 50],
            "sell_volume": [100, 50]
        })
        result = calculate_taker_buy_sell_ratio(df)
        
        # Ratio should be 1.0
        self.assertEqual(result.iloc[0], 1.0)
        self.assertEqual(result.iloc[1], 1.0)

    def test_zero_sell_volume(self):
        """Test with zero sell volume."""
        df = pd.DataFrame({
            "buy_volume": [100],
            "sell_volume": [0]
        })
        result = calculate_taker_buy_sell_ratio(df)
        
        # Should be NaN when sell volume is 0
        self.assertTrue(np.isnan(result.iloc[0]))

    def test_custom_columns(self):
        """Test with custom column names."""
        df = pd.DataFrame({
            "taker_buy": [100, 150],
            "taker_sell": [80, 100]
        })
        result = calculate_taker_buy_sell_ratio(
            df,
            buy_volume_column="taker_buy",
            sell_volume_column="taker_sell"
        )
        
        self.assertEqual(len(result), len(df))

    def test_missing_columns(self):
        """Test with missing columns."""
        df = pd.DataFrame({"buy_volume": [100, 150]})
        
        with self.assertRaises(ValueError) as context:
            calculate_taker_buy_sell_ratio(df)
        
        self.assertIn("sell_volume", str(context.exception))

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame()
        
        # Should raise ValueError for missing column
        with self.assertRaises(ValueError):
            calculate_taker_buy_sell_ratio(df)


class TestCalculateDistanceToTarget(unittest.TestCase):
    """Test calculate_distance_to_target function."""

    def test_basic_calculation(self):
        """Test basic distance to target calculation."""
        df = pd.DataFrame({"price": [0.45, 0.48, 0.52]})
        result = calculate_distance_to_target(df, target_price=0.5)
        
        # Check that result is a DataFrame
        self.assertIsInstance(result, pd.DataFrame)
        
        # Check columns
        self.assertIn("distance_absolute", result.columns)
        self.assertIn("distance_percentage", result.columns)
        
        # Check length
        self.assertEqual(len(result), len(df))
        
        # First row: absolute = 0.45 - 0.5 = -0.05, percentage = -0.05/0.5 = -0.1
        self.assertAlmostEqual(result["distance_absolute"].iloc[0], -0.05, places=5)
        self.assertAlmostEqual(result["distance_percentage"].iloc[0], -0.1, places=5)
        
        # Third row: absolute = 0.52 - 0.5 = 0.02, percentage = 0.02/0.5 = 0.04
        self.assertAlmostEqual(result["distance_absolute"].iloc[2], 0.02, places=5)
        self.assertAlmostEqual(result["distance_percentage"].iloc[2], 0.04, places=5)

    def test_default_target(self):
        """Test with default target price."""
        df = pd.DataFrame({"price": [0.4, 0.5, 0.6]})
        result = calculate_distance_to_target(df)  # Uses default target of 0.5
        
        # Middle value should have 0 distance
        self.assertAlmostEqual(result["distance_absolute"].iloc[1], 0.0, places=5)

    def test_target_column(self):
        """Test with target price from column."""
        df = pd.DataFrame({
            "price": [100, 105, 110],
            "target": [105, 105, 105]
        })
        result = calculate_distance_to_target(df, target_column="target")
        
        # First row: 100 - 105 = -5
        self.assertAlmostEqual(result["distance_absolute"].iloc[0], -5.0, places=5)
        
        # Second row: 105 - 105 = 0
        self.assertAlmostEqual(result["distance_absolute"].iloc[1], 0.0, places=5)

    def test_zero_target(self):
        """Test with zero target price."""
        df = pd.DataFrame({"price": [0.1, 0.2, 0.3]})
        result = calculate_distance_to_target(df, target_price=0.0)
        
        # With scalar target of 0.0, division by zero gives inf
        # The function handles scalar targets differently
        self.assertTrue(np.isinf(result["distance_percentage"].iloc[0]) or np.isnan(result["distance_percentage"].iloc[0]))

    def test_missing_price_column(self):
        """Test with missing price column."""
        df = pd.DataFrame({"volume": [100, 200, 300]})
        
        with self.assertRaises(ValueError) as context:
            calculate_distance_to_target(df)
        
        self.assertIn("price", str(context.exception))

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame()
        
        # Should raise ValueError for missing column
        with self.assertRaises(ValueError):
            calculate_distance_to_target(df)


class TestCalculateFeatures(unittest.TestCase):
    """Test calculate_features unified function."""

    def setUp(self):
        """Set up test fixtures."""
        self.times = [datetime(2026, 3, 8, 10, 0, i) for i in range(10)]
        self.df = pd.DataFrame({
            "price": [100 + i for i in range(10)],
            "ts": self.times,
            "bid_volume": [100 + i * 5 for i in range(10)],
            "ask_volume": [80 + i * 3 for i in range(10)],
            "buy_volume": [50 + i * 2 for i in range(10)],
            "sell_volume": [40 + i for i in range(10)],
        })

    def test_basic_calculation(self):
        """Test basic feature calculation."""
        result = calculate_features(self.df)
        
        # Check that result is a DataFrame
        self.assertIsInstance(result, pd.DataFrame)
        
        # Check all expected columns
        expected_columns = [
            "std_dev_price",
            "velocity",
            "order_book_imbalance",
            "taker_buy_sell_ratio",
            "distance_absolute",
            "distance_percentage"
        ]
        for col in expected_columns:
            self.assertIn(col, result.columns)
        
        # Check length
        self.assertEqual(len(result), len(self.df))

    def test_custom_config(self):
        """Test with custom configuration."""
        config = FeatureConfig(
            std_dev_window=5,
            velocity_window=3,
            default_target_price=105.0
        )
        result = calculate_features(self.df, config=config)
        
        # Check that features are calculated
        self.assertEqual(len(result), len(self.df))
        
        # Note: min_periods=1 by default, so values are calculated even with small data
        # Check that we have valid values after window fills
        self.assertFalse(np.isnan(result["std_dev_price"].iloc[4]))

    def test_custom_target_price(self):
        """Test with custom target price."""
        result = calculate_features(self.df, target_price=105.0)
        
        # Check distance calculations
        # Price at index 5 is 105, so distance should be 0
        self.assertAlmostEqual(result["distance_absolute"].iloc[5], 0.0, places=5)

    def test_partial_data(self):
        """Test with partial data (missing some columns)."""
        df_partial = pd.DataFrame({
            "price": [100, 101, 102],
            "ts": self.times[:3]
        })
        result = calculate_features(df_partial)
        
        # Should still calculate available features
        self.assertEqual(len(result), len(df_partial))
        
        # std_dev_price and velocity should have values
        self.assertFalse(result["std_dev_price"].isna().all())
        
        # order_book_imbalance should be NaN (missing columns)
        self.assertTrue(result["order_book_imbalance"].isna().all())

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df_empty = pd.DataFrame()
        result = calculate_features(df_empty)
        
        # Should return empty DataFrame with correct columns
        self.assertEqual(len(result), 0)
        expected_columns = [
            "std_dev_price",
            "velocity",
            "order_book_imbalance",
            "taker_buy_sell_ratio",
            "distance_absolute",
            "distance_percentage"
        ]
        for col in expected_columns:
            self.assertIn(col, result.columns)

    def test_custom_column_names(self):
        """Test with custom column names."""
        df_custom = pd.DataFrame({
            "close": [100, 101, 102],
            "timestamp": self.times[:3],
            "bids": [100, 110, 120],
            "asks": [80, 90, 100],
            "taker_buy": [50, 55, 60],
            "taker_sell": [40, 45, 50],
        })
        result = calculate_features(
            df_custom,
            price_column="close",
            time_column="timestamp",
            bid_volume_column="bids",
            ask_volume_column="asks",
            buy_volume_column="taker_buy",
            sell_volume_column="taker_sell"
        )
        
        # Should calculate all features
        self.assertEqual(len(result), len(df_custom))
        self.assertFalse(result["order_book_imbalance"].isna().all())


class TestIntegration(unittest.TestCase):
    """Integration tests for feature engineering."""

    def test_realistic_market_data(self):
        """Test with realistic market data simulation."""
        # Simulate 1 minute of market data (60 seconds)
        times = [datetime(2026, 3, 8, 10, 0, i) for i in range(60)]
        
        # Simulate price movement (random walk)
        np.random.seed(42)
        price_changes = np.random.randn(60) * 0.1
        prices = 100 + np.cumsum(price_changes)
        
        # Simulate order book
        bid_volumes = 100 + np.random.randint(-20, 20, 60)
        ask_volumes = 80 + np.random.randint(-15, 15, 60)
        
        # Simulate taker volumes
        buy_volumes = 50 + np.random.randint(-10, 10, 60)
        sell_volumes = 40 + np.random.randint(-8, 8, 60)
        
        df = pd.DataFrame({
            "price": prices,
            "ts": times,
            "bid_volume": bid_volumes,
            "ask_volume": ask_volumes,
            "buy_volume": buy_volumes,
            "sell_volume": sell_volumes,
        })
        
        # Calculate features
        result = calculate_features(df, target_price=100.0)
        
        # Verify all features are calculated
        self.assertEqual(len(result), len(df))
        
        # Check that we have valid values (not all NaN)
        self.assertFalse(result["std_dev_price"].isna().all())
        self.assertFalse(result["velocity"].isna().all())
        self.assertFalse(result["order_book_imbalance"].isna().all())
        self.assertFalse(result["taker_buy_sell_ratio"].isna().all())
        self.assertFalse(result["distance_absolute"].isna().all())
        
        # Check order book imbalance is in valid range [-1, 1]
        valid_imbalance = result["order_book_imbalance"].dropna()
        self.assertTrue((valid_imbalance >= -1).all() and (valid_imbalance <= 1).all())


if __name__ == "__main__":
    unittest.main()
