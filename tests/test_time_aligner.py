"""
Unit tests for ASOF JOIN Time Aligner

These tests verify the time aligner module logic without requiring
a running ClickHouse instance.
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.sync.time_aligner import (
    TimeAligner,
    TimeDeltaStats,
    MatchedPair,
    AlignmentResult,
)


class TestTimeDeltaStats(unittest.TestCase):
    """Test TimeDeltaStats model."""
    
    def test_stats_creation(self):
        """Test creating TimeDeltaStats."""
        stats = TimeDeltaStats(
            count=100,
            mean_ms=250.5,
            median_ms=245.0,
            std_dev_ms=50.2,
            min_ms=10.0,
            max_ms=500.0,
            p25_ms=200.0,
            p75_ms=300.0,
            p95_ms=400.0,
        )
        
        self.assertEqual(stats.count, 100)
        self.assertEqual(stats.mean_ms, 250.5)
        self.assertEqual(stats.median_ms, 245.0)
    
    def test_stats_str_representation(self):
        """Test string representation of stats."""
        stats = TimeDeltaStats(
            count=10,
            mean_ms=100.0,
            median_ms=90.0,
            std_dev_ms=20.0,
            min_ms=50.0,
            max_ms=150.0,
            p25_ms=75.0,
            p75_ms=125.0,
            p95_ms=140.0,
        )
        
        stats_str = str(stats)
        self.assertIn("Matched pairs: 10", stats_str)
        self.assertIn("Mean:   100.000 ms", stats_str)
        self.assertIn("Median: 90.000 ms", stats_str)


class TestMatchedPair(unittest.TestCase):
    """Test MatchedPair model."""
    
    def test_pair_creation(self):
        """Test creating a MatchedPair."""
        poly_ts = datetime(2026, 3, 8, 10, 0, 0, 500000)
        binance_ts = datetime(2026, 3, 8, 10, 0, 0, 250000)
        
        pair = MatchedPair(
            poly_ts=poly_ts,
            binance_ts=binance_ts,
            delta_ms=250.0,
            poly_price=0.5,
            binance_price=50000.0,
            poly_volume=100.0,
            binance_volume=0.5,
            poly_side="buy",
            binance_side="sell",
        )
        
        self.assertEqual(pair.poly_ts, poly_ts)
        self.assertEqual(pair.binance_ts, binance_ts)
        self.assertEqual(pair.delta_ms, 250.0)


class TestAlignmentResult(unittest.TestCase):
    """Test AlignmentResult model."""
    
    def test_success_result(self):
        """Test successful alignment result."""
        stats = TimeDeltaStats(
            count=10,
            mean_ms=100.0,
            median_ms=90.0,
            std_dev_ms=20.0,
            min_ms=50.0,
            max_ms=150.0,
            p25_ms=75.0,
            p75_ms=125.0,
            p95_ms=140.0,
        )
        
        result = AlignmentResult(
            success=True,
            stats=stats,
            matched_pairs=10,
            unmatched_poly=5,
            unmatched_binance=100,
            time_window_ms=1000,
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.matched_pairs, 10)
        self.assertIsNotNone(result.stats)
    
    def test_failure_result(self):
        """Test failed alignment result."""
        result = AlignmentResult(
            success=False,
            error="Connection refused",
            time_window_ms=1000,
        )
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Connection refused")
        self.assertIsNone(result.stats)


class TestTimeAligner(unittest.TestCase):
    """Test TimeAligner class."""
    
    def test_init(self):
        """Test TimeAligner initialization."""
        aligner = TimeAligner(
            clickhouse_host="localhost",
            clickhouse_port="8123",
            binance_symbol="BTCUSDT",
        )
        
        self.assertEqual(aligner.clickhouse_host, "localhost")
        self.assertEqual(aligner.clickhouse_port, "8123")
        self.assertEqual(aligner.binance_symbol, "BTCUSDT")
    
    def test_build_asof_join_query(self):
        """Test ASOF JOIN query building."""
        aligner = TimeAligner()
        
        start_time = datetime(2026, 3, 8, 10, 0, 0)
        end_time = datetime(2026, 3, 8, 11, 0, 0)
        
        query = aligner._build_asof_join_query(
            start_time=start_time,
            end_time=end_time,
            time_window_ms=1000,
        )
        
        # Verify query contains key elements
        self.assertIn("ASOF LEFT JOIN", query)
        self.assertIn("source = 'polymarket'", query)
        self.assertIn("source = 'binance'", query)
        self.assertIn("symbol = 'BTCUSDT'", query)
        self.assertIn("2026-03-08 10:00:00", query)
        self.assertIn("2026-03-08 11:00:00", query)
        self.assertIn("delta_ms", query)
    
    def test_build_asof_join_query_with_limit(self):
        """Test ASOF JOIN query with limit."""
        aligner = TimeAligner()
        
        start_time = datetime(2026, 3, 8, 10, 0, 0)
        end_time = datetime(2026, 3, 8, 11, 0, 0)
        
        query = aligner._build_asof_join_query(
            start_time=start_time,
            end_time=end_time,
            time_window_ms=1000,
            limit=1000,
        )
        
        self.assertIn("LIMIT 1000", query)
    
    def test_parse_query_results(self):
        """Test parsing query results."""
        aligner = TimeAligner()
        
        # Simulate ClickHouse query result
        result_text = """2026-03-08 10:00:00.500\t2026-03-08 10:00:00.250\t250.0\t0.5\t50000.0\t100.0\t0.5\tbuy\tsell
2026-03-08 10:00:01.500\t2026-03-08 10:00:01.200\t300.0\t0.6\t50100.0\t150.0\t0.6\tsell\tbuy"""
        
        pairs = aligner._parse_query_results(result_text)
        
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0].delta_ms, 250.0)
        self.assertEqual(pairs[0].poly_price, 0.5)
        self.assertEqual(pairs[0].binance_price, 50000.0)
        self.assertEqual(pairs[0].poly_side, "buy")
        self.assertEqual(pairs[0].binance_side, "sell")
    
    def test_parse_empty_results(self):
        """Test parsing empty query results."""
        aligner = TimeAligner()
        
        pairs = aligner._parse_query_results("")
        self.assertEqual(len(pairs), 0)
        
        pairs = aligner._parse_query_results("\n\n")
        self.assertEqual(len(pairs), 0)
    
    def test_calculate_statistics(self):
        """Test statistics calculation."""
        aligner = TimeAligner()
        
        # Create sample pairs with known deltas
        base_ts = datetime(2026, 3, 8, 10, 0, 0)
        pairs = [
            MatchedPair(
                poly_ts=base_ts + timedelta(seconds=i),
                binance_ts=base_ts + timedelta(seconds=i, milliseconds=-100),
                delta_ms=100.0 + i * 10,
                poly_price=0.5,
                binance_price=50000.0,
                poly_volume=100.0,
                binance_volume=0.5,
                poly_side="buy",
                binance_side="sell",
            )
            for i in range(10)
        ]
        
        stats = aligner._calculate_statistics(pairs)
        
        self.assertEqual(stats.count, 10)
        self.assertEqual(stats.min_ms, 100.0)
        self.assertEqual(stats.max_ms, 190.0)
        # Mean should be (100 + 190) / 2 = 145
        self.assertAlmostEqual(stats.mean_ms, 145.0, places=1)
    
    def test_calculate_statistics_single_pair(self):
        """Test statistics with single pair."""
        aligner = TimeAligner()
        
        pairs = [
            MatchedPair(
                poly_ts=datetime(2026, 3, 8, 10, 0, 0),
                binance_ts=datetime(2026, 3, 8, 10, 0, 0, 250000),
                delta_ms=250.0,
                poly_price=0.5,
                binance_price=50000.0,
                poly_volume=100.0,
                binance_volume=0.5,
                poly_side="buy",
                binance_side="sell",
            )
        ]
        
        stats = aligner._calculate_statistics(pairs)
        
        self.assertEqual(stats.count, 1)
        self.assertEqual(stats.mean_ms, 250.0)
        self.assertEqual(stats.median_ms, 250.0)
        self.assertEqual(stats.std_dev_ms, 0.0)  # Single value has no std dev
    
    def test_calculate_statistics_empty_raises(self):
        """Test that empty pairs raises error."""
        aligner = TimeAligner()
        
        with self.assertRaises(ValueError) as context:
            aligner._calculate_statistics([])
        
        self.assertIn("No pairs", str(context.exception))


class TestTimeAlignerIntegration(unittest.TestCase):
    """Integration tests for TimeAligner (require mocking)."""
    
    def test_context_manager(self):
        """Test async context manager."""
        import asyncio
        
        async def test():
            async with TimeAligner() as aligner:
                self.assertIsNotNone(aligner._session)
            # Session should be closed after context
        
        asyncio.run(test())


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestTimeDeltaStats))
    suite.addTests(loader.loadTestsFromTestCase(TestMatchedPair))
    suite.addTests(loader.loadTestsFromTestCase(TestAlignmentResult))
    suite.addTests(loader.loadTestsFromTestCase(TestTimeAligner))
    suite.addTests(loader.loadTestsFromTestCase(TestTimeAlignerIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
