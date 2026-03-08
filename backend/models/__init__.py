"""
LSTM Models Module for Golden Rectangle Detection

This module provides neural network models for detecting Golden Rectangle
patterns in market data using LSTM architecture.
"""

from backend.models.lstm_model import (
    RectangleLSTM,
    RectangleLSTMDataset,
    RectangleLSTMConfig,
)

from backend.models.trainer import (
    RectangleLSTMTrainer,
    train_model,
    predict,
    save_model,
    load_model,
)

__all__ = [
    # Model
    "RectangleLSTM",
    "RectangleLSTMConfig",
    "RectangleLSTMDataset",
    # Training
    "RectangleLSTMTrainer",
    "train_model",
    "predict",
    "save_model",
    "load_model",
]
