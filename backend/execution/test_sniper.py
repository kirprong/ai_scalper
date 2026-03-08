"""
Tests for Sniper Execution
"""
import pytest
import asyncio
from backend.execution.sniper import (
    SniperExecution,
    TradingSignal,
    Order,
    OrderType,
    OrderSide,
)


@pytest.fixture
def sniper():
    """Create sniper execution instance"""
    return SniperExecution(
        min_confidence=0.85,
        order_type=OrderType.FOK,
        position_size=100.0,
    )


@pytest.fixture
def valid_signal():
    """Create valid trading signal"""
    return TradingSignal(
        ml_status=1,
        xgb_confidence=0.90,
        lstm_probability=0.85,
        poly_lag_confirmed=True,
        box_top=0.65,
        box_bottom=0.55,
        timestamp=1234567890.0,
    )


@pytest.fixture
def invalid_signal():
    """Create invalid trading signal"""
    return TradingSignal(
        ml_status=0,  # No signal
        xgb_confidence=0.90,
        lstm_probability=0.85,
        poly_lag_confirmed=True,
        box_top=0.65,
        box_bottom=0.55,
        timestamp=1234567890.0,
    )


@pytest.fixture
def low_confidence_signal():
    """Create signal with low confidence"""
    return TradingSignal(
        ml_status=1,
        xgb_confidence=0.75,  # Below threshold
        lstm_probability=0.85,
        poly_lag_confirmed=True,
        box_top=0.65,
        box_bottom=0.55,
        timestamp=1234567890.0,
    )


class TestTradingSignal:
    """Tests for TradingSignal"""
    
    def test_valid_signal(self, valid_signal):
        """Test valid signal"""
        assert valid_signal.is_valid() is True
    
    def test_invalid_signal(self, invalid_signal):
        """Test invalid signal"""
        assert invalid_signal.is_valid() is False
    
    def test_low_confidence_signal(self, low_confidence_signal):
        """Test low confidence signal"""
        assert low_confidence_signal.is_valid() is False


class TestOrder:
    """Tests for Order"""
    
    def test_order_creation(self):
        """Test order creation"""
        order = Order(
            symbol="BTC_TARGET",
            side=OrderSide.BUY,
            order_type=OrderType.FOK,
            quantity=100.0,
            price=0.55,
        )
        
        assert order.symbol == "BTC_TARGET"
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.FOK
        assert order.quantity == 100.0
        assert order.price == 0.55
        assert order.status == "pending"
    
    def test_order_to_polymarket_format(self):
        """Test order conversion to Polymarket format"""
        order = Order(
            symbol="BTC_TARGET",
            side=OrderSide.BUY,
            order_type=OrderType.FOK,
            quantity=100.0,
            price=0.55,
        )
        
        result = order.to_polymarket_format()
        
        assert result["symbol"] == "BTC_TARGET"
        assert result["side"] == "BUY"
        assert result["type"] == "FOK"
        assert result["quantity"] == 100.0
        assert result["price"] == 0.55


class TestSniperExecution:
    """Tests for SniperExecution"""
    
    @pytest.mark.asyncio
    async def test_evaluate_valid_signal(self, sniper, valid_signal):
        """Test evaluating valid signal"""
        result = await sniper.evaluate_signal(valid_signal)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_evaluate_invalid_signal(self, sniper, invalid_signal):
        """Test evaluating invalid signal"""
        result = await sniper.evaluate_signal(invalid_signal)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_evaluate_low_confidence_signal(self, sniper, low_confidence_signal):
        """Test evaluating low confidence signal"""
        result = await sniper.evaluate_signal(low_confidence_signal)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_create_order(self, sniper, valid_signal):
        """Test creating order from signal"""
        order = await sniper.create_order(valid_signal, "BTC_TARGET")
        
        assert order.symbol == "BTC_TARGET"
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.FOK
        assert order.quantity > 0
        assert order.price == valid_signal.box_bottom
    
    @pytest.mark.asyncio
    async def test_send_order(self, sniper):
        """Test sending order"""
        order = Order(
            symbol="BTC_TARGET",
            side=OrderSide.BUY,
            order_type=OrderType.FOK,
            quantity=100.0,
            price=0.55,
        )
        
        result = await sniper.send_order(order)
        
        assert result["status"] == "filled"
        assert result["filled_quantity"] == 100.0
        assert order.order_id is not None
    
    @pytest.mark.asyncio
    async def test_execute_valid_signal(self, sniper, valid_signal):
        """Test executing valid signal"""
        result = await sniper.execute_signal(valid_signal, "BTC_TARGET")
        
        assert result is not None
        assert result["status"] == "filled"
        assert sniper.has_position() is True
    
    @pytest.mark.asyncio
    async def test_execute_invalid_signal(self, sniper, invalid_signal):
        """Test executing invalid signal"""
        result = await sniper.execute_signal(invalid_signal, "BTC_TARGET")
        
        assert result is None
        assert sniper.has_position() is False
    
    @pytest.mark.asyncio
    async def test_position_management(self, sniper, valid_signal):
        """Test position management"""
        # Execute signal
        await sniper.execute_signal(valid_signal, "BTC_TARGET")
        
        # Check position
        position = sniper.get_position()
        assert position is not None
        assert position["symbol"] == "BTC_TARGET"
        assert position["quantity"] > 0
        
        # Close position
        result = await sniper.close_position()
        assert result is not None
        assert sniper.has_position() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
