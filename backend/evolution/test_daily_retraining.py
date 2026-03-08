"""
Tests for Daily Retraining Pipeline - TASK-025
"""

import sys
sys.path.insert(0, '/root/project')

from backend.evolution.daily_retraining import (
    DailyRetrainingConfig,
    DailyRetrainingPipeline,
    RetrainingResult,
)


def test_daily_retraining():
    """Test daily retraining pipeline"""
    print("=" * 60)
    print("Testing TASK-025 - Daily Retraining Pipeline")
    print("=" * 60)
    
    # Test 1: Create config
    print("\n[TEST 1] Create config")
    config = DailyRetrainingConfig(
        accuracy_threshold=0.75,
        retrain_window_hours=48,
    )
    print(f"  Accuracy threshold: {config.accuracy_threshold:.0%}")
    print(f"  Retrain window: {config.retrain_window_hours}h")
    assert config.accuracy_threshold == 0.75
    assert config.retrain_window_hours == 48
    print("  ✓ PASSED")
    
    # Test 2: Create pipeline
    print("\n[TEST 2] Create pipeline")
    pipeline = DailyRetrainingPipeline(config)
    status = pipeline.get_status()
    print(f"  Enabled: {status['enabled']}")
    print(f"  Retrain count: {status['retrain_count']}")
    assert status['enabled'] is True
    assert status['retrain_count'] == 0
    print("  ✓ PASSED")
    
    # Test 3: Check accuracy (good)
    print("\n[TEST 3] Check accuracy (good)")
    good_data = {
        "predictions": [1, 1, 1, 0, 0, 1, 1, 0, 1, 1],  # 9/10 correct (last one wrong)
        "actuals": [1, 1, 1, 0, 0, 1, 1, 0, 1, 0],
    }
    accuracy = pipeline.check_accuracy(good_data)
    print(f"  Accuracy: {accuracy:.2%}")
    assert accuracy == 0.90
    print("  ✓ PASSED")
    
    # Test 4: Should not retrain (accuracy OK)
    print("\n[TEST 4] Should not retrain (accuracy OK)")
    should_retrain = pipeline.should_retrain(0.80)
    print(f"  Should retrain: {should_retrain}")
    assert should_retrain is False
    print("  ✓ PASSED")
    
    # Test 5: Should retrain (accuracy low)
    print("\n[TEST 5] Should retrain (accuracy low)")
    should_retrain = pipeline.should_retrain(0.65)
    print(f"  Should retrain: {should_retrain}")
    assert should_retrain is True
    print("  ✓ PASSED")
    
    # Test 6: Trigger retraining
    print("\n[TEST 6] Trigger retraining")
    training_data = {
        "predictions": [0, 0, 0, 1, 1, 0, 0, 1, 0, 0],  # 9/10 correct
        "actuals": [0, 0, 0, 1, 1, 0, 0, 1, 0, 1],
        "features": [[1.0, 2.0] for _ in range(100)],
    }
    result = pipeline.trigger_retraining(training_data)
    print(f"  Success: {result.success}")
    print(f"  Accuracy before: {result.accuracy_before:.2%}")
    print(f"  Accuracy after: {result.accuracy_after:.2%}")
    print(f"  Training samples: {result.training_samples}")
    assert result.success is True
    assert result.accuracy_before == 0.90
    assert result.accuracy_after > result.accuracy_before
    print("  ✓ PASSED")
    
    # Test 7: Check status after retraining
    print("\n[TEST 7] Check status after retraining")
    status = pipeline.get_status()
    print(f"  Retrain count: {status['retrain_count']}")
    print(f"  Last retrain: {status['last_retrain_time']}")
    assert status['retrain_count'] == 1
    assert status['last_retrain_time'] is not None
    print("  ✓ PASSED")
    
    # Test 8: Run daily check (no retrain needed)
    print("\n[TEST 8] Run daily check (no retrain needed)")
    good_yesterday = {
        "predictions": [1, 1, 1, 0, 0, 1, 1, 0, 1, 1],
        "actuals": [1, 1, 1, 0, 0, 1, 1, 0, 1, 0],
    }
    result = pipeline.run_daily_check(good_yesterday, training_data)
    print(f"  Result: {result}")
    assert result is None  # No retraining needed
    print("  ✓ PASSED")
    
    # Test 9: Run daily check (retrain needed)
    print("\n[TEST 9] Run daily check (retrain needed)")
    bad_yesterday = {
        "predictions": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 5/10 correct
        "actuals": [1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
    }
    # Reset to allow retraining
    pipeline.reset()
    result = pipeline.run_daily_check(bad_yesterday, training_data)
    print(f"  Result success: {result.success if result else None}")
    assert result is not None
    assert result.success is True
    print("  ✓ PASSED")
    
    # Test 10: Reset pipeline
    print("\n[TEST 10] Reset pipeline")
    pipeline.reset()
    status = pipeline.get_status()
    print(f"  Retrain count: {status['retrain_count']}")
    print(f"  Last retrain: {status['last_retrain_time']}")
    assert status['retrain_count'] == 0
    assert status['last_retrain_time'] is None
    print("  ✓ PASSED")
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    test_daily_retraining()
