"""
Evolution Module - Model Retraining Pipeline

This module provides automatic model retraining capabilities:
- Daily accuracy monitoring
- Automatic fine-tuning when accuracy drops below threshold
- Model validation and hot reload
- Model versioning and rollback
- A/B testing framework
"""

from backend.evolution.daily_retraining import (
    DailyRetrainingConfig,
    DailyRetrainingPipeline,
    RetrainingResult,
)

from backend.evolution.model_versioning import (
    ModelVersion,
    ModelVersioningSystem,
    VersionComparison,
)

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

__all__ = [
    "DailyRetrainingConfig",
    "DailyRetrainingPipeline",
    "RetrainingResult",
    "ModelVersion",
    "ModelVersioningSystem",
    "VersionComparison",
    "ABTestingFramework",
    "Experiment",
    "Variant",
    "StatisticalResult",
    "ExperimentManager",
    "EarlyStoppingConfig",
]
