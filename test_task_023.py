"""
Test script for TASK-023 - Simulation Matrix
"""
import sys
import asyncio
sys.path.insert(0, '/root/project')

from backend.backtesting.simulation_matrix import (
    SimulationMatrix,
    SimulationConfig,
    SimulationResult,
)


async def mock_strategy(data, spread):
    """Mock strategy function"""
    # Simulate trades with different PnL based on spread
    trades = []
    for i in range(10):
        # Higher spread = lower PnL
        pnl = 100.0 - (spread * 1000) + (i * 10)
        trades.append({"pnl": pnl})
    return trades


async def mock_load_data(start, end):
    """Mock data loader"""
    return list(range(100))


async def test_simulation_matrix():
    """Test simulation matrix"""
    print("=" * 60)
    print("Testing TASK-023 - Simulation Matrix")
    print("=" * 60)
    
    # Create config
    config = SimulationConfig(
        spread_levels=[0.01, 0.02, 0.03],
        latency_ms=200,
        fee_rate=0.001,
    )
    
    # Create matrix
    matrix = SimulationMatrix(
        config=config,
        strategy_fn=mock_strategy,
        data_loader_fn=mock_load_data,
    )
    
    # Test 1: Run single simulation
    print("\n[TEST 1] Run single simulation")
    data = list(range(100))
    result = await matrix.run_simulation(0.01, data)
    
    print(f"  Spread: {result.spread_level:.2%}")
    print(f"  Total trades: {result.total_trades}")
    print(f"  Winning trades: {result.winning_trades}")
    print(f"  Total PnL: ${result.total_pnl:.2f}")
    print(f"  Win rate: {result.win_rate:.2%}")
    print(f"  Profit factor: {result.profit_factor:.2f}")
    
    assert result.total_trades == 10
    assert result.total_pnl > 0
    print("  ✓ PASSED")
    
    # Test 2: Run all simulations
    print("\n[TEST 2] Run all simulations")
    matrix2 = SimulationMatrix(
        config=config,
        strategy_fn=mock_strategy,
        data_loader_fn=mock_load_data,
    )
    
    summary = await matrix2.run_all()
    
    print(f"  Spread levels: {summary['spread_levels']}")
    print(f"  Best spread: {summary['best_spread']:.2%}")
    
    for spread, result in summary['results'].items():
        print(f"    Spread {spread:.2%}: {result['total_trades']} trades, PnL ${result['total_pnl']:.2f}")
    
    assert len(summary['results']) == 3
    assert summary['best_spread'] is not None
    print("  ✓ PASSED")
    
    # Test 3: Get result
    print("\n[TEST 3] Get result")
    result = matrix2.get_result(0.01)
    print(f"  Result for spread 0.01: {result.total_trades} trades")
    assert result is not None
    
    result = matrix2.get_result(0.05)
    print(f"  Result for spread 0.05: {result}")
    assert result is None
    print("  ✓ PASSED")
    
    # Test 4: Get all results
    print("\n[TEST 4] Get all results")
    all_results = matrix2.get_all_results()
    print(f"  Total results: {len(all_results)}")
    assert len(all_results) > 0
    print("  ✓ PASSED")
    
    # Test 5: Print summary
    print("\n[TEST 5] Print summary")
    matrix2.print_summary()
    print("  ✓ PASSED")
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_simulation_matrix())
