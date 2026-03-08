"""
Evolution Module - Model Retraining Pipeline

This module provides automatic model retraining capabilities:
- Daily accuracy monitoring
- Automatic fine-tuning when accuracy drops below threshold
- Model validation and hot reload
- Model versioning and rollback
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

__all__ = [
    "DailyRetrainingConfig",
    "DailyRetrainingPipeline",
    "RetrainingResult",
    "ModelVersion",
    "ModelVersioningSystem",
    "VersionComparison",
]
