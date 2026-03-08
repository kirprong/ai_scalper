"""
Inference Engine Module.

This module provides async inference capabilities for running XGBoost and LSTM
predictions in a separate process with low latency (<20ms).

Components:
- InferenceEngine: Main orchestrator for inference operations
- InferenceWorker: Worker process for model predictions
- PredictionRequest/Result: Data models for communication
"""

from .engine import InferenceEngine, PredictionRequest, PredictionResult
from .worker import InferenceWorker

__all__ = [
    "InferenceEngine",
    "InferenceWorker",
    "PredictionRequest",
    "PredictionResult",
]
