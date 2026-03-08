#!/usr/bin/env python3
"""
Test script for Paper Trading Simulator.

This script demonstrates paper trading functionality with:
- Slippage simulation (0.01-0.02 cents)
- Latency simulation (200-500ms)
- Fee calculation
- PnL tracking
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.trading import PaperTradingSimulator, PaperTradingConfig


async def test_paper_trading():
    """Test paper trading simulator."""
    
    print("=" * 60)
    print("Paper Trading Simulator Test")
    print("=" * 60)
    
    # Create simulator
    config = PaperTradingConfig(
        initial_balance=10000.0,
        min_latency_ms=200,
        max_latency_ms=500,
        random_seed=42,
    )
    
    simulator = PaperTradingSimulator(config)
    
    print(f"\nInitial Balance: ${config.initial_balance:.2f}")
    print(f"Latency Range: {config.min_latency_ms}-{config.max_latency_ms}ms")
    print(f"Slippage: {config.slippage_config.base_slippage_cents}-{config.slippage_config.max_slippage_cents} cents")
    
    # Test 1: Buy order
    print("\n" + "-" * 60)
    print("Test 1: Buy Order")
    print("-" * 60)
    
    result = await simulator.place_order(
        symbol="BTC-PERP",
        side="buy",
        quantity=1.0,
        price=100.0,
    )
    
    print(f"Success: {result['success']}")
    print(f"Expected Price: ${result['expected_price']:.4f}")
    print(f"Execution Price: ${result['execution_price']:.4f}")
    print(f"Slippage: ${result['slippage']:.4f}")
    print(f"Fees: ${result['fees']:.2f}")
    print(f"Latency: {result['latency_ms']}ms")
    print(f"Balance: ${result['balance']:.2f}")
    
    # Test 2: Sell order (profitable)
    print("\n" + "-" * 60)
    print("Test 2: Sell Order (Profitable)")
    print("-" * 60)
    
    result = await simulator.place_order(
        symbol="BTC-PERP",
        side="sell",
        quantity=1.0,
        price=105.0,  # 5% profit
    )
    
    print(f"Success: {result['success']}")
    print(f"Expected Price: ${result['expected_price']:.4f}")
    print(f"Execution Price: ${result['execution_price']:.4f}")
    print(f"Balance: ${result['balance']:.2f}")
    
    # Get stats
    print("\n" + "-" * 60)
    print("Trading Statistics")
    print("-" * 60)
    
    stats = simulator.get_stats()
    
    print(f"Total Trades: {stats['total_trades']}")
    print(f"Winning Trades: {stats['winning_trades']}")
    print(f"Losing Trades: {stats['losing_trades']}")
    print(f"Win Rate: {stats['win_rate']:.1f}%")
    print(f"Total PnL: ${stats['total_pnl']:.2f}")
    print(f"Total Fees: ${stats['total_fees']:.2f}")
    print(f"Total Slippage: ${stats['total_slippage']:.4f}")
    print(f"Average PnL: ${stats['avg_pnl']:.2f}")
    
    # Test 3: Multiple trades
    print("\n" + "-" * 60)
    print("Test 3: Multiple Trades")
    print("-" * 60)
    
    # Reset simulator
    simulator.reset()
    
    # Execute multiple trades
    for i in range(5):
        # Buy
        await simulator.place_order(
            symbol=f"MARKET-{i}",
            side="buy",
            quantity=1.0,
            price=100.0 + i * 10,
        )
        
        # Sell (with random profit/loss)
        profit = (i % 2) * 10 - 5  # Alternating profit/loss
        await simulator.place_order(
            symbol=f"MARKET-{i}",
            side="sell",
            quantity=1.0,
            price=100.0 + i * 10 + profit,
        )
    
    stats = simulator.get_stats()
    
    print(f"Total Trades: {stats['total_trades']}")
    print(f"Winning Trades: {stats['winning_trades']}")
    print(f"Losing Trades: {stats['losing_trades']}")
    print(f"Win Rate: {stats['win_rate']:.1f}%")
    print(f"Total PnL: ${stats['total_pnl']:.2f}")
    print(f"Total Fees: ${stats['total_fees']:.2f}")
    
    print("\n" + "=" * 60)
    print("Test Completed Successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_paper_trading())
