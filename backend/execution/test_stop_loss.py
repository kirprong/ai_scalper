"""
Tests for Exit Strategy B - Dynamic Stop Loss
"""
import pytest
import asyncio
from backend.execution.stop_loss import (
    DynamicStopLoss,
    StopLossOrder,
    StopLossType,
)


@pytest.fixture
def stop_loss():
    """Create stop loss instance"""
    return DynamicStopLoss(drop_threshold=0.20)


@pytest.fixture
def position():
    """Create mock position"""
    return {
        "symbol": "BTC_TARGET",
        "quantity": 1000.0,
        "entry_price": 0.55,
        "box_top": 0.65,
        "box_bottom": 0.55,
        "timestamp": 1234567890.0,
    }


class TestDynamicStopLoss:
    """Tests for DynamicStopLoss"""
    
    def test_calculate_trigger_price(self, stop_loss):
        """Test trigger price calculation"""
        box_bottom = 0.55
        box_height = 0.10
        
        trigger_price = stop_loss.calculate_trigger_price(box_bottom, box_height)
        
        # Trigger = 0.55 - (0.10 * 0.20) = 0.55 - 0.02 = 0.53
        assert trigger_price == 0.53
    
    def test_create_stop_loss(self, stop_loss, position):
        """Test creating stop loss order"""
        order = stop_loss.create_stop_loss(position)
        
        assert order.symbol == "BTC_TARGET"
        assert order.quantity == 1000.0
        assert order.trigger_price == 0.53  # 0.55 - (0.10 * 0.20)
        assert order.stop_loss_type == StopLossType.DYNAMIC
        assert stop_loss.has_stop_loss() is True
    
    def test_should_trigger_above_price(self, stop_loss, position):
        """Test stop loss not triggered when price above trigger"""
        stop_loss.create_stop_loss(position)
        
        # Price above trigger
        current_price = 0.54
        should_trigger = stop_loss.should_trigger(current_price)
        
        assert should_trigger is False
    
    def test_should_trigger_at_trigger(self, stop_loss, position):
        """Test stop loss triggered when price at trigger"""
        stop_loss.create_stop_loss(position)
        
        # Price at trigger
        current_price = 0.53
        should_trigger = stop_loss.should_trigger(current_price)
        
        assert should_trigger is True
    
    def test_should_trigger_below_trigger(self, stop_loss, position):
        """Test stop loss triggered when price below trigger"""
        stop_loss.create_stop_loss(position)
        
        # Price below trigger
        current_price = 0.50
        should_trigger = stop_loss.should_trigger(current_price)
        
        assert should_trigger is True
    
    @pytest.mark.asyncio
    async def test_execute_stop_loss(self, stop_loss, position):
        """Test executing stop loss"""
        stop_loss.create_stop_loss(position)
        
        result = await stop_loss.execute_stop_loss()
        
        assert result["status"] == "filled"
        assert result["order_type"] == "MARKET_SELL"
        assert result["quantity"] == 1000.0
        assert stop_loss.cancelled_limit_order is True
    
    def test_update_trigger_price(self, stop_loss, position):
        """Test updating trigger price"""
        stop_loss.create_stop_loss(position)
        
        # Update with new box values
        new_box_bottom = 0.56
        new_box_height = 0.09
        
        updated_order = stop_loss.update_trigger_price(new_box_bottom, new_box_height)
        
        # New trigger = 0.56 - (0.09 * 0.20) = 0.56 - 0.018 = 0.542
        assert updated_order is not None
        assert abs(updated_order.trigger_price - 0.542) < 0.001
    
    def test_clear(self, stop_loss, position):
        """Test clearing stop loss"""
        stop_loss.create_stop_loss(position)
        assert stop_loss.has_stop_loss() is True
        
        stop_loss.clear()
        assert stop_loss.has_stop_loss() is False
        assert stop_loss.get_stop_loss_order() is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
