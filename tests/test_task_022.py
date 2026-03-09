"""
Test script for TASK-022 - Walk-Forward Optimization Engine
"""
import sys
import asyncio
from datetime import datetime, timedelta
sys.path.insert(0, '/root/project')

from backend.backtesting.walk_forward import (
    WalkForwardOptimizer,
    WFOConfig,
    WFOPeriod,
)


async def mock_train(data):
    """Mock training function"""
    await asyncio.sleep(0.01)
    return 0.85  # 85% accuracy


async def mock_test(data):
    """Mock test function"""
    await asyncio.sleep(0.01)
    return 0.80, 100.0  # 80% accuracy, $100 PnL


async def mock_load_data(start, end):
    """Mock data loader"""
    await asyncio.sleep(0.01)
    days = (end - start).days
    return list(range(days * 100))  # 100 samples per day


async def test_walk_forward():
    """Test walk-forward optimization"""
    print("=" * 60)
    print("Testing TASK-022 - Walk-Forward Optimization Engine")
    print("=" * 60)
    
    # Create config
    config = WFOConfig(
        train_days=5,
        test_days=1,
        step_days=1,
        min_train_samples=100,
        retrain_threshold=0.75,
    )
    
    # Create optimizer
    optimizer = WalkForwardOptimizer(
        config=config,
        train_fn=mock_train,
        test_fn=mock_test,
        data_loader_fn=mock_load_data,
    )
    
    # Test 1: Generate periods
    print("\n[TEST 1] Generate periods")
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 15)
    
    periods = optimizer.generate_periods(start, end)
    print(f"  Generated {len(periods)} periods")
    
    for i, period in enumerate(periods[:3]):  # Show first 3
        print(f"  Period {i}:")
        print(f"    Train: {period.train_start.date()} to {period.train_end.date()}")
        print(f"    Test:  {period.test_start.date()} to {period.test_end.date()}")
    
    assert len(periods) > 0
    print("  ✓ PASSED")
    
    # Test 2: Run single period
    print("\n[TEST 2] Run single period")
    period = WFOPeriod(
        period_id=0,
        train_start=start,
        train_end=start + timedelta(days=5),
        test_start=start + timedelta(days=5),
        test_end=start + timedelta(days=6),
    )
    
    result = await optimizer.run_period(period)
    print(f"  Status: {result.status}")
    print(f"  Train samples: {result.train_samples}")
    print(f"  Test samples: {result.test_samples}")
    print(f"  Train accuracy: {result.train_accuracy:.2%}")
    print(f"  Test accuracy: {result.test_accuracy:.2%}")
    print(f"  Test PnL: ${result.test_pnl:.2f}")
    
    assert result.status == "completed"
    assert result.train_accuracy == 0.85
    assert result.test_accuracy == 0.80
    print("  ✓ PASSED")
    
    # Test 3: Run all periods
    print("\n[TEST 3] Run all periods")
    optimizer2 = WalkForwardOptimizer(
        config=config,
        train_fn=mock_train,
        test_fn=mock_test,
        data_loader_fn=mock_load_data,
    )
    
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 10)
    
    summary = await optimizer2.run_all(start, end)
    print(f"  Total periods: {summary['total_periods']}")
    print(f"  Completed: {summary['completed_periods']}")
    print(f"  Failed: {summary['failed_periods']}")
    print(f"  Avg train accuracy: {summary['avg_train_accuracy']:.2%}")
    print(f"  Avg test accuracy: {summary['avg_test_accuracy']:.2%}")
    print(f"  Total PnL: ${summary['total_pnl']:.2f}")
    
    assert summary['completed_periods'] > 0
    print("  ✓ PASSED")
    
    # Test 4: Should retrain
    print("\n[TEST 4] Should retrain")
    should_retrain_1 = optimizer.should_retrain(0.70)
    should_retrain_2 = optimizer.should_retrain(0.75)
    should_retrain_3 = optimizer.should_retrain(0.80)
    
    print(f"  Accuracy 70%: should retrain = {should_retrain_1}")
    print(f"  Accuracy 75%: should retrain = {should_retrain_2}")
    print(f"  Accuracy 80%: should retrain = {should_retrain_3}")
    
    assert should_retrain_1 is True
    assert should_retrain_2 is False
    assert should_retrain_3 is False
    print("  ✓ PASSED")
    
    # Test 5: Get progress
    print("\n[TEST 5] Get progress")
    progress = optimizer2.get_progress()
    print(f"  Total periods: {progress['total_periods']}")
    print(f"  Completed: {progress['completed']}")
    print(f"  Failed: {progress['failed']}")
    print(f"  Is running: {progress['is_running']}")
    
    assert 'total_periods' in progress
    assert 'completed' in progress
    print("  ✓ PASSED")
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_walk_forward())
