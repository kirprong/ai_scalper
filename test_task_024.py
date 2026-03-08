"""
Test script for TASK-024 - Telemetry Calculation Block
"""
import sys
sys.path.insert(0, '/root/project')

from backend.telemetry.metrics import (
    TelemetryCalculator,
    TelemetryMetrics,
)


def test_telemetry():
    """Test telemetry calculation"""
    print("=" * 60)
    print("Testing TASK-024 - Telemetry Calculation Block")
    print("=" * 60)
    
    # Create calculator
    calculator = TelemetryCalculator(ocr_threshold=0.70, min_trades=10)
    
    # Test 1: Calculate OCR
    print("\n[TEST 1] Calculate OCR")
    ocr = calculator.calculate_ocr(5, 3)
    print(f"  OCR: {ocr:.2%}")
    assert ocr == 0.60
    print("  ✓ PASSED")
    
    # Test 2: Calculate edge per trade
    print("\n[TEST 2] Calculate edge per trade")
    trades = [
        {"id": 1, "pnl": 100.0, "duration": 60},
        {"id": 2, "pnl": -50.0, "duration": 120},
        {"id": 3, "pnl": 150.0, "duration": 90},
        {"id": 4, "pnl": 75.0, "duration": 45},
        {"id": 5, "pnl": -25.0, "duration": 180},
    ]
    edge = calculator.calculate_edge_per_trade(trades)
    print(f"  Edge per trade: ${edge:.2f}")
    assert edge == 50.0
    print("  ✓ PASSED")
    
    # Test 3: Calculate box stability
    print("\n[TEST 3] Calculate box stability")
    boxes = [
        {"id": 1, "duration": 900},
        {"id": 2, "duration": 920},
        {"id": 3, "duration": 880},
        {"id": 4, "duration": 910},
        {"id": 5, "duration": 890},
    ]
    stability = calculator.calculate_box_stability(boxes)
    print(f"  Box stability: {stability:.2%}")
    assert stability > 0.9
    print("  ✓ PASSED")
    
    # Test 4: Calculate all metrics
    print("\n[TEST 4] Calculate all metrics")
    calculator2 = TelemetryCalculator(ocr_threshold=0.70)
    opportunities = [
        {"id": 1, "captured": True},
        {"id": 2, "captured": True},
        {"id": 3, "captured": False},
        {"id": 4, "captured": True},
        {"id": 5, "captured": False},
    ]
    metrics = calculator2.calculate_all(opportunities, trades, boxes)
    
    print(f"  OCR: {metrics.opportunity_capture_rate:.2%}")
    print(f"  Edge per trade: ${metrics.edge_per_trade:.2f}")
    print(f"  Box stability: {metrics.box_stability:.2%}")
    print(f"  Total opportunities: {metrics.total_opportunities}")
    print(f"  Captured opportunities: {metrics.captured_opportunities}")
    print(f"  Total trades: {metrics.total_trades}")
    print(f"  Winning trades: {metrics.winning_trades}")
    print(f"  Total PnL: ${metrics.total_pnl:.2f}")
    
    assert metrics.opportunity_capture_rate == 0.60
    assert metrics.edge_per_trade == 50.0
    assert metrics.total_trades == 5
    print("  ✓ PASSED")
    
    # Test 5: OCR health check
    print("\n[TEST 5] OCR health check")
    print(f"  OCR: {metrics.opportunity_capture_rate:.2%}")
    print(f"  Threshold: 70%")
    print(f"  Is healthy: {calculator2.is_ocr_healthy()}")
    assert calculator2.is_ocr_healthy() is False  # 60% < 70%
    print("  ✓ PASSED")
    
    # Test 6: Get summary
    print("\n[TEST 6] Get summary")
    summary = calculator2.get_summary()
    print(f"  Summary keys: {list(summary.keys())}")
    assert "opportunity_capture_rate" in summary
    assert "edge_per_trade" in summary
    assert "box_stability" in summary
    assert "ocr_healthy" in summary
    print("  ✓ PASSED")
    
    # Test 7: Print summary
    print("\n[TEST 7] Print summary")
    calculator2.print_summary()
    print("  ✓ PASSED")
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    test_telemetry()
