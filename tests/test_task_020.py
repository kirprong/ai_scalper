"""
Test script for TASK-020 - Exit Strategy A
"""
import sys
sys.path.insert(0, '/root/project')

from backend.execution.exit_strategy import (
    ExitStrategyA,
    ExitType,
)


def test_exit_strategy():
    """Test exit strategy"""
    print("=" * 60)
    print("Testing TASK-020 - Exit Strategy A")
    print("=" * 60)
    
    # Create exit strategy
    strategy = ExitStrategyA(price_offset=0.01)
    
    # Test 1: Calculate exit price
    print("\n[TEST 1] Calculate exit price")
    box_top = 0.65
    exit_price = strategy.calculate_exit_price(box_top)
    print(f"  Box top: {box_top}")
    print(f"  Exit price: {exit_price}")
    assert exit_price == 0.64, "Exit price should be box_top - offset"
    print("  ✓ PASSED")
    
    # Test 2: Create exit order
    print("\n[TEST 2] Create exit order")
    position = {
        "symbol": "BTC_TARGET",
        "quantity": 1000.0,
        "entry_price": 0.55,
        "box_top": 0.65,
        "box_bottom": 0.55,
        "timestamp": 1234567890.0,
    }
    
    order = strategy.create_exit_order(position)
    print(f"  Order: {order.exit_type.value} {order.quantity} @ {order.price}")
    assert order.symbol == "BTC_TARGET"
    assert order.quantity == 1000.0
    assert order.price == 0.64
    assert order.exit_type == ExitType.LIMIT_SELL
    print("  ✓ PASSED")
    
    # Test 3: Update exit order
    print("\n[TEST 3] Update exit order")
    new_box_top = 0.67
    updated_order = strategy.update_exit_order(new_box_top)
    print(f"  New box top: {new_box_top}")
    print(f"  Updated exit price: {updated_order.price}")
    assert updated_order.price == 0.66
    print("  ✓ PASSED")
    
    # Test 4: Stop loss not triggered
    print("\n[TEST 4] Stop loss not triggered")
    current_price = 0.55
    should_trigger = strategy.should_trigger_stop_loss(current_price)
    print(f"  Current price: {current_price}")
    print(f"  Should trigger: {should_trigger}")
    assert should_trigger is False
    print("  ✓ PASSED")
    
    # Test 5: Stop loss triggered
    print("\n[TEST 5] Stop loss triggered")
    current_price = 0.525  # 25% drop from box bottom
    should_trigger = strategy.should_trigger_stop_loss(current_price)
    print(f"  Current price: {current_price}")
    print(f"  Should trigger: {should_trigger}")
    assert should_trigger is True
    print("  ✓ PASSED")
    
    # Test 6: Clear strategy
    print("\n[TEST 6] Clear strategy")
    strategy.clear()
    print(f"  Has exit order: {strategy.has_exit_order()}")
    assert strategy.has_exit_order() is False
    print("  ✓ PASSED")
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    test_exit_strategy()
