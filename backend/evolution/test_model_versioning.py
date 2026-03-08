"""
Tests for Model Versioning System - TASK-026
"""

import sys
sys.path.insert(0, '/root/project')

import pytest
from datetime import datetime
from pathlib import Path
import json
import tempfile
import shutil

from backend.evolution.model_versioning import (
    ModelVersion,
    ModelVersioningSystem,
    VersionComparison,
)


class TestModelVersion:
    """Test ModelVersion dataclass"""
    
    def test_model_version_creation(self):
        """Test creating a ModelVersion"""
        version = ModelVersion(
            version_id="v1.0.0",
            model_type="lstm",
            created_at=datetime.now(),
            metrics={"accuracy": 0.85, "loss": 0.15},
            file_path="checkpoints/model.pt",
            is_active=False,
        )
        
        assert version.version_id == "v1.0.0"
        assert version.model_type == "lstm"
        assert version.metrics["accuracy"] == 0.85
        assert version.is_active is False
    
    def test_model_version_to_dict(self):
        """Test converting ModelVersion to dict"""
        created_at = datetime.now()
        version = ModelVersion(
            version_id="v1.0.0",
            model_type="xgboost",
            created_at=created_at,
            metrics={"accuracy": 0.90},
            file_path="checkpoints/model.json",
            is_active=True,
        )
        
        data = version.to_dict()
        
        assert data["version_id"] == "v1.0.0"
        assert data["model_type"] == "xgboost"
        assert data["created_at"] == created_at.isoformat()
        assert data["metrics"]["accuracy"] == 0.90
        assert data["is_active"] is True
    
    def test_model_version_from_dict(self):
        """Test creating ModelVersion from dict"""
        created_at = datetime.now()
        data = {
            "version_id": "v1.0.1",
            "model_type": "lstm",
            "created_at": created_at.isoformat(),
            "metrics": {"accuracy": 0.88, "loss": 0.12},
            "file_path": "checkpoints/model_v1.0.1.pt",
            "is_active": False,
        }
        
        version = ModelVersion.from_dict(data)
        
        assert version.version_id == "v1.0.1"
        assert version.model_type == "lstm"
        assert version.metrics["accuracy"] == 0.88
        assert version.is_active is False


class TestModelVersioningSystem:
    """Test ModelVersioningSystem class"""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory"""
        temp_dir = tempfile.mkdtemp()
        storage_path = Path(temp_dir) / "versions.json"
        yield str(storage_path)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def versioning_system(self, temp_storage):
        """Create versioning system with temp storage"""
        return ModelVersioningSystem(storage_path=temp_storage)
    
    def test_initialization(self, temp_storage):
        """Test versioning system initialization"""
        system = ModelVersioningSystem(storage_path=temp_storage)
        
        assert system.versions == {}
        assert system.active_versions == {}
    
    def test_register_model(self, versioning_system):
        """Test registering a new model version"""
        version = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model.pt",
            metrics={"accuracy": 0.85, "loss": 0.15, "training_samples": 10000},
        )
        
        assert version.version_id == "lstm-v1.0.0"
        assert version.model_type == "lstm"
        assert version.metrics["accuracy"] == 0.85
        assert version.is_active is False
        assert len(versioning_system.versions["lstm"]) == 1
    
    def test_register_multiple_versions(self, versioning_system):
        """Test registering multiple versions"""
        v1 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v1.pt",
            metrics={"accuracy": 0.85},
        )
        
        v2 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v2.pt",
            metrics={"accuracy": 0.87},
        )
        
        v3 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v3.pt",
            metrics={"accuracy": 0.89},
        )
        
        assert v1.version_id == "lstm-v1.0.0"
        assert v2.version_id == "lstm-v1.0.1"
        assert v3.version_id == "lstm-v1.0.2"
        assert len(versioning_system.versions["lstm"]) == 3
    
    def test_register_different_model_types(self, versioning_system):
        """Test registering versions for different model types"""
        lstm_v = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/lstm.pt",
            metrics={"accuracy": 0.85},
        )
        
        xgb_v = versioning_system.register_model(
            model_type="xgboost",
            file_path="checkpoints/xgb.json",
            metrics={"accuracy": 0.90},
        )
        
        assert lstm_v.version_id == "lstm-v1.0.0"
        assert xgb_v.version_id == "xgboost-v1.0.0"
        assert len(versioning_system.versions["lstm"]) == 1
        assert len(versioning_system.versions["xgboost"]) == 1
    
    def test_register_invalid_model_type(self, versioning_system):
        """Test registering with invalid model type"""
        with pytest.raises(ValueError, match="Invalid model type"):
            versioning_system.register_model(
                model_type="invalid",
                file_path="checkpoints/model.pt",
                metrics={"accuracy": 0.85},
            )
    
    def test_register_duplicate_version(self, versioning_system):
        """Test registering duplicate version"""
        versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model.pt",
            metrics={"accuracy": 0.85},
            version_id="v1.0.0",
        )
        
        with pytest.raises(ValueError, match="already exists"):
            versioning_system.register_model(
                model_type="lstm",
                file_path="checkpoints/model2.pt",
                metrics={"accuracy": 0.87},
                version_id="v1.0.0",
            )
    
    def test_activate_model(self, versioning_system):
        """Test activating a model version"""
        version = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model.pt",
            metrics={"accuracy": 0.85},
        )
        
        result = versioning_system.activate_model(version.version_id)
        
        assert result is True
        active = versioning_system.get_active_model("lstm")
        assert active is not None
        assert active.version_id == version.version_id
        assert active.is_active is True
    
    def test_activate_nonexistent_version(self, versioning_system):
        """Test activating non-existent version"""
        result = versioning_system.activate_model("v99.0.0")
        assert result is False
    
    def test_get_active_model(self, versioning_system):
        """Test getting active model"""
        version = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model.pt",
            metrics={"accuracy": 0.85},
        )
        
        # No active model initially
        active = versioning_system.get_active_model("lstm")
        assert active is None
        
        # Activate model
        versioning_system.activate_model(version.version_id)
        
        # Now should return active model
        active = versioning_system.get_active_model("lstm")
        assert active is not None
        assert active.version_id == version.version_id
    
    def test_rollback_model(self, versioning_system):
        """Test rolling back to previous version"""
        # Register multiple versions
        v1 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v1.pt",
            metrics={"accuracy": 0.85},
        )
        
        v2 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v2.pt",
            metrics={"accuracy": 0.87},
        )
        
        v3 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v3.pt",
            metrics={"accuracy": 0.89},
        )
        
        # Activate latest version
        versioning_system.activate_model(v3.version_id)
        
        # Rollback 1 step
        rollback = versioning_system.rollback_model("lstm", steps=1)
        
        assert rollback is not None
        assert rollback.version_id == v2.version_id
        
        # Verify active model
        active = versioning_system.get_active_model("lstm")
        assert active.version_id == v2.version_id
    
    def test_rollback_multiple_steps(self, versioning_system):
        """Test rolling back multiple steps"""
        v1 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v1.pt",
            metrics={"accuracy": 0.85},
        )
        
        v2 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v2.pt",
            metrics={"accuracy": 0.87},
        )
        
        v3 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v3.pt",
            metrics={"accuracy": 0.89},
        )
        
        # Activate latest
        versioning_system.activate_model(v3.version_id)
        
        # Rollback 2 steps
        rollback = versioning_system.rollback_model("lstm", steps=2)
        
        assert rollback is not None
        assert rollback.version_id == v1.version_id
    
    def test_rollback_too_far(self, versioning_system):
        """Test rolling back too many steps"""
        version = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model.pt",
            metrics={"accuracy": 0.85},
        )
        
        versioning_system.activate_model(version.version_id)
        
        # Try to rollback 1 step (no previous version)
        rollback = versioning_system.rollback_model("lstm", steps=1)
        
        assert rollback is None
    
    def test_list_versions(self, versioning_system):
        """Test listing versions"""
        v1 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v1.pt",
            metrics={"accuracy": 0.85},
        )
        
        v2 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v2.pt",
            metrics={"accuracy": 0.87},
        )
        
        v3 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v3.pt",
            metrics={"accuracy": 0.89},
        )
        
        versions = versioning_system.list_versions("lstm", limit=10)
        
        assert len(versions) == 3
        # Should be sorted by version (most recent first)
        assert versions[0].version_id == v3.version_id
        assert versions[1].version_id == v2.version_id
        assert versions[2].version_id == v1.version_id
    
    def test_list_versions_with_limit(self, versioning_system):
        """Test listing versions with limit"""
        versions_created = []
        for i in range(5):
            v = versioning_system.register_model(
                model_type="lstm",
                file_path=f"checkpoints/model_v{i}.pt",
                metrics={"accuracy": 0.85 + i * 0.01},
            )
            versions_created.append(v)
        
        versions = versioning_system.list_versions("lstm", limit=2)
        
        assert len(versions) == 2
        assert versions[0].version_id == versions_created[4].version_id
        assert versions[1].version_id == versions_created[3].version_id
    
    def test_compare_versions(self, versioning_system):
        """Test comparing two versions"""
        v1 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v1.pt",
            metrics={"accuracy": 0.85, "loss": 0.15, "training_samples": 10000},
        )
        
        v2 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v2.pt",
            metrics={"accuracy": 0.87, "loss": 0.13, "training_samples": 15000},
        )
        
        comparison = versioning_system.compare_versions(v1.version_id, v2.version_id)
        
        assert comparison is not None
        assert comparison.version_id_1 == v1.version_id
        assert comparison.version_id_2 == v2.version_id
        assert comparison.metrics_diff["accuracy"] == pytest.approx(0.02, rel=0.01)
        assert comparison.metrics_diff["loss"] == pytest.approx(-0.02, rel=0.01)
        assert comparison.winner == v2.version_id  # Higher accuracy
    
    def test_compare_versions_improvement_pct(self, versioning_system):
        """Test percentage improvement calculation"""
        v1 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v1.pt",
            metrics={"accuracy": 0.80, "loss": 0.20},
        )
        
        v2 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v2.pt",
            metrics={"accuracy": 0.90, "loss": 0.10},
        )
        
        comparison = versioning_system.compare_versions(v1.version_id, v2.version_id)
        
        # Accuracy improved by 12.5%: (0.90 - 0.80) / 0.80 * 100
        assert comparison.improvement_pct["accuracy"] == pytest.approx(12.5, rel=0.01)
        # Loss improved by -50%: (0.10 - 0.20) / 0.20 * 100
        assert comparison.improvement_pct["loss"] == pytest.approx(-50.0, rel=0.01)
    
    def test_compare_nonexistent_versions(self, versioning_system):
        """Test comparing non-existent versions"""
        comparison = versioning_system.compare_versions("v99.0.0", "v98.0.0")
        assert comparison is None
    
    def test_delete_version(self, versioning_system):
        """Test deleting a version"""
        v1 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v1.pt",
            metrics={"accuracy": 0.85},
        )
        
        v2 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model_v2.pt",
            metrics={"accuracy": 0.87},
        )
        
        # Delete non-active version
        result = versioning_system.delete_version(v1.version_id)
        
        assert result is True
        assert len(versioning_system.versions["lstm"]) == 1
        assert versioning_system.get_version(v1.version_id) is None
    
    def test_delete_active_version(self, versioning_system):
        """Test deleting active version (should fail)"""
        version = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model.pt",
            metrics={"accuracy": 0.85},
        )
        
        versioning_system.activate_model(version.version_id)
        
        # Try to delete active version
        result = versioning_system.delete_version(version.version_id)
        
        assert result is False
        assert len(versioning_system.versions["lstm"]) == 1
    
    def test_get_version(self, versioning_system):
        """Test getting a specific version"""
        v = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/model.pt",
            metrics={"accuracy": 0.85},
        )
        
        version = versioning_system.get_version(v.version_id)
        
        assert version is not None
        assert version.version_id == v.version_id
    
    def test_get_nonexistent_version(self, versioning_system):
        """Test getting non-existent version"""
        version = versioning_system.get_version("v99.0.0")
        assert version is None
    
    def test_get_statistics(self, versioning_system):
        """Test getting statistics"""
        v1 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/lstm_v1.pt",
            metrics={"accuracy": 0.85},
        )
        
        v2 = versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/lstm_v2.pt",
            metrics={"accuracy": 0.87},
        )
        
        v3 = versioning_system.register_model(
            model_type="xgboost",
            file_path="checkpoints/xgb_v1.json",
            metrics={"accuracy": 0.90},
        )
        
        versioning_system.activate_model(v2.version_id)  # Activate lstm v2
        
        stats = versioning_system.get_statistics()
        
        assert stats["total_versions"] == 3
        assert stats["model_types"]["lstm"]["count"] == 2
        assert stats["model_types"]["xgboost"]["count"] == 1
        assert stats["model_types"]["lstm"]["active_version"] == v2.version_id
        assert stats["model_types"]["lstm"]["latest_version"] == v2.version_id
    
    def test_persistence(self, temp_storage):
        """Test that versions persist across instances"""
        # Create first instance and register version
        system1 = ModelVersioningSystem(storage_path=temp_storage)
        v = system1.register_model(
            model_type="lstm",
            file_path="checkpoints/model.pt",
            metrics={"accuracy": 0.85},
        )
        system1.activate_model(v.version_id)
        
        # Create second instance and verify persistence
        system2 = ModelVersioningSystem(storage_path=temp_storage)
        
        assert len(system2.versions["lstm"]) == 1
        active = system2.get_active_model("lstm")
        assert active is not None
        assert active.version_id == v.version_id


class TestVersionComparison:
    """Test VersionComparison dataclass"""
    
    def test_version_comparison_creation(self):
        """Test creating a VersionComparison"""
        comparison = VersionComparison(
            version_id_1="v1.0.0",
            version_id_2="v1.0.1",
            metrics_diff={"accuracy": 0.02, "loss": -0.02},
            winner="v1.0.1",
            improvement_pct={"accuracy": 2.5, "loss": -15.0},
        )
        
        assert comparison.version_id_1 == "v1.0.0"
        assert comparison.version_id_2 == "v1.0.1"
        assert comparison.winner == "v1.0.1"
    
    def test_version_comparison_to_dict(self):
        """Test converting VersionComparison to dict"""
        comparison = VersionComparison(
            version_id_1="v1.0.0",
            version_id_2="v1.0.1",
            metrics_diff={"accuracy": 0.02},
            winner="v1.0.1",
            improvement_pct={"accuracy": 2.5},
        )
        
        data = comparison.to_dict()
        
        assert data["version_id_1"] == "v1.0.0"
        assert data["version_id_2"] == "v1.0.1"
        assert data["winner"] == "v1.0.1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
