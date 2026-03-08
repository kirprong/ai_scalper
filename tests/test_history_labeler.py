"""
Tests for History Labeler Module

This module tests the automatic labeling of historical data with Golden Box tags.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from backend.labeling.history_labeler import (
    label_data_point,
    label_data_batch,
    LabelingConfig,
    LabelingResult,
    HistoryLabeler,
    ClickHouseLabelClient,
    run_labeling_pipeline,
)
from backend.detection import GoldenRectangle


class TestLabelDataPoint:
    """Tests for the label_data_point function."""
    
    def test_point_inside_rectangle(self):
        """Test labeling when point is inside a golden rectangle."""
        rect = GoldenRectangle(
            symbol="BTCUSDT",
            ts_start=datetime(2026, 1, 1, 10, 0),
            ts_end=datetime(2026, 1, 1, 10, 15),
            price_min=100.0,
            price_max=105.0
        )
        
        # Point inside rectangle
        result = label_data_point(
            ts=datetime(2026, 1, 1, 10, 5),
            price=102.0,
            rectangles=[rect]
        )
        assert result == 1
    
    def test_point_outside_rectangle_price(self):
        """Test labeling when point is outside rectangle (price)."""
        rect = GoldenRectangle(
            symbol="BTCUSDT",
            ts_start=datetime(2026, 1, 1, 10, 0),
            ts_end=datetime(2026, 1, 1, 10, 15),
            price_min=100.0,
            price_max=105.0
        )
        
        # Point outside rectangle (price too high)
        result = label_data_point(
            ts=datetime(2026, 1, 1, 10, 5),
            price=110.0,
            rectangles=[rect]
        )
        assert result == 0
    
    def test_point_outside_rectangle_time(self):
        """Test labeling when point is outside rectangle (time)."""
        rect = GoldenRectangle(
            symbol="BTCUSDT",
            ts_start=datetime(2026, 1, 1, 10, 0),
            ts_end=datetime(2026, 1, 1, 10, 15),
            price_min=100.0,
            price_max=105.0
        )
        
        # Point outside rectangle (time before)
        result = label_data_point(
            ts=datetime(2026, 1, 1, 9, 0),
            price=102.0,
            rectangles=[rect]
        )
        assert result == 0
    
    def test_point_on_boundary(self):
        """Test labeling when point is on rectangle boundary."""
        rect = GoldenRectangle(
            symbol="BTCUSDT",
            ts_start=datetime(2026, 1, 1, 10, 0),
            ts_end=datetime(2026, 1, 1, 10, 15),
            price_min=100.0,
            price_max=105.0
        )
        
        # Point on price boundary
        result = label_data_point(
            ts=datetime(2026, 1, 1, 10, 5),
            price=100.0,  # On lower boundary
            rectangles=[rect]
        )
        assert result == 1
        
        result = label_data_point(
            ts=datetime(2026, 1, 1, 10, 5),
            price=105.0,  # On upper boundary
            rectangles=[rect]
        )
        assert result == 1
    
    def test_multiple_rectangles(self):
        """Test labeling with multiple rectangles."""
        rect1 = GoldenRectangle(
            symbol="BTCUSDT",
            ts_start=datetime(2026, 1, 1, 10, 0),
            ts_end=datetime(2026, 1, 1, 10, 15),
            price_min=100.0,
            price_max=105.0
        )
        rect2 = GoldenRectangle(
            symbol="BTCUSDT",
            ts_start=datetime(2026, 1, 1, 11, 0),
            ts_end=datetime(2026, 1, 1, 11, 15),
            price_min=110.0,
            price_max=115.0
        )
        
        # Point in first rectangle
        result = label_data_point(
            ts=datetime(2026, 1, 1, 10, 5),
            price=102.0,
            rectangles=[rect1, rect2]
        )
        assert result == 1
        
        # Point in second rectangle
        result = label_data_point(
            ts=datetime(2026, 1, 1, 11, 5),
            price=112.0,
            rectangles=[rect1, rect2]
        )
        assert result == 1
        
        # Point in neither rectangle
        result = label_data_point(
            ts=datetime(2026, 1, 1, 10, 30),
            price=102.0,
            rectangles=[rect1, rect2]
        )
        assert result == 0
    
    def test_empty_rectangles(self):
        """Test labeling with no rectangles."""
        result = label_data_point(
            ts=datetime(2026, 1, 1, 10, 5),
            price=102.0,
            rectangles=[]
        )
        assert result == 0
    
    def test_rectangle_without_time_bounds(self):
        """Test labeling when rectangle has no time bounds."""
        rect = GoldenRectangle(
            symbol="BTCUSDT",
            ts_start=None,
            ts_end=None,
            price_min=100.0,
            price_max=105.0
        )
        
        # Should match on price only (time bounds check is skipped if None)
        result = label_data_point(
            ts=datetime(2026, 1, 1, 10, 5),
            price=102.0,
            rectangles=[rect]
        )
        # When time bounds are None, the time check is skipped
        # So the point matches if price is in range
        assert result == 1


class TestLabelDataBatch:
    """Tests for the label_data_batch function."""
    
    def test_batch_labeling_basic(self):
        """Test basic batch labeling."""
        # Create test data
        times = [datetime(2026, 1, 1, 10, i) for i in range(5)]
        prices = [100.0, 102.0, 104.0, 106.0, 108.0]
        df = pd.DataFrame({
            'ts': times,
            'price': prices
        })
        
        # Create rectangle covering first 3 points
        rect = GoldenRectangle(
            symbol="BTCUSDT",
            ts_start=datetime(2026, 1, 1, 10, 0),
            ts_end=datetime(2026, 1, 1, 10, 2),
            price_min=99.0,
            price_max=105.0
        )
        
        labeled_df = label_data_batch(df, [rect])
        
        assert 'is_golden_box' in labeled_df.columns
        assert labeled_df['is_golden_box'].tolist() == [1, 1, 1, 0, 0]
    
    def test_batch_labeling_empty_dataframe(self):
        """Test batch labeling with empty DataFrame."""
        df = pd.DataFrame({'ts': [], 'price': []})
        rect = GoldenRectangle(
            symbol="BTCUSDT",
            ts_start=datetime(2026, 1, 1, 10, 0),
            ts_end=datetime(2026, 1, 1, 10, 15),
            price_min=100.0,
            price_max=105.0
        )
        
        labeled_df = label_data_batch(df, [rect])
        
        # Empty DataFrame returns early without adding columns
        assert len(labeled_df) == 0
    
    def test_batch_labeling_no_rectangles(self):
        """Test batch labeling with no rectangles."""
        times = [datetime(2026, 1, 1, 10, i) for i in range(5)]
        prices = [100.0, 102.0, 104.0, 106.0, 108.0]
        df = pd.DataFrame({
            'ts': times,
            'price': prices
        })
        
        labeled_df = label_data_batch(df, [])
        
        assert 'is_golden_box' in labeled_df.columns
        assert all(labeled_df['is_golden_box'] == 0)
    
    def test_batch_labeling_overlapping_rectangles(self):
        """Test batch labeling with overlapping rectangles."""
        times = [datetime(2026, 1, 1, 10, i) for i in range(5)]
        prices = [100.0, 102.0, 104.0, 106.0, 108.0]
        df = pd.DataFrame({
            'ts': times,
            'price': prices
        })
        
        # Two overlapping rectangles
        rect1 = GoldenRectangle(
            symbol="BTCUSDT",
            ts_start=datetime(2026, 1, 1, 10, 0),
            ts_end=datetime(2026, 1, 1, 10, 2),
            price_min=99.0,
            price_max=105.0
        )
        rect2 = GoldenRectangle(
            symbol="BTCUSDT",
            ts_start=datetime(2026, 1, 1, 10, 1),
            ts_end=datetime(2026, 1, 1, 10, 4),
            price_min=101.0,
            price_max=107.0
        )
        
        labeled_df = label_data_batch(df, [rect1, rect2])
        
        # Points should be labeled 1 if in either rectangle
        assert labeled_df['is_golden_box'].tolist() == [1, 1, 1, 1, 0]
    
    def test_batch_labeling_custom_columns(self):
        """Test batch labeling with custom column names."""
        times = [datetime(2026, 1, 1, 10, i) for i in range(5)]
        prices = [100.0, 102.0, 104.0, 106.0, 108.0]
        df = pd.DataFrame({
            'timestamp': times,
            'trade_price': prices
        })
        
        rect = GoldenRectangle(
            symbol="BTCUSDT",
            ts_start=datetime(2026, 1, 1, 10, 0),
            ts_end=datetime(2026, 1, 1, 10, 2),
            price_min=99.0,
            price_max=105.0
        )
        
        labeled_df = label_data_batch(
            df, [rect],
            ts_column='timestamp',
            price_column='trade_price'
        )
        
        assert 'is_golden_box' in labeled_df.columns
        assert labeled_df['is_golden_box'].tolist() == [1, 1, 1, 0, 0]


class TestLabelingConfig:
    """Tests for LabelingConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = LabelingConfig()
        
        assert config.window_minutes == 15
        assert config.min_height_pct == 5.0
        assert config.min_touch_count == 2
        assert config.batch_size == 10000
        assert config.chunk_hours == 24
        assert config.label_column == "is_golden_box"
        assert config.use_separate_table is True
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = LabelingConfig(
            window_minutes=30,
            min_height_pct=3.0,
            batch_size=5000
        )
        
        assert config.window_minutes == 30
        assert config.min_height_pct == 3.0
        assert config.batch_size == 5000
    
    def test_config_from_env(self):
        """Test configuration from environment variables."""
        import os
        
        # Set environment variables
        os.environ['CLICKHOUSE_HOST'] = 'custom_host'
        os.environ['CLICKHOUSE_HTTP_PORT'] = '9999'
        
        config = LabelingConfig()
        
        assert config.clickhouse_host == 'custom_host'
        assert config.clickhouse_port == 9999
        
        # Clean up
        del os.environ['CLICKHOUSE_HOST']
        del os.environ['CLICKHOUSE_HTTP_PORT']


class TestLabelingResult:
    """Tests for LabelingResult dataclass."""
    
    def test_result_creation(self):
        """Test creating a labeling result."""
        result = LabelingResult(
            symbol="BTCUSDT",
            total_rows=1000,
            labeled_rows=1000,
            golden_box_rows=150,
            rectangles_found=5
        )
        
        assert result.symbol == "BTCUSDT"
        assert result.total_rows == 1000
        assert result.golden_box_rows == 150
        assert result.rectangles_found == 5
        assert result.errors == []
    
    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = LabelingResult(
            symbol="BTCUSDT",
            total_rows=1000,
            labeled_rows=1000,
            golden_box_rows=150,
            rectangles_found=5,
            start_time=datetime(2026, 1, 1),
            end_time=datetime(2026, 1, 31),
            processing_time_seconds=10.5
        )
        
        result_dict = result.to_dict()
        
        assert result_dict['symbol'] == "BTCUSDT"
        assert result_dict['total_rows'] == 1000
        assert result_dict['golden_box_rows'] == 150
        assert result_dict['rectangles_found'] == 5
        assert '2026-01-01' in result_dict['start_time']
        assert '2026-01-31' in result_dict['end_time']
        assert result_dict['processing_time_seconds'] == 10.5


class TestClickHouseLabelClient:
    """Tests for ClickHouseLabelClient class."""
    
    @patch('requests.post')
    @patch('requests.get')
    def test_ping_success(self, mock_get, mock_post):
        """Test successful ping to ClickHouse."""
        config = LabelingConfig()
        client = ClickHouseLabelClient(config)
        
        mock_get.return_value.status_code = 200
        
        assert client.ping() is True
        mock_get.assert_called_once()
    
    @patch('requests.get')
    def test_ping_failure(self, mock_get):
        """Test failed ping to ClickHouse."""
        config = LabelingConfig()
        client = ClickHouseLabelClient(config)
        
        mock_get.side_effect = Exception("Connection refused")
        
        assert client.ping() is False
    
    @patch('requests.post')
    def test_execute_query(self, mock_post):
        """Test executing a query."""
        config = LabelingConfig()
        client = ClickHouseLabelClient(config)
        
        mock_response = Mock()
        mock_response.text = "result"
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        result = client._execute("SELECT 1")
        
        assert result == "result"
        mock_post.assert_called_once()
    
    @patch('requests.post')
    def test_count_data_points(self, mock_post):
        """Test counting data points."""
        config = LabelingConfig()
        client = ClickHouseLabelClient(config)
        
        mock_response = Mock()
        mock_response.text = "42"
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        count = client.count_data_points("BTCUSDT")
        
        assert count == 42


class TestHistoryLabeler:
    """Tests for HistoryLabeler class."""
    
    def test_labeler_initialization(self):
        """Test labeler initialization."""
        config = LabelingConfig(window_minutes=30)
        labeler = HistoryLabeler(config)
        
        assert labeler.config.window_minutes == 30
        assert labeler.client is not None
    
    def test_parse_time_datetime(self):
        """Test parsing datetime input."""
        config = LabelingConfig()
        labeler = HistoryLabeler(config)
        
        dt = datetime(2026, 1, 1, 12, 0)
        result = labeler._parse_time(dt)
        
        assert result == dt
    
    def test_parse_time_string(self):
        """Test parsing string input."""
        config = LabelingConfig()
        labeler = HistoryLabeler(config)
        
        result = labeler._parse_time("2026-01-01")
        
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 1
    
    @patch.object(ClickHouseLabelClient, 'ping')
    @patch.object(ClickHouseLabelClient, 'count_data_points')
    @patch.object(ClickHouseLabelClient, 'create_labels_table')
    @patch.object(ClickHouseLabelClient, 'fetch_data_chunk')
    @patch.object(ClickHouseLabelClient, 'insert_labels')
    def test_label_symbol_dry_run(
        self, 
        mock_insert, 
        mock_fetch, 
        mock_create, 
        mock_count, 
        mock_ping
    ):
        """Test labeling in dry run mode."""
        mock_ping.return_value = True
        mock_count.return_value = 10
        mock_create.return_value = True
        
        # Create sample data
        times = [datetime(2026, 1, 1, 10, i) for i in range(10)]
        df = pd.DataFrame({
            'symbol': ['BTCUSDT'] * 10,
            'ts': times,
            'price': [100.0 + i for i in range(10)],
            'volume': [1.0] * 10,
            'side': ['buy'] * 10,
            'source': ['test'] * 10
        })
        
        mock_fetch.return_value = df
        
        config = LabelingConfig()
        labeler = HistoryLabeler(config)
        
        result = labeler.label_symbol(
            symbol="BTCUSDT",
            start_time="2026-01-01",
            end_time="2026-01-02",
            dry_run=True
        )
        
        assert result.symbol == "BTCUSDT"
        assert result.total_rows == 10
        # In dry run, insert should not be called
        mock_insert.assert_not_called()


class TestRunLabelingPipeline:
    """Tests for run_labeling_pipeline function."""
    
    @patch.object(HistoryLabeler, 'label_symbol')
    def test_pipeline_execution(self, mock_label):
        """Test pipeline execution."""
        mock_result = LabelingResult(
            symbol="BTCUSDT",
            total_rows=100,
            golden_box_rows=20,
            rectangles_found=3
        )
        mock_label.return_value = mock_result
        
        result = run_labeling_pipeline(
            symbol="BTCUSDT",
            start_time="2026-01-01",
            end_time="2026-01-31"
        )
        
        assert result.symbol == "BTCUSDT"
        assert result.total_rows == 100
        mock_label.assert_called_once()


class TestIntegration:
    """Integration tests for the labeling module."""
    
    def test_full_labeling_workflow(self):
        """Test the full labeling workflow with synthetic data."""
        # Create synthetic data that will form a golden rectangle
        np.random.seed(42)
        
        # Create data with consolidation between 100-105
        times = [datetime(2026, 1, 1, 10, i) for i in range(30)]
        # Price oscillates between 100 and 105
        prices = [100 + 5 * (i % 2) + np.random.uniform(-0.5, 0.5) for i in range(30)]
        
        df = pd.DataFrame({
            'ts': times,
            'price': prices,
            'volume': [1.0] * 30
        })
        
        # Detect rectangles
        from backend.detection import find_rectangles, RectangleConfig
        
        config = RectangleConfig(
            window_minutes=15,
            min_height_pct=4.0,
            min_touch_count=2
        )
        
        rectangles = find_rectangles(
            df=df,
            window_minutes=15,
            min_height_pct=4.0,
            symbol="TEST",
            config=config
        )
        
        # Label the data
        labeled_df = label_data_batch(df, rectangles)
        
        # Verify labeling
        assert 'is_golden_box' in labeled_df.columns
        
        # If rectangles were found, some points should be labeled
        if rectangles:
            assert labeled_df['is_golden_box'].sum() > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
