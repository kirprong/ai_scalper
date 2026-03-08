"""
Tests for Paper Trading Simulator.

This module tests the paper trading simulation functionality.
"""

import pytest
import asyncio
from backend.trading import (
    PaperTradingSimulator,
    PaperTradingConfig,
    SlippageEngine,
    SlippageConfig,
    FeeCalculator,
    FeeConfig,
)


class TestSlippageEngine:
    """Test slippage calculation."""
    
    def test_slippage_buy_order(self):
        """Test slippage for buy order."""
        config = SlippageConfig(
            base_slippage_cents=0.01,
            max_slippage_cents=0.02,
            random_seed=42,
        )
        engine = SlippageEngine(config)
        
        price = 100.0
        execution_price, slippage = engine.calculate_slippage(
            price=price,
            side="buy",
            order_size=1.0,
        )
        
        # Buy order should execute at higher price
        assert execution_price > price
        assert slippage > 0
        assert slippage >= config.base_slippage_cents
        assert slippage <= config.max_slippage_cents
    
    def test_slippage_sell_order(self):
        """Test slippage for sell order."""
        config = SlippageConfig(
            base_slippage_cents=0.01,
            max_slippage_cents=0.02,
            random_seed=42,
        )
        engine = SlippageEngine(config)
        
        price = 100.0
        execution_price, slippage = engine.calculate_slippage(
            price=price,
            side="sell",
            order_size=1.0,
        )
        
        # Sell order should execute at lower price
        assert execution_price < price
        assert slippage > 0
        assert slippage >= config.base_slippage_cents
        assert slippage <= config.max_slippage_cents
    
    def test_slippage_large_order(self):
        """Test slippage for large order."""
        config = SlippageConfig(
            base_slippage_cents=0.01,
            max_slippage_cents=0.02,
            impact_factor=0.1,
            random_seed=42,
        )
        engine = SlippageEngine(config)
        
        price = 100.0
        
        # Normal order
        _, normal_slip = engine.calculate_slippage(
            price=price,
            side="buy",
            order_size=1.0,
        )
        
        # Large order (2x size)
        _, large_slip = engine.calculate_slippage(
            price=price,
            side="buy",
            order_size=2.0,
        )
        
        # Large order should have more slippage
        assert large_slip > normal_slip


class TestFeeCalculator:
    """Test fee calculation."""
    
    def test_fee_calculation(self):
        """Test basic fee calculation."""
        config = FeeConfig(
            maker_fee_pct=0.0,
            taker_fee_pct=0.0,
            gas_fee_usd=0.50,
        )
        calculator = FeeCalculator(config)
        
        price = 100.0
        quantity = 10.0
        
        result = calculator.calculate_fee(
            price=price,
            quantity=quantity,
            side="buy",
            order_type="market",
        )
        
        assert result["trade_value"] == price * quantity
        assert result["trading_fee"] == 0.0  # Polymarket has no trading fees
        assert result["network_fee"] == config.gas_fee_usd
        assert result["total_fee"] > 0
    
    def test_pnl_adjustment(self):
        """Test PnL adjustment for fees."""
        calculator = FeeCalculator()
        
        entry_price = 100.0
        exit_price = 105.0
        quantity = 10.0
        
        result = calculator.calculate_pnl_adjustment(
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
        )
        
        # Gross PnL = (105 - 100) * 10 = 50
        assert result["gross_pnl"] == 50.0
        
        # Net PnL should be less due to fees
        assert result["net_pnl"] < result["gross_pnl"]
        assert result["total_fees"] > 0


class TestPaperTradingSimulator:
    """Test paper trading simulator."""
    
    @pytest.mark.asyncio
    async def test_buy_order(self):
        """Test buy order execution."""
        config = PaperTradingConfig(
            initial_balance=10000.0,
            random_seed=42,
        )
        simulator = PaperTradingSimulator(config)
        
        result = await simulator.place_order(
            symbol="BTC-PERP",
            side="buy",
            quantity=1.0,
            price=100.0,
        )
        
        assert result["success"] is True
        assert result["symbol"] == "BTC-PERP"
        assert result["side"] == "buy"
        assert result["quantity"] == 1.0
        assert result["execution_price"] > result["expected_price"]
        assert result["slippage"] > 0
        assert result["fees"] > 0
        assert result["latency_ms"] >= config.min_latency_ms
        assert result["latency_ms"] <= config.max_latency_ms
    
    @pytest.mark.asyncio
    async def test_sell_order(self):
        """Test sell order execution."""
        config = PaperTradingConfig(
            initial_balance=10000.0,
            random_seed=42,
        )
        simulator = PaperTradingSimulator(config)
        
        # Buy first
        await simulator.place_order(
            symbol="BTC-PERP",
            side="buy",
            quantity=1.0,
            price=100.0,
        )
        
        # Then sell
        result = await simulator.place_order(
            symbol="BTC-PERP",
            side="sell",
            quantity=1.0,
            price=105.0,
        )
        
        assert result["success"] is True
        assert result["symbol"] == "BTC-PERP"
        assert result["side"] == "sell"
        assert result["execution_price"] < result["expected_price"]
    
    @pytest.mark.asyncio
    async def test_insufficient_balance(self):
        """Test order with insufficient balance."""
        config = PaperTradingConfig(
            initial_balance=100.0,
            random_seed=42,
        )
        simulator = PaperTradingSimulator(config)
        
        result = await simulator.place_order(
            symbol="BTC-PERP",
            side="buy",
            quantity=10.0,
            price=100.0,  # Total = 1000, but balance = 100
        )
        
        assert result["success"] is False
        assert "Insufficient balance" in result["error"]
    
    @pytest.mark.asyncio
    async def test_sell_without_position(self):
        """Test sell without position."""
        simulator = PaperTradingSimulator()
        
        result = await simulator.place_order(
            symbol="BTC-PERP",
            side="sell",
            quantity=1.0,
            price=100.0,
        )
        
        assert result["success"] is False
        assert "No position to sell" in result["error"]
    
    @pytest.mark.asyncio
    async def test_pnl_calculation(self):
        """Test PnL calculation with slippage and fees."""
        config = PaperTradingConfig(
            initial_balance=10000.0,
            random_seed=42,
        )
        simulator = PaperTradingSimulator(config)
        
        # Buy at 100
        await simulator.place_order(
            symbol="BTC-PERP",
            side="buy",
            quantity=1.0,
            price=100.0,
        )
        
        # Sell at 105
        await simulator.place_order(
            symbol="BTC-PERP",
            side="sell",
            quantity=1.0,
            price=105.0,
        )
        
        stats = simulator.get_stats()
        
        # Should have 1 trade
        assert stats["total_trades"] == 1
        
        # PnL should account for slippage and fees
        # Gross PnL ≈ 5, but net PnL < 5 due to costs
        assert stats["total_pnl"] < 5.0
        assert stats["total_fees"] > 0
        assert stats["total_slippage"] > 0
    
    @pytest.mark.asyncio
    async def test_latency_simulation(self):
        """Test latency simulation."""
        config = PaperTradingConfig(
            min_latency_ms=200,
            max_latency_ms=500,
            random_seed=42,
        )
        simulator = PaperTradingSimulator(config)
        
        import time
        start = time.time()
        
        await simulator.place_order(
            symbol="BTC-PERP",
            side="buy",
            quantity=1.0,
            price=100.0,
        )
        
        elapsed_ms = (time.time() - start) * 1000
        
        # Should have at least min_latency
        assert elapsed_ms >= config.min_latency_ms
    
    def test_reset(self):
        """Test simulator reset."""
        simulator = PaperTradingSimulator()
        
        # Not async, so we can't place orders in this test
        # Just test the reset method exists
        simulator.reset()
        
        stats = simulator.get_stats()
        assert stats["balance"] == simulator.config.initial_balance
        assert stats["total_trades"] == 0
        assert stats["open_positions"] == 0
