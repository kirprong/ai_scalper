"""
Tests for Exit Strategy A
"""
import pytest
from backend.execution.exit_strategy import (
    ExitStrategyA,
    ExitOrder,
    ExitType,
)


@pytest.fixture
def exit_strategy():
    """Create exit strategy instance"""
    return ExitStrategyA(price_offset=0.01)


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


class TestExitStrategyA:
    """Tests for ExitStrategyA"""
    
    def test_calculate_exit_price(self, exit_strategy):
        """Test exit price calculation"""
        box_top = 0.65
        exit_price = exit_strategy.calculate_exit_price(box_top)
        
        assert exit_price == 0.64  # 0.65 - 0.01
    
    def test_create_exit_order(self, exit_strategy, position):
        """Test creating exit order"""
        order = exit_strategy.create_exit_order(position)
        
        assert order.symbol == "BTC_TARGET"
        assert order.quantity == 1000.0
        assert order.price == 0.64  # 0.65 - 0.01
        assert order.exit_type == ExitType.LIMIT_SELL
        assert exit_strategy.has_exit_order() is True
    
    def test_update_exit_order(self, exit_strategy, position):
        """Test updating exit order"""
        # Create initial order
        exit_strategy.create_exit_order(position)
        
        # Update with new box top
        new_box_top = 0.67
        updated_order = exit_strategy.update_exit_order(new_box_top)
        
        assert updated_order is not None
        assert updated_order.price == 0.66  # 0.67 - 0.01
    
    def test_should_trigger_stop_loss_no_drop(self, exit_strategy, position):
        """Test stop loss not triggered"""
        exit_strategy.create_exit_order(position)
        
        # Price at box bottom (no drop)
        current_price = 0.55
        should_trigger = exit_strategy.should_trigger_stop_loss(current_price)
        
        assert should_trigger is False
    
    def test_should_trigger_stop_loss_small_drop(self, exit_strategy, position):
        """Test stop loss not triggered with small drop"""
        exit_strategy.create_exit_order(position)
        
        # Price dropped 10% of box height
        current_price = 0.54  # 0.01 drop (10% of 0.10 box height)
        should_trigger = exit_strategy.should_trigger_stop_loss(current_price)
        
        assert should_trigger is False
    
    def test_should_trigger_stop_loss_large_drop(self, exit_strategy, position):
        """Test stop loss triggered with large drop"""
        exit_strategy.create_exit_order(position)
        
        # Price dropped 25% of box height
        current_price = 0.525  # 0.025 drop (25% of 0.10 box height)
        should_trigger = exit_strategy.should_trigger_stop_loss(current_price)
        
        assert should_trigger is True
    
    def test_clear(self, exit_strategy, position):
        """Test clearing exit strategy"""
        exit_strategy.create_exit_order(position)
        assert exit_strategy.has_exit_order() is True
        
        exit_strategy.clear()
        assert exit_strategy.has_exit_order() is False
        assert exit_strategy.get_exit_order() is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
