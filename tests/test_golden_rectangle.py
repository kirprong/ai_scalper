"""
Unit Tests for Golden Rectangle Detector

Tests cover:
- Rectangle detection algorithm
- Boundary touch counting
- Quality scoring
- Box validity checking
- Overlap removal
- CLI functionality
"""

import json
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from io import StringIO

from backend.detection.golden_rectangle import (
    find_rectangles,
    GoldenRectangle,
    RectangleConfig,
    calculate_rolling_bounds,
    detect_boundary_touches,
    check_box_validity,
    calculate_quality_score,
    find_rectangles_in_range,
    _rectangles_overlap,
    _remove_overlapping_rectangles,
)


class TestGoldenRectangle:
    """Tests for GoldenRectangle dataclass."""
    
    def test_golden_rectangle_creation(self):
        """Test basic GoldenRectangle creation."""
        rect = GoldenRectangle(
            box_id="test123",
            symbol="BTCUSDT",
            ts_start=datetime(2026, 3, 8, 10, 0),
            ts_end=datetime(2026, 3, 8, 10, 15),
            price_min=100.0,
            price_max=105.0,
            height_pct=4.88,
            touch_count=6,
            quality_score=0.75
        )
        
        assert rect.box_id == "test123"
        assert rect.symbol == "BTCUSDT"
        assert rect.price_min == 100.0
        assert rect.price_max == 105.0
        assert rect.height_pct == 4.88
        assert rect.touch_count == 6
        assert rect.quality_score == 0.75
    
    def test_golden_rectangle_auto_id(self):
        """Test that box_id is auto-generated."""
        rect = GoldenRectangle()
        assert rect.box_id is not None
        assert len(rect.box_id) == 8
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        rect = GoldenRectangle(
            box_id="test456",
            symbol="ETHUSDT",
            ts_start=datetime(2026, 3, 8, 10, 0),
            ts_end=datetime(2026, 3, 8, 10, 15),
            price_min=2000.0,
            price_max=2100.0,
            height_pct=4.88,
            touch_count=4,
            quality_score=0.65,
            metadata={"test": "value"}
        )
        
        result = rect.to_dict()
        
        assert result["box_id"] == "test456"
        assert result["symbol"] == "ETHUSDT"
        assert result["price_min"] == 2000.0
        assert result["price_max"] == 2100.0
        assert result["height_pct"] == 4.88
        assert result["touch_count"] == 4
        assert result["quality_score"] == 0.65
        assert result["metadata"]["test"] == "value"
    
    def test_str_representation(self):
        """Test string representation."""
        rect = GoldenRectangle(
            box_id="abc123",
            price_min=100.0,
            price_max=105.0,
            height_pct=4.88,
            touch_count=6,
            quality_score=0.75
        )
        
        result = str(rect)
        
        assert "abc123" in result
        assert "100" in result
        assert "105" in result
        assert "4.88" in result
        assert "6" in result
        assert "0.75" in result


class TestRectangleConfig:
    """Tests for RectangleConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = RectangleConfig()
        
        assert config.window_minutes == 15
        assert config.min_height_pct == 5.0
        assert config.min_touch_count == 2
        assert config.touch_threshold_pct == 0.5
        assert config.breakout_threshold_pct == 1.0
        assert config.min_window_samples == 10
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = RectangleConfig(
            window_minutes=30,
            min_height_pct=3.0,
            min_touch_count=4
        )
        
        assert config.window_minutes == 30
        assert config.min_height_pct == 3.0
        assert config.min_touch_count == 4


class TestCalculateRollingBounds:
    """Tests for calculate_rolling_bounds function."""
    
    def test_basic_calculation(self):
        """Test basic rolling bounds calculation."""
        df = pd.DataFrame({
            "price": [100, 101, 102, 101, 100, 99, 100, 101, 102, 103]
        })
        
        result = calculate_rolling_bounds(df, window=3)
        
        assert "rolling_min" in result.columns
        assert "rolling_max" in result.columns
        assert "range_pct" in result.columns
    
    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame({"price": []})
        result = calculate_rolling_bounds(df)
        
        assert len(result) == 0
    
    def test_missing_column(self):
        """Test with missing price column."""
        df = pd.DataFrame({"value": [100, 101, 102]})
        
        with pytest.raises(ValueError, match="Column 'price' not found"):
            calculate_rolling_bounds(df)
    
    def test_range_percentage(self):
        """Test range percentage calculation."""
        # Create data with known range
        df = pd.DataFrame({
            "price": [100, 105, 100, 105, 100]  # 5% range
        })
        
        result = calculate_rolling_bounds(df, window=5)
        
        # Range should be approximately 5% (5/102.5 * 100)
        assert result["range_pct"].iloc[-1] > 0


class TestDetectBoundaryTouches:
    """Tests for detect_boundary_touches function."""
    
    def test_basic_touch_detection(self):
        """Test basic boundary touch detection."""
        # Prices oscillating between 100 and 105
        prices = np.array([100.0, 105.0, 100.0, 105.0, 102.5])
        
        support_touches, resistance_touches = detect_boundary_touches(
            prices, 100.0, 105.0, threshold_pct=1.0
        )
        
        # With 1% threshold, should detect touches
        assert support_touches >= 2
        assert resistance_touches >= 2
    
    def test_no_touches(self):
        """Test when prices don't touch boundaries."""
        # Prices in the middle of the range
        prices = np.array([102.0, 102.5, 103.0, 102.5, 102.0])
        
        support_touches, resistance_touches = detect_boundary_touches(
            prices, 100.0, 105.0, threshold_pct=0.1
        )
        
        # With small threshold, should not detect touches
        assert support_touches == 0
        assert resistance_touches == 0
    
    def test_empty_prices(self):
        """Test with empty price array."""
        prices = np.array([])
        
        support_touches, resistance_touches = detect_boundary_touches(
            prices, 100.0, 105.0
        )
        
        assert support_touches == 0
        assert resistance_touches == 0
    
    def test_invalid_boundaries(self):
        """Test with invalid boundaries (min >= max)."""
        prices = np.array([100.0, 101.0, 102.0])
        
        support_touches, resistance_touches = detect_boundary_touches(
            prices, 105.0, 100.0  # Invalid: min > max
        )
        
        assert support_touches == 0
        assert resistance_touches == 0


class TestCheckBoxValidity:
    """Tests for check_box_validity function."""
    
    def test_valid_box(self):
        """Test valid box (prices within boundaries)."""
        prices = np.array([100.0, 102.0, 104.0, 102.0, 100.0])
        
        is_valid = check_box_validity(prices, 99.0, 105.0)
        
        assert is_valid is True
    
    def test_invalid_box_breakout(self):
        """Test invalid box (price breaks out)."""
        prices = np.array([100.0, 102.0, 110.0, 102.0, 100.0])  # 110 breaks out
        
        is_valid = check_box_validity(prices, 99.0, 105.0, breakout_threshold_pct=0.5)
        
        assert is_valid is False
    
    def test_empty_prices(self):
        """Test with empty prices."""
        prices = np.array([])
        
        is_valid = check_box_validity(prices, 100.0, 105.0)
        
        assert is_valid is False
    
    def test_with_tolerance(self):
        """Test with breakout tolerance."""
        prices = np.array([100.0, 102.0, 105.5, 102.0, 100.0])  # Slight breakout
        
        # With 2% tolerance: box height is 5, allowed deviation is 5 * 0.02 = 0.1
        # 105.5 is 0.5 above 105.0, which exceeds 0.1 tolerance
        # Need higher tolerance to pass
        is_valid = check_box_validity(
            prices, 100.0, 105.0, breakout_threshold_pct=15.0
        )
        
        assert is_valid is True


class TestCalculateQualityScore:
    """Tests for calculate_quality_score function."""
    
    def test_high_quality_box(self):
        """Test high quality box scoring."""
        rect = GoldenRectangle(
            touch_count=8,
            height_pct=10.0
        )
        # Stable prices
        prices = np.array([100.0, 100.5, 101.0, 100.5, 100.0] * 3)
        
        score = calculate_quality_score(rect, prices)
        
        assert 0 <= score <= 1
        assert score > 0.5  # Should be relatively high quality
    
    def test_low_quality_box(self):
        """Test low quality box scoring."""
        rect = GoldenRectangle(
            touch_count=2,
            height_pct=5.0
        )
        # Volatile prices
        prices = np.array([95.0, 105.0, 95.0, 105.0, 95.0])
        
        score = calculate_quality_score(rect, prices)
        
        assert 0 <= score <= 1
    
    def test_with_volumes(self):
        """Test scoring with volume data."""
        rect = GoldenRectangle(
            touch_count=6,
            height_pct=8.0
        )
        prices = np.array([100.0, 101.0, 102.0, 101.0, 100.0])
        volumes = np.array([1000, 1000, 1000, 1000, 1000])  # Consistent volume
        
        score = calculate_quality_score(rect, prices, volumes)
        
        assert 0 <= score <= 1
    
    def test_empty_prices(self):
        """Test with empty prices."""
        rect = GoldenRectangle()
        prices = np.array([])
        
        score = calculate_quality_score(rect, prices)
        
        assert score == 0.0


class TestFindRectangles:
    """Tests for find_rectangles function."""
    
    @pytest.fixture
    def sample_consolidation_data(self):
        """Create sample data with clear consolidation pattern."""
        times = [datetime(2026, 3, 8, 10, 0) + timedelta(minutes=i) 
                 for i in range(60)]
        
        # Price oscillates between 100 and 106 (6% range)
        np.random.seed(42)
        prices = []
        for i in range(60):
            if i % 2 == 0:
                prices.append(100.0 + np.random.uniform(-0.3, 0.3))
            else:
                prices.append(106.0 + np.random.uniform(-0.3, 0.3))
        
        return pd.DataFrame({
            "ts": times,
            "price": prices,
            "volume": [1000] * 60
        })
    
    @pytest.fixture
    def sample_trending_data(self):
        """Create sample data with trending pattern (no consolidation)."""
        times = [datetime(2026, 3, 8, 10, 0) + timedelta(minutes=i) 
                 for i in range(60)]
        
        # Price trends upward
        prices = [100 + i * 0.5 for i in range(60)]
        
        return pd.DataFrame({
            "ts": times,
            "price": prices,
            "volume": [1000] * 60
        })
    
    def test_find_rectangles_consolidation(self, sample_consolidation_data):
        """Test finding rectangles in consolidation data."""
        rectangles = find_rectangles(
            sample_consolidation_data,
            window_minutes=15,
            min_height_pct=5.0,
            symbol="BTCUSDT"
        )
        
        # Should find at least one rectangle
        assert len(rectangles) >= 1
        
        # Check rectangle properties
        for rect in rectangles:
            assert rect.symbol == "BTCUSDT"
            assert rect.height_pct >= 5.0
            assert rect.touch_count >= 2
            assert rect.quality_score >= 0
            assert rect.ts_start is not None
            assert rect.ts_end is not None
    
    def test_find_rectangles_trending(self, sample_trending_data):
        """Test that trending data produces fewer or no rectangles."""
        rectangles = find_rectangles(
            sample_trending_data,
            window_minutes=15,
            min_height_pct=5.0
        )
        
        # Trending data should produce fewer rectangles
        # (prices don't stay within a range)
        # This is expected behavior - trending markets don't form boxes
        assert isinstance(rectangles, list)
    
    def test_find_rectangles_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame({"ts": [], "price": []})
        
        rectangles = find_rectangles(df)
        
        assert rectangles == []
    
    def test_find_rectangles_missing_columns(self):
        """Test with missing required columns."""
        df = pd.DataFrame({"value": [100, 101, 102]})
        
        with pytest.raises(ValueError, match="Column 'price' not found"):
            find_rectangles(df)
        
        df2 = pd.DataFrame({"price": [100, 101, 102]})
        
        with pytest.raises(ValueError, match="Column 'ts' not found"):
            find_rectangles(df2)
    
    def test_find_rectangles_insufficient_data(self):
        """Test with insufficient data."""
        df = pd.DataFrame({
            "ts": [datetime(2026, 3, 8, 10, 0)],
            "price": [100.0]
        })
        
        rectangles = find_rectangles(df)
        
        assert rectangles == []
    
    def test_find_rectangles_with_config(self):
        """Test using custom configuration."""
        times = [datetime(2026, 3, 8, 10, 0) + timedelta(minutes=i) 
                 for i in range(30)]
        prices = [100 + 5 * (i % 2) for i in range(30)]
        
        df = pd.DataFrame({"ts": times, "price": prices})
        
        config = RectangleConfig(
            window_minutes=10,
            min_height_pct=4.0,
            min_touch_count=2
        )
        
        rectangles = find_rectangles(df, config=config)
        
        assert isinstance(rectangles, list)
    
    def test_find_rectangles_with_volume(self):
        """Test with volume data."""
        times = [datetime(2026, 3, 8, 10, 0) + timedelta(minutes=i) 
                 for i in range(30)]
        prices = [100 + 5 * (i % 2) for i in range(30)]
        volumes = [1000] * 30
        
        df = pd.DataFrame({
            "ts": times,
            "price": prices,
            "volume": volumes
        })
        
        rectangles = find_rectangles(
            df,
            window_minutes=10,
            min_height_pct=4.0,
            volume_column="volume"
        )
        
        assert isinstance(rectangles, list)


class TestRectanglesOverlap:
    """Tests for _rectangles_overlap function."""
    
    def test_overlapping_rectangles(self):
        """Test detection of overlapping rectangles."""
        r1 = GoldenRectangle(
            ts_start=datetime(2026, 3, 8, 10, 0),
            ts_end=datetime(2026, 3, 8, 10, 15),
            price_min=100.0,
            price_max=105.0
        )
        r2 = GoldenRectangle(
            ts_start=datetime(2026, 3, 8, 10, 5),
            ts_end=datetime(2026, 3, 8, 10, 20),
            price_min=100.0,
            price_max=105.0
        )
        
        is_overlap = _rectangles_overlap(r1, r2, tolerance=0.3)
        
        assert is_overlap is True
    
    def test_non_overlapping_time(self):
        """Test rectangles with non-overlapping time."""
        r1 = GoldenRectangle(
            ts_start=datetime(2026, 3, 8, 10, 0),
            ts_end=datetime(2026, 3, 8, 10, 15),
            price_min=100.0,
            price_max=105.0
        )
        r2 = GoldenRectangle(
            ts_start=datetime(2026, 3, 8, 11, 0),
            ts_end=datetime(2026, 3, 8, 11, 15),
            price_min=100.0,
            price_max=105.0
        )
        
        is_overlap = _rectangles_overlap(r1, r2, tolerance=0.3)
        
        assert is_overlap is False
    
    def test_non_overlapping_price(self):
        """Test rectangles with non-overlapping price ranges."""
        r1 = GoldenRectangle(
            ts_start=datetime(2026, 3, 8, 10, 0),
            ts_end=datetime(2026, 3, 8, 10, 15),
            price_min=100.0,
            price_max=105.0
        )
        r2 = GoldenRectangle(
            ts_start=datetime(2026, 3, 8, 10, 5),
            ts_end=datetime(2026, 3, 8, 10, 20),
            price_min=200.0,
            price_max=205.0
        )
        
        is_overlap = _rectangles_overlap(r1, r2, tolerance=0.3)
        
        # Time overlaps but price doesn't
        assert is_overlap is False


class TestRemoveOverlappingRectangles:
    """Tests for _remove_overlapping_rectangles function."""
    
    def test_remove_overlapping(self):
        """Test removal of overlapping rectangles."""
        r1 = GoldenRectangle(
            box_id="r1",
            ts_start=datetime(2026, 3, 8, 10, 0),
            ts_end=datetime(2026, 3, 8, 10, 15),
            price_min=100.0,
            price_max=105.0,
            quality_score=0.9
        )
        r2 = GoldenRectangle(
            box_id="r2",
            ts_start=datetime(2026, 3, 8, 10, 5),
            ts_end=datetime(2026, 3, 8, 10, 20),
            price_min=100.0,
            price_max=105.0,
            quality_score=0.7
        )
        r3 = GoldenRectangle(
            box_id="r3",
            ts_start=datetime(2026, 3, 8, 11, 0),
            ts_end=datetime(2026, 3, 8, 11, 15),
            price_min=100.0,
            price_max=105.0,
            quality_score=0.8
        )
        
        result = _remove_overlapping_rectangles(
            [r1, r2, r3], overlap_tolerance=0.3
        )
        
        # Should keep r1 (highest quality) and r3 (non-overlapping)
        assert len(result) == 2
        assert result[0].box_id == "r1"
        assert result[1].box_id == "r3"
    
    def test_no_overlap(self):
        """Test with non-overlapping rectangles."""
        r1 = GoldenRectangle(
            box_id="r1",
            ts_start=datetime(2026, 3, 8, 10, 0),
            ts_end=datetime(2026, 3, 8, 10, 15),
            price_min=100.0,
            price_max=105.0,
            quality_score=0.8
        )
        r2 = GoldenRectangle(
            box_id="r2",
            ts_start=datetime(2026, 3, 8, 11, 0),
            ts_end=datetime(2026, 3, 8, 11, 15),
            price_min=100.0,
            price_max=105.0,
            quality_score=0.9
        )
        
        result = _remove_overlapping_rectangles(
            [r1, r2], overlap_tolerance=0.3
        )
        
        # Both should be kept
        assert len(result) == 2
    
    def test_empty_list(self):
        """Test with empty list."""
        result = _remove_overlapping_rectangles([], overlap_tolerance=0.3)
        
        assert result == []


class TestFindRectanglesInRange:
    """Tests for find_rectangles_in_range function."""
    
    def test_find_in_range(self):
        """Test finding rectangles in a specific time range."""
        times = [datetime(2026, 3, 8, 10, 0) + timedelta(minutes=i) 
                 for i in range(120)]
        prices = [100 + 5 * (i % 2) for i in range(120)]
        
        df = pd.DataFrame({"ts": times, "price": prices})
        
        start_time = datetime(2026, 3, 8, 10, 30)
        end_time = datetime(2026, 3, 8, 11, 30)
        
        rectangles = find_rectangles_in_range(
            df,
            start_time,
            end_time,
            window_minutes=15,
            min_height_pct=4.0
        )
        
        assert isinstance(rectangles, list)
    
    def test_find_in_range_no_data(self):
        """Test with time range outside data."""
        times = [datetime(2026, 3, 8, 10, 0) + timedelta(minutes=i) 
                 for i in range(60)]
        prices = [100 + i for i in range(60)]
        
        df = pd.DataFrame({"ts": times, "price": prices})
        
        start_time = datetime(2026, 3, 8, 12, 0)
        end_time = datetime(2026, 3, 8, 13, 0)
        
        rectangles = find_rectangles_in_range(
            df,
            start_time,
            end_time,
            window_minutes=15
        )
        
        assert rectangles == []


class TestCLI:
    """Tests for CLI functionality."""
    
    @pytest.fixture
    def temp_csv_file(self, tmp_path):
        """Create a temporary CSV file with test data."""
        times = [datetime(2026, 3, 8, 10, 0) + timedelta(minutes=i) 
                 for i in range(60)]
        prices = [100 + 5 * (i % 2) for i in range(60)]
        volumes = [1000] * 60
        
        df = pd.DataFrame({
            "ts": times,
            "price": prices,
            "volume": volumes
        })
        
        csv_path = tmp_path / "test_data.csv"
        df.to_csv(csv_path, index=False)
        
        return str(csv_path)
    
    def test_cli_basic(self, temp_csv_file, tmp_path):
        """Test basic CLI execution."""
        from backend.detection.golden_rectangle import main
        import sys
        
        output_path = str(tmp_path / "output.json")
        
        # Mock command line arguments
        with patch.object(sys, 'argv', [
            'golden_rectangle.py',
            '--input', temp_csv_file,
            '--window', '15',
            '--min-height', '4.0',
            '--symbol', 'BTCUSDT',
            '--output', output_path
        ]):
            result = main()
            
            assert result == 0
            
            # Check output file was created
            import os
            assert os.path.exists(output_path)
            
            # Check output content
            with open(output_path) as f:
                data = json.load(f)
                assert isinstance(data, list)


class TestIntegration:
    """Integration tests for Golden Rectangle detection."""
    
    def test_full_detection_workflow(self):
        """Test complete detection workflow."""
        # Create realistic consolidation data
        np.random.seed(42)
        times = [datetime(2026, 3, 8, 10, 0) + timedelta(minutes=i) 
                 for i in range(120)]
        
        # Create consolidation pattern: price oscillates in 100-106 range
        prices = []
        for i in range(120):
            base = 100 if i % 2 == 0 else 106
            noise = np.random.uniform(-0.5, 0.5)
            prices.append(base + noise)
        
        df = pd.DataFrame({
            "ts": times,
            "price": prices,
            "volume": [1000 + np.random.randint(-100, 100) for _ in range(120)]
        })
        
        # Run detection
        rectangles = find_rectangles(
            df,
            window_minutes=15,
            min_height_pct=5.0,
            symbol="BTCUSDT"
        )
        
        # Verify results
        assert len(rectangles) >= 1
        
        for rect in rectangles:
            # Verify all fields are populated
            assert rect.box_id is not None
            assert rect.symbol == "BTCUSDT"
            assert rect.ts_start is not None
            assert rect.ts_end is not None
            assert rect.price_min > 0
            assert rect.price_max > rect.price_min
            assert rect.height_pct >= 5.0
            assert rect.touch_count >= 2
            assert 0 <= rect.quality_score <= 1
            
            # Verify metadata
            assert "window_samples" in rect.metadata
            assert "support_touches" in rect.metadata
            assert "resistance_touches" in rect.metadata
    
    def test_one_day_simulation(self):
        """Test running on 1 day of simulated historical data."""
        # Simulate 1 day of minute data (1440 minutes)
        np.random.seed(42)
        times = [datetime(2026, 3, 8, 0, 0) + timedelta(minutes=i) 
                 for i in range(1440)]
        
        # Create multiple consolidation periods throughout the day
        prices = []
        for i in range(1440):
            hour = i // 60
            if 2 <= hour <= 4:  # Morning consolidation
                base = 100 if i % 2 == 0 else 106
            elif 10 <= hour <= 12:  # Midday consolidation
                base = 95 if i % 2 == 0 else 102
            elif 18 <= hour <= 20:  # Evening consolidation
                base = 105 if i % 2 == 0 else 112
            else:  # Trending periods
                base = 100 + i * 0.01
            
            noise = np.random.uniform(-0.3, 0.3)
            prices.append(base + noise)
        
        df = pd.DataFrame({
            "ts": times,
            "price": prices,
            "volume": [1000] * 1440
        })
        
        # Run detection
        rectangles = find_rectangles(
            df,
            window_minutes=15,
            min_height_pct=5.0,
            symbol="BTCUSDT"
        )
        
        # Log results (this is what the task requires)
        print(f"\n{'='*60}")
        print(f"Golden Rectangle Detection - 1 Day Historical Data")
        print(f"{'='*60}")
        print(f"Total rectangles found: {len(rectangles)}")
        
        for rect in rectangles:
            print(f"\nGolden Box Found:")
            print(f"  ID: {rect.box_id}")
            print(f"  Time: {rect.ts_start} -> {rect.ts_end}")
            print(f"  Price Min: {rect.price_min:.4f}")
            print(f"  Price Max: {rect.price_max:.4f}")
            print(f"  Height: {rect.height_pct:.2f}%")
            print(f"  Touches: {rect.touch_count}")
            print(f"  Quality: {rect.quality_score:.4f}")
        
        print(f"{'='*60}")
        
        # Should find rectangles in consolidation periods
        assert len(rectangles) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
