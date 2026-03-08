"""
Test script for TASK-021 - Exit Strategy B
"""
import sys
import asyncio
sys.path.insert(0, '/root/project')

from backend.execution.stop_loss import (
    DynamicStopLoss,
    StopLossType,
)


async def test_stop_loss():
    """Test stop loss"""
    print("=" * 60)
    print("Testing TASK-021 - Exit Strategy B (Dynamic Stop Loss)")
    print("=" * 60)
    
    # Create stop loss
    stop_loss = DynamicStopLoss(drop_threshold=0.20)
    
    # Test 1: Calculate trigger price
    print("\n[TEST 1] Calculate trigger price")
    box_bottom = 0.55
    box_height = 0.10
    trigger_price = stop_loss.calculate_trigger_price(box_bottom, box_height)
    print(f"  Box bottom: {box_bottom}")
    print(f"  Box height: {box_height}")
    print(f"  Trigger price: {trigger_price}")
    assert trigger_price == 0.53, "Trigger price should be box_bottom - (box_height * threshold)"
    print("  ✓ PASSED")
    
    # Test 2: Create stop loss order
    print("\n[TEST 2] Create stop loss order")
    position = {
        "symbol": "BTC_TARGET",
        "quantity": 1000.0,
        "entry_price": 0.55,
        "box_top": 0.65,
        "box_bottom": 0.55,
        "timestamp": 1234567890.0,
    }
    
    order = stop_loss.create_stop_loss(position)
    print(f"  Order: {order.stop_loss_type.value} {order.quantity} @ trigger {order.trigger_price}")
    assert order.symbol == "BTC_TARGET"
    assert order.quantity == 1000.0
    assert order.trigger_price == 0.53
    assert order.stop_loss_type == StopLossType.DYNAMIC
    print("  ✓ PASSED")
    
    # Test 3: Should not trigger (price above)
    print("\n[TEST 3] Should not trigger (price above)")
    current_price = 0.54
    should_trigger = stop_loss.should_trigger(current_price)
    print(f"  Current price: {current_price}")
    print(f"  Should trigger: {should_trigger}")
    assert should_trigger is False
    print("  ✓ PASSED")
    
    # Test 4: Should trigger (price at trigger)
    print("\n[TEST 4] Should trigger (price at trigger)")
    current_price = 0.53
    should_trigger = stop_loss.should_trigger(current_price)
    print(f"  Current price: {current_price}")
    print(f"  Should trigger: {should_trigger}")
    assert should_trigger is True
    print("  ✓ PASSED")
    
    # Test 5: Should trigger (price below)
    print("\n[TEST 5] Should trigger (price below)")
    current_price = 0.50
    should_trigger = stop_loss.should_trigger(current_price)
    print(f"  Current price: {current_price}")
    print(f"  Should trigger: {should_trigger}")
    assert should_trigger is True
    print("  ✓ PASSED")
    
    # Test 6: Execute stop loss
    print("\n[TEST 6] Execute stop loss")
    result = await stop_loss.execute_stop_loss()
    print(f"  Result: {result}")
    assert result["status"] == "filled"
    assert result["order_type"] == "MARKET_SELL"
    assert stop_loss.cancelled_limit_order is True
    print("  ✓ PASSED")
    
    # Test 7: Update trigger price
    print("\n[TEST 7] Update trigger price")
    stop_loss2 = DynamicStopLoss()
    stop_loss2.create_stop_loss(position)
    
    new_box_bottom = 0.56
    new_box_height = 0.09
    updated_order = stop_loss2.update_trigger_price(new_box_bottom, new_box_height)
    print(f"  New box bottom: {new_box_bottom}")
    print(f"  New box height: {new_box_height}")
    print(f"  Updated trigger: {updated_order.trigger_price}")
    assert abs(updated_order.trigger_price - 0.542) < 0.001
    print("  ✓ PASSED")
    
    # Test 8: Clear stop loss
    print("\n[TEST 8] Clear stop loss")
    stop_loss2.clear()
    print(f"  Has stop loss: {stop_loss2.has_stop_loss()}")
    assert stop_loss2.has_stop_loss() is False
    print("  ✓ PASSED")
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_stop_loss())
