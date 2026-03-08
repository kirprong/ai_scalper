"""
Test script for TASK-026 - Evolution: Model Versioning System
"""

import sys
sys.path.insert(0, '/root/project')

from backend.evolution.model_versioning import (
    ModelVersion,
    ModelVersioningSystem,
    VersionComparison,
)
from datetime import datetime
import tempfile
import shutil
from pathlib import Path


def test_model_versioning():
    """Test complete model versioning workflow"""
    
    print("=" * 60)
    print("TASK-026: Model Versioning System Test")
    print("=" * 60)
    
    # Create temporary storage
    temp_dir = tempfile.mkdtemp()
    storage_path = Path(temp_dir) / "versions.json"
    
    try:
        # Initialize versioning system
        print("\n[1] Initializing Model Versioning System...")
        system = ModelVersioningSystem(storage_path=str(storage_path))
        print("    ✓ System initialized")
        
        # Register LSTM models
        print("\n[2] Registering LSTM model versions...")
        lstm_v1 = system.register_model(
            model_type="lstm",
            file_path="checkpoints/lstm_v1.0.0.pt",
            metrics={
                "accuracy": 0.82,
                "loss": 0.18,
                "training_samples": 10000,
                "epochs": 50,
            },
        )
        print(f"    ✓ Registered {lstm_v1.version_id} (accuracy: {lstm_v1.metrics['accuracy']:.2%})")
        
        lstm_v2 = system.register_model(
            model_type="lstm",
            file_path="checkpoints/lstm_v1.0.1.pt",
            metrics={
                "accuracy": 0.85,
                "loss": 0.15,
                "training_samples": 15000,
                "epochs": 50,
            },
        )
        print(f"    ✓ Registered {lstm_v2.version_id} (accuracy: {lstm_v2.metrics['accuracy']:.2%})")
        
        lstm_v3 = system.register_model(
            model_type="lstm",
            file_path="checkpoints/lstm_v1.0.2.pt",
            metrics={
                "accuracy": 0.87,
                "loss": 0.13,
                "training_samples": 20000,
                "epochs": 50,
            },
        )
        print(f"    ✓ Registered {lstm_v3.version_id} (accuracy: {lstm_v3.metrics['accuracy']:.2%})")
        
        # Register XGBoost models
        print("\n[3] Registering XGBoost model versions...")
        xgb_v1 = system.register_model(
            model_type="xgboost",
            file_path="checkpoints/xgb_v1.0.0.json",
            metrics={
                "accuracy": 0.88,
                "log_loss": 0.12,
                "training_samples": 12000,
            },
        )
        print(f"    ✓ Registered {xgb_v1.version_id} (accuracy: {xgb_v1.metrics['accuracy']:.2%})")
        
        xgb_v2 = system.register_model(
            model_type="xgboost",
            file_path="checkpoints/xgb_v1.0.1.json",
            metrics={
                "accuracy": 0.90,
                "log_loss": 0.10,
                "training_samples": 18000,
            },
        )
        print(f"    ✓ Registered {xgb_v2.version_id} (accuracy: {xgb_v2.metrics['accuracy']:.2%})")
        
        # Activate models
        print("\n[4] Activating models...")
        system.activate_model(lstm_v3.version_id)  # Activate latest LSTM
        print(f"    ✓ Activated LSTM {lstm_v3.version_id}")
        
        system.activate_model(xgb_v2.version_id)  # Activate latest XGBoost
        print(f"    ✓ Activated XGBoost {xgb_v2.version_id}")
        
        # Get active models
        print("\n[5] Getting active models...")
        active_lstm = system.get_active_model("lstm")
        print(f"    ✓ Active LSTM: {active_lstm.version_id} (accuracy: {active_lstm.metrics['accuracy']:.2%})")
        
        active_xgb = system.get_active_model("xgboost")
        print(f"    ✓ Active XGBoost: {active_xgb.version_id} (accuracy: {active_xgb.metrics['accuracy']:.2%})")
        
        # List versions
        print("\n[6] Listing LSTM versions...")
        lstm_versions = system.list_versions("lstm", limit=10)
        for v in lstm_versions:
            status = " [ACTIVE]" if v.is_active else ""
            print(f"    - {v.version_id}: accuracy={v.metrics['accuracy']:.2%}{status}")
        
        # Compare versions
        print("\n[7] Comparing versions...")
        comparison = system.compare_versions("lstm-v1.0.0", "lstm-v1.0.2")
        print(f"    Comparison: {comparison.version_id_1} vs {comparison.version_id_2}")
        print(f"    - Accuracy diff: {comparison.metrics_diff['accuracy']:+.2%}")
        print(f"    - Loss diff: {comparison.metrics_diff['loss']:+.2%}")
        print(f"    - Winner: {comparison.winner}")
        print(f"    - Improvement: {comparison.improvement_pct['accuracy']:+.1f}%")
        
        # Rollback
        print("\n[8] Testing rollback...")
        rollback = system.rollback_model("lstm", steps=1)
        print(f"    ✓ Rolled back to {rollback.version_id}")
        
        active_lstm = system.get_active_model("lstm")
        print(f"    ✓ Active LSTM now: {active_lstm.version_id}")
        
        # Get statistics
        print("\n[9] Getting statistics...")
        stats = system.get_statistics()
        print(f"    Total versions: {stats['total_versions']}")
        for model_type, model_stats in stats['model_types'].items():
            print(f"    {model_type}:")
            print(f"      - Count: {model_stats['count']}")
            print(f"      - Active: {model_stats['active_version']}")
            print(f"      - Latest: {model_stats['latest_version']}")
        
        # Test persistence
        print("\n[10] Testing persistence...")
        system2 = ModelVersioningSystem(storage_path=str(storage_path))
        print(f"    ✓ Loaded {len(system2.versions['lstm'])} LSTM versions")
        print(f"    ✓ Loaded {len(system2.versions['xgboost'])} XGBoost versions")
        
        active = system2.get_active_model("lstm")
        print(f"    ✓ Active LSTM after reload: {active.version_id}")
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    test_model_versioning()
"""
Test script for TASK-026 - Model Versioning System
"""

import sys
sys.path.insert(0, '/root/project')

from backend.evolution.model_versioning import (
    ModelVersioningSystem,
    ModelVersion,
    VersionComparison,
)


def test_task_026():
    """Test TASK-026 - Model Versioning System"""
    print("=" * 60)
    print("Testing TASK-026 - Model Versioning System")
    print("=" * 60)
    
    # Test 1: Create versioning system
    print("\n[TEST 1] Create versioning system")
    versioning = ModelVersioningSystem(storage_path=".temp/test_versions.json")
    print(f"  Total versions: {versioning.get_statistics()['total_versions']}")
    assert versioning.get_statistics()['total_versions'] == 0
    print("  ✓ PASSED")
    
    # Test 2: Register LSTM model
    print("\n[TEST 2] Register LSTM model")
    lstm_v1 = versioning.register_model(
        model_type="lstm",
        file_path="checkpoints/lstm_v1.pt",
        metrics={"accuracy": 0.85, "loss": 0.15},
    )
    print(f"  Version ID: {lstm_v1.version_id}")
    print(f"  Model type: {lstm_v1.model_type}")
    print(f"  Accuracy: {lstm_v1.metrics['accuracy']}")
    assert lstm_v1.version_id == "lstm-v1.0.0"
    assert lstm_v1.model_type == "lstm"
    print("  ✓ PASSED")
    
    # Test 3: Register XGBoost model
    print("\n[TEST 3] Register XGBoost model")
    xgb_v1 = versioning.register_model(
        model_type="xgboost",
        file_path="checkpoints/xgb_v1.json",
        metrics={"accuracy": 0.90, "loss": 0.10},
    )
    print(f"  Version ID: {xgb_v1.version_id}")
    assert xgb_v1.version_id == "xgboost-v1.0.0"
    print("  ✓ PASSED")
    
    # Test 4: Activate model
    print("\n[TEST 4] Activate model")
    success = versioning.activate_model("lstm-v1.0.0")
    print(f"  Activation success: {success}")
    active = versioning.get_active_model("lstm")
    print(f"  Active version: {active.version_id if active else None}")
    assert success is True
    assert active.version_id == "lstm-v1.0.0"
    print("  ✓ PASSED")
    
    # Test 5: Register new version
    print("\n[TEST 5] Register new version")
    lstm_v2 = versioning.register_model(
        model_type="lstm",
        file_path="checkpoints/lstm_v2.pt",
        metrics={"accuracy": 0.88, "loss": 0.12},
    )
    print(f"  Version ID: {lstm_v2.version_id}")
    assert lstm_v2.version_id == "lstm-v1.0.1"
    print("  ✓ PASSED")
    
    # Test 6: Compare versions
    print("\n[TEST 6] Compare versions")
    comparison = versioning.compare_versions("lstm-v1.0.0", "lstm-v1.0.1")
    print(f"  Version 1: {comparison.version_id_1}")
    print(f"  Version 2: {comparison.version_id_2}")
    print(f"  Accuracy diff: {comparison.metrics_diff.get('accuracy', 0):.2%}")
    print(f"  Winner: {comparison.winner}")
    assert comparison.winner == "lstm-v1.0.1"
    print("  ✓ PASSED")
    
    # Test 7: Rollback
    print("\n[TEST 7] Rollback")
    versioning.activate_model("lstm-v1.0.1")
    rolled_back = versioning.rollback_model("lstm", steps=1)
    print(f"  Rolled back to: {rolled_back.version_id if rolled_back else None}")
    assert rolled_back.version_id == "lstm-v1.0.0"
    print("  ✓ PASSED")
    
    # Test 8: List versions
    print("\n[TEST 8] List versions")
    versions = versioning.list_versions("lstm")
    print(f"  Version count: {len(versions)}")
    for v in versions:
        print(f"    - {v.version_id} (active: {v.is_active})")
    assert len(versions) == 2
    print("  ✓ PASSED")
    
    # Test 9: Get statistics
    print("\n[TEST 9] Get statistics")
    stats = versioning.get_statistics()
    print(f"  Total versions: {stats['total_versions']}")
    print(f"  Model types: {list(stats['model_types'].keys())}")
    assert stats['total_versions'] == 3  # 2 LSTM + 1 XGBoost
    print("  ✓ PASSED")
    
    # Test 10: Delete version
    print("\n[TEST 10] Delete version")
    # First deactivate
    versioning.activate_model("lstm-v1.0.0")
    deleted = versioning.delete_version("lstm-v1.0.1")
    print(f"  Deletion success: {deleted}")
    versions = versioning.list_versions("lstm")
    print(f"  Remaining versions: {len(versions)}")
    assert deleted is True
    assert len(versions) == 1
    print("  ✓ PASSED")
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    test_task_026()
