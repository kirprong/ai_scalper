"""
Test script for TASK-019 - Sniper Execution
"""
import asyncio
import sys
sys.path.insert(0, '/root/project')

from backend.execution.sniper import (
    SniperExecution,
    TradingSignal,
    OrderType,
)


async def test_sniper():
    """Test sniper execution"""
    print("=" * 60)
    print("Testing TASK-019 - Sniper Execution")
    print("=" * 60)
    
    # Create sniper
    sniper = SniperExecution(
        min_confidence=0.85,
        order_type=OrderType.FOK,
        position_size=100.0,
    )
    
    # Test 1: Valid signal
    print("\n[TEST 1] Valid signal")
    valid_signal = TradingSignal(
        ml_status=1,
        xgb_confidence=0.90,
        lstm_probability=0.85,
        poly_lag_confirmed=True,
        box_top=0.65,
        box_bottom=0.55,
        timestamp=1234567890.0,
    )
    
    result = await sniper.execute_signal(valid_signal, "BTC_TARGET")
    print(f"  Result: {result}")
    print(f"  Position: {sniper.get_position()}")
    assert result is not None, "Should execute valid signal"
    assert result["status"] == "filled", "Should be filled"
    print("  ✓ PASSED")
    
    # Test 2: Invalid signal (ml_status = 0)
    print("\n[TEST 2] Invalid signal (ml_status = 0)")
    sniper2 = SniperExecution()
    invalid_signal = TradingSignal(
        ml_status=0,
        xgb_confidence=0.90,
        lstm_probability=0.85,
        poly_lag_confirmed=True,
        box_top=0.65,
        box_bottom=0.55,
        timestamp=1234567890.0,
    )
    
    result = await sniper2.execute_signal(invalid_signal, "BTC_TARGET")
    print(f"  Result: {result}")
    assert result is None, "Should not execute invalid signal"
    print("  ✓ PASSED")
    
    # Test 3: Low confidence signal
    print("\n[TEST 3] Low confidence signal")
    sniper3 = SniperExecution()
    low_conf_signal = TradingSignal(
        ml_status=1,
        xgb_confidence=0.75,  # Below threshold
        lstm_probability=0.85,
        poly_lag_confirmed=True,
        box_top=0.65,
        box_bottom=0.55,
        timestamp=1234567890.0,
    )
    
    result = await sniper3.execute_signal(low_conf_signal, "BTC_TARGET")
    print(f"  Result: {result}")
    assert result is None, "Should not execute low confidence signal"
    print("  ✓ PASSED")
    
    # Test 4: Position management
    print("\n[TEST 4] Position management")
    print(f"  Has position: {sniper.has_position()}")
    assert sniper.has_position() is True, "Should have position"
    
    close_result = await sniper.close_position()
    print(f"  Close result: {close_result}")
    print(f"  Has position after close: {sniper.has_position()}")
    assert sniper.has_position() is False, "Should not have position after close"
    print("  ✓ PASSED")
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_sniper())
