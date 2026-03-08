"""
Labeling Module for Historical Data

This module provides automatic labeling of historical market data
with Is_Golden_Box tags for ML training.

Modules:
- history_labeler: Labels data points based on Golden Rectangle detection
"""

from .history_labeler import (
    HistoryLabeler,
    LabelingConfig,
    label_data_point,
    run_labeling_pipeline,
)

__all__ = [
    "HistoryLabeler",
    "LabelingConfig",
    "label_data_point",
    "run_labeling_pipeline",
]
