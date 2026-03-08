"""
LSTM Models Module for Golden Rectangle Detection

This module provides neural network models for detecting Golden Rectangle
patterns in market data using LSTM architecture, and XGBoost models for
detecting leading micro-spikes in Binance data.
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

from backend.models.xgboost_model import (
    LeadXGBoost,
    LeadXGBoostConfig,
    LeadXGBoostTrainer,
    train_xgboost_model,
    generate_mock_data,
)

__all__ = [
# LSTM Model
"RectangleLSTM",
"RectangleLSTMConfig",
"RectangleLSTMDataset",
# LSTM Training
"RectangleLSTMTrainer",
"train_model",
"predict",
"save_model",
"load_model",
# XGBoost Model
"LeadXGBoost",
"LeadXGBoostConfig",
"LeadXGBoostTrainer",
"train_xgboost_model",
"generate_mock_data",
]
