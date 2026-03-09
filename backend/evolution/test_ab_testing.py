"""
Tests for A/B Testing Framework - TASK-027
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime

from backend.evolution.ab_testing import (
    ABTestingFramework,
    Experiment,
    Variant,
    StatisticalResult,
)
from backend.evolution.experiment_manager import (
    ExperimentManager,
    EarlyStoppingConfig,
)
from backend.evolution.model_versioning import ModelVersioningSystem


class TestABTestingFramework:
    """Test A/B Testing Framework"""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            yield f.name
        Path(f.name).unlink(missing_ok=True)
    
    @pytest.fixture
    def framework(self, temp_storage):
        """Create ABTestingFramework instance"""
        return ABTestingFramework(storage_path=temp_storage)
    
    def test_register_experiment(self, framework):
        """Test experiment registration"""
        experiment = framework.register_experiment(
            name="Test Experiment",
            model_type="lstm",
            variants=[
                {"variant_id": "control", "version_id": "lstm-v1.0.0", "traffic_ratio": 0.5},
                {"variant_id": "treatment", "version_id": "lstm-v1.0.1", "traffic_ratio": 0.5},
            ],
        )
        
        assert experiment.experiment_id is not None
        assert experiment.name == "Test Experiment"
        assert experiment.model_type == "lstm"
        assert experiment.status == "created"
        assert len(experiment.variants) == 2
    
    def test_invalid_traffic_ratio(self, framework):
        """Test that invalid traffic ratios are rejected"""
        with pytest.raises(ValueError, match="Traffic ratios must sum to 1.0"):
            framework.register_experiment(
                name="Invalid Experiment",
                model_type="lstm",
                variants=[
                    {"variant_id": "control", "version_id": "lstm-v1.0.0", "traffic_ratio": 0.3},
                    {"variant_id": "treatment", "version_id": "lstm-v1.0.1", "traffic_ratio": 0.3},
                ],
            )
    
    def test_start_experiment(self, framework):
        """Test starting an experiment"""
        experiment = framework.register_experiment(
            name="Test",
            model_type="lstm",
            variants=[
                {"variant_id": "control", "version_id": "lstm-v1.0.0", "traffic_ratio": 0.5},
                {"variant_id": "treatment", "version_id": "lstm-v1.0.1", "traffic_ratio": 0.5},
            ],
        )
        
        success = framework.start_experiment(experiment.experiment_id)
        assert success is True
        
        updated = framework.get_experiment(experiment.experiment_id)
        assert updated.status == "running"
        assert updated.started_at is not None
    
    def test_pause_experiment(self, framework):
        """Test pausing an experiment"""
        experiment = framework.register_experiment(
            name="Test",
            model_type="lstm",
            variants=[
                {"variant_id": "control", "version_id": "lstm-v1.0.0", "traffic_ratio": 0.5},
                {"variant_id": "treatment", "version_id": "lstm-v1.0.1", "traffic_ratio": 0.5},
            ],
        )
        
        framework.start_experiment(experiment.experiment_id)
        success = framework.pause_experiment(experiment.experiment_id)
        
        assert success is True
        updated = framework.get_experiment(experiment.experiment_id)
        assert updated.status == "paused"
    
    def test_assign_variant(self, framework):
        """Test variant assignment"""
        experiment = framework.register_experiment(
            name="Test",
            model_type="lstm",
            variants=[
                {"variant_id": "control", "version_id": "lstm-v1.0.0", "traffic_ratio": 0.5},
                {"variant_id": "treatment", "version_id": "lstm-v1.0.1", "traffic_ratio": 0.5},
            ],
        )
        
        framework.start_experiment(experiment.experiment_id)
        
        # Test consistent assignment
        variant1 = framework.assign_variant(experiment.experiment_id, "user1")
        variant2 = framework.assign_variant(experiment.experiment_id, "user1")
        
        assert variant1.variant_id == variant2.variant_id
        
        # Test different users get different variants (probabilistic)
        variants = set()
        for i in range(100):
            variant = framework.assign_variant(experiment.experiment_id, f"user{i}")
            variants.add(variant.variant_id)
        
        # Should have both variants with 50/50 split
        assert len(variants) == 2
    
    def test_record_metrics(self, framework):
        """Test metrics recording"""
        experiment = framework.register_experiment(
            name="Test",
            model_type="lstm",
            variants=[
                {"variant_id": "control", "version_id": "lstm-v1.0.0", "traffic_ratio": 0.5},
                {"variant_id": "treatment", "version_id": "lstm-v1.0.1", "traffic_ratio": 0.5},
            ],
        )
        
        framework.start_experiment(experiment.experiment_id)
        
        # Record metrics
        framework.record_metrics(
            experiment_id=experiment.experiment_id,
            variant_id="control",
            prediction=1.0,
            actual=1.0,
            accuracy=0.85,
        )
        
        updated = framework.get_experiment(experiment.experiment_id)
        control = [v for v in updated.variants if v.variant_id == "control"][0]
        
        assert len(control.metrics["accuracy"]) == 1
        assert control.metrics["accuracy"][0] == 0.85
    
    def test_statistical_significance(self, framework):
        """Test statistical significance calculation"""
        experiment = framework.register_experiment(
            name="Test",
            model_type="lstm",
            variants=[
                {"variant_id": "control", "version_id": "lstm-v1.0.0", "traffic_ratio": 0.5},
                {"variant_id": "treatment", "version_id": "lstm-v1.0.1", "traffic_ratio": 0.5},
            ],
        )
        
        framework.start_experiment(experiment.experiment_id)
        
        # Record metrics with clear difference
        for i in range(50):
            framework.record_metrics(
                experiment_id=experiment.experiment_id,
                variant_id="control",
                prediction=1.0,
                actual=1.0,
                accuracy=0.70 + (i % 10) * 0.01,
            )
            framework.record_metrics(
                experiment_id=experiment.experiment_id,
                variant_id="treatment",
                prediction=1.0,
                actual=1.0,
                accuracy=0.80 + (i % 10) * 0.01,
            )
        
        result = framework.calculate_statistical_significance(experiment.experiment_id)
        
        assert result is not None
        assert result.test_name == "t-test"
        assert result.p_value < 0.05  # Should be significant
        assert result.is_significant == True
    
    def test_select_winner(self, framework):
        """Test winner selection"""
        experiment = framework.register_experiment(
            name="Test",
            model_type="lstm",
            variants=[
                {"variant_id": "control", "version_id": "lstm-v1.0.0", "traffic_ratio": 0.5},
                {"variant_id": "treatment", "version_id": "lstm-v1.0.1", "traffic_ratio": 0.5},
            ],
        )
        
        framework.start_experiment(experiment.experiment_id)
        
        # Record metrics with clear winner
        for i in range(50):
            framework.record_metrics(
                experiment_id=experiment.experiment_id,
                variant_id="control",
                prediction=1.0,
                actual=1.0,
                accuracy=0.70,
            )
            framework.record_metrics(
                experiment_id=experiment.experiment_id,
                variant_id="treatment",
                prediction=1.0,
                actual=1.0,
                accuracy=0.85,
            )
        
        winner = framework.select_winner(experiment.experiment_id)
        
        assert winner == "treatment"
    
    def test_list_experiments(self, framework):
        """Test listing experiments"""
        # Create multiple experiments
        exp1 = framework.register_experiment(
            name="Test1",
            model_type="lstm",
            variants=[
                {"variant_id": "control", "version_id": "lstm-v1.0.0", "traffic_ratio": 0.5},
                {"variant_id": "treatment", "version_id": "lstm-v1.0.1", "traffic_ratio": 0.5},
            ],
        )
        
        exp2 = framework.register_experiment(
            name="Test2",
            model_type="xgboost",
            variants=[
                {"variant_id": "control", "version_id": "xgboost-v1.0.0", "traffic_ratio": 0.7},
                {"variant_id": "treatment", "version_id": "xgboost-v1.0.1", "traffic_ratio": 0.3},
            ],
        )
        
        framework.start_experiment(exp1.experiment_id)
        
        all_experiments = framework.list_experiments()
        assert len(all_experiments) == 2
        
        running_experiments = framework.list_experiments(status="running")
        assert len(running_experiments) == 1
        assert running_experiments[0].experiment_id == exp1.experiment_id


class TestExperimentManager:
    """Test Experiment Manager"""
    
    @pytest.fixture
    def temp_files(self):
        """Create temporary files"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f1:
            f1.write('{}')
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f2:
            f2.write('{}')
        
        yield f1.name, f2.name
        
        Path(f1.name).unlink(missing_ok=True)
        Path(f2.name).unlink(missing_ok=True)
    
    @pytest.fixture
    def manager(self, temp_files):
        """Create ExperimentManager instance"""
        ab_storage, version_storage = temp_files
        
        ab_framework = ABTestingFramework(storage_path=ab_storage)
        versioning_system = ModelVersioningSystem(storage_path=version_storage)
        
        # Register test versions
        versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/lstm_v1.0.0.pkl",
            metrics={"accuracy": 0.80},
            version_id="lstm-v1.0.0",
        )
        versioning_system.register_model(
            model_type="lstm",
            file_path="checkpoints/lstm_v1.0.1.pkl",
            metrics={"accuracy": 0.85},
            version_id="lstm-v1.0.1",
        )
        
        return ExperimentManager(
            ab_framework=ab_framework,
            versioning_system=versioning_system,
        )
    
    def test_create_experiment(self, manager):
        """Test creating experiment through manager"""
        experiment = manager.create_experiment(
            name="Test Experiment",
            model_type="lstm",
            control_version="lstm-v1.0.0",
            treatment_version="lstm-v1.0.1",
            traffic_split=0.5,
        )
        
        assert experiment is not None
        assert experiment.name == "Test Experiment"
        assert len(experiment.variants) == 2
    
    def test_invalid_version(self, manager):
        """Test that invalid versions are rejected"""
        with pytest.raises(ValueError, match="Control version not found"):
            manager.create_experiment(
                name="Test",
                model_type="lstm",
                control_version="invalid-version",
                treatment_version="lstm-v1.0.1",
            )
    
    def test_stop_experiment_with_winner(self, manager):
        """Test stopping experiment and activating winner"""
        experiment = manager.create_experiment(
            name="Test",
            model_type="lstm",
            control_version="lstm-v1.0.0",
            treatment_version="lstm-v1.0.1",
        )
        
        manager.start_experiment(experiment.experiment_id)
        
        # Record metrics
        for i in range(50):
            manager.ab_framework.record_metrics(
                experiment_id=experiment.experiment_id,
                variant_id="treatment",
                prediction=1.0,
                actual=1.0,
                accuracy=0.85,
            )
        
        # Stop with winner
        success = manager.stop_experiment(experiment.experiment_id, winner="treatment")
        assert success is True
        
        # Check version activated
        active = manager.versioning_system.get_active_model("lstm")
        assert active.version_id == "lstm-v1.0.1"
    
    def test_early_stopping(self, manager):
        """Test early stopping detection"""
        experiment = manager.create_experiment(
            name="Test",
            model_type="lstm",
            control_version="lstm-v1.0.0",
            treatment_version="lstm-v1.0.1",
        )
        
        manager.start_experiment(experiment.experiment_id)
        
        # Record metrics with clear difference
        for i in range(100):
            manager.ab_framework.record_metrics(
                experiment_id=experiment.experiment_id,
                variant_id="control",
                prediction=1.0,
                actual=1.0,
                accuracy=0.70,
            )
            manager.ab_framework.record_metrics(
                experiment_id=experiment.experiment_id,
                variant_id="treatment",
                prediction=1.0,
                actual=1.0,
                accuracy=0.85,
            )
        
        # Check early stopping
        winner = manager.check_early_stopping(experiment.experiment_id)
        assert winner == "treatment"
    
    def test_get_experiment_status(self, manager):
        """Test getting experiment status"""
        experiment = manager.create_experiment(
            name="Test",
            model_type="lstm",
            control_version="lstm-v1.0.0",
            treatment_version="lstm-v1.0.1",
        )
        
        manager.start_experiment(experiment.experiment_id)
        
        # Record some metrics
        for i in range(20):
            manager.ab_framework.record_metrics(
                experiment_id=experiment.experiment_id,
                variant_id="control",
                prediction=1.0,
                actual=1.0,
                accuracy=0.75,
            )
        
        status = manager.get_experiment_status(experiment.experiment_id)
        
        assert status is not None
        assert status["experiment_id"] == experiment.experiment_id
        assert status["status"] == "running"
        assert "control" in status["variants"]
        assert status["variants"]["control"]["samples"] == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
