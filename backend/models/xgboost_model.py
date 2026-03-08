"""
LeadXGBoost Model for Micro-Spike Detection

This module implements an XGBoost trigger model for detecting leading micro-spikes
in Binance data. The model works on 1-second bars and outputs confidence scores
for trading signals.

Architecture:
- Input: Feature vector from 1-second bar data
- XGBoost Classifier with binary:logistic objective
- Output: Confidence score (0-1), Signal (1 if confidence > 0.85)

Features:
- Price features: price, price_velocity, price_acceleration
- Volume features: volume, volume_surge, volume_velocity
- Order flow: taker_buy_sell_ratio, order_imbalance
- Microstructure: trade_count, avg_trade_size, trade_size_std
- Derived: hurst_exponent, ema_crossings, mean_reversion_score
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Any, Union
from pathlib import Path
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime

# XGBoost imports
import xgboost as xgb
from xgboost import XGBClassifier

# Scikit-learn for metrics and utilities
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    log_loss,
    confusion_matrix,
    classification_report,
)
from sklearn.preprocessing import StandardScaler

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class LeadXGBoostConfig:
    """Configuration for LeadXGBoost model."""

    # Model parameters
    max_depth: int = 6
    learning_rate: float = 0.1
    n_estimators: int = 100
    objective: str = "binary:logistic"
    booster: str = "gbtree"

    # Regularization
    min_child_weight: float = 1.0
    gamma: float = 0.0
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_alpha: float = 0.0
    reg_lambda: float = 1.0

    # Imbalanced data handling
    scale_pos_weight: float = 1.0
    max_delta_step: int = 0

    # Training parameters
    early_stopping_rounds: int = 10
    eval_metric: List[str] = field(default_factory=lambda: ["auc", "logloss"])

    # Threshold for signal generation
    confidence_threshold: float = 0.85

    # Feature names (for reference)
    feature_names: Tuple[str, ...] = (
        "price",
        "price_velocity",
        "price_acceleration",
        "volume",
        "volume_surge",
        "volume_velocity",
        "taker_buy_sell_ratio",
        "order_imbalance",
        "trade_count",
        "avg_trade_size",
        "trade_size_std",
        "hurst_exponent",
        "ema_crossings",
        "mean_reversion_score",
    )

    # Random state for reproducibility
    random_state: int = 42

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "max_depth": self.max_depth,
            "learning_rate": self.learning_rate,
            "n_estimators": self.n_estimators,
            "objective": self.objective,
            "booster": self.booster,
            "min_child_weight": self.min_child_weight,
            "gamma": self.gamma,
            "subsample": self.subsample,
            "colsample_bytree": self.colsample_bytree,
            "reg_alpha": self.reg_alpha,
            "reg_lambda": self.reg_lambda,
            "scale_pos_weight": self.scale_pos_weight,
            "max_delta_step": self.max_delta_step,
            "early_stopping_rounds": self.early_stopping_rounds,
            "eval_metric": self.eval_metric,
            "confidence_threshold": self.confidence_threshold,
            "feature_names": list(self.feature_names),
            "random_state": self.random_state,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LeadXGBoostConfig":
        """Create config from dictionary."""
        return cls(
            max_depth=data.get("max_depth", 6),
            learning_rate=data.get("learning_rate", 0.1),
            n_estimators=data.get("n_estimators", 100),
            objective=data.get("objective", "binary:logistic"),
            booster=data.get("booster", "gbtree"),
            min_child_weight=data.get("min_child_weight", 1.0),
            gamma=data.get("gamma", 0.0),
            subsample=data.get("subsample", 0.8),
            colsample_bytree=data.get("colsample_bytree", 0.8),
            reg_alpha=data.get("reg_alpha", 0.0),
            reg_lambda=data.get("reg_lambda", 1.0),
            scale_pos_weight=data.get("scale_pos_weight", 1.0),
            max_delta_step=data.get("max_delta_step", 0),
            early_stopping_rounds=data.get("early_stopping_rounds", 10),
            eval_metric=data.get("eval_metric", ["auc", "logloss"]),
            confidence_threshold=data.get("confidence_threshold", 0.85),
            feature_names=tuple(data.get("feature_names", (
                "price",
                "price_velocity",
                "price_acceleration",
                "volume",
                "volume_surge",
                "volume_velocity",
                "taker_buy_sell_ratio",
                "order_imbalance",
                "trade_count",
                "avg_trade_size",
                "trade_size_std",
                "hurst_exponent",
                "ema_crossings",
                "mean_reversion_score",
            ))),
            random_state=data.get("random_state", 42),
        )


class LeadXGBoost:
    """
    XGBoost trigger model for detecting leading micro-spikes.

    This model analyzes 1-second bar data to detect early signals of price
    movements. It outputs a confidence score and generates trading signals
    when confidence exceeds the threshold (default 0.85).

    Features:
    - Price features: price, price_velocity, price_acceleration
    - Volume features: volume, volume_surge, volume_velocity
    - Order flow: taker_buy_sell_ratio, order_imbalance
    - Microstructure: trade_count, avg_trade_size, trade_size_std
    - Derived: hurst_exponent, ema_crossings, mean_reversion_score

    Output:
    - Confidence score (0-1)
    - Signal: 1 if confidence > threshold (0.85)
    """

    def __init__(self, config: Optional[LeadXGBoostConfig] = None):
        """
        Initialize the LeadXGBoost model.

        Args:
            config: Model configuration. If None, uses default config.
        """
        self.config = config or LeadXGBoostConfig()
        self.model: Optional[XGBClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.is_fitted: bool = False
        self.feature_importance_: Optional[Dict[str, float]] = None

        # Initialize the model
        self._init_model()

    def _init_model(self) -> None:
        """Initialize the XGBoost classifier with configuration."""
        self.model = XGBClassifier(
            max_depth=self.config.max_depth,
            learning_rate=self.config.learning_rate,
            n_estimators=self.config.n_estimators,
            objective=self.config.objective,
            booster=self.config.booster,
            min_child_weight=self.config.min_child_weight,
            gamma=self.config.gamma,
            subsample=self.config.subsample,
            colsample_bytree=self.config.colsample_bytree,
            reg_alpha=self.config.reg_alpha,
            reg_lambda=self.config.reg_lambda,
            scale_pos_weight=self.config.scale_pos_weight,
            max_delta_step=self.config.max_delta_step,
            random_state=self.config.random_state,
            use_label_encoder=False,
            eval_metric=self.config.eval_metric,
        )

        # Initialize scaler for feature normalization
        self.scaler = StandardScaler()

    def prepare_features(
        self,
        data: Union[pd.DataFrame, np.ndarray],
        fit_scaler: bool = False,
    ) -> np.ndarray:
        """
        Prepare features for model input.

        Args:
            data: Input data (DataFrame or numpy array)
            fit_scaler: Whether to fit the scaler on this data

        Returns:
            Prepared feature array
        """
        if isinstance(data, pd.DataFrame):
            # Extract features in the correct order
            features = data[list(self.config.feature_names)].values
        else:
            features = np.asarray(data)

        # Validate feature dimensions
        expected_features = len(self.config.feature_names)
        if features.shape[1] != expected_features:
            raise ValueError(
                f"Expected {expected_features} features, got {features.shape[1]}"
            )

        # Handle missing values
        features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)

        # Scale features
        if fit_scaler:
            features = self.scaler.fit_transform(features)
        elif self.scaler is not None and hasattr(self.scaler, "mean_"):
            features = self.scaler.transform(features)

        return features.astype(np.float32)

    def train(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        X_val: Optional[Union[pd.DataFrame, np.ndarray]] = None,
        y_val: Optional[Union[pd.Series, np.ndarray]] = None,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        Train the XGBoost model.

        Args:
            X: Training features
            y: Training labels (binary: 0 or 1)
            X_val: Optional validation features
            y_val: Optional validation labels
            verbose: Whether to print training progress

        Returns:
            Dictionary with training metrics
        """
        # Prepare features
        X_train = self.prepare_features(X, fit_scaler=True)
        y_train = np.asarray(y).ravel()

        # Validate labels
        unique_labels = np.unique(y_train)
        if not np.all(np.isin(unique_labels, [0, 1])):
            raise ValueError("Labels must be binary (0 or 1)")

        # Calculate scale_pos_weight if not set
        if self.config.scale_pos_weight == 1.0:
            n_pos = np.sum(y_train == 1)
            n_neg = np.sum(y_train == 0)
            if n_pos > 0:
                self.config.scale_pos_weight = n_neg / n_pos
                self.model.scale_pos_weight = self.config.scale_pos_weight

        # Prepare validation data
        eval_set = None
        if X_val is not None and y_val is not None:
            X_val_prep = self.prepare_features(X_val)
            y_val_prep = np.asarray(y_val).ravel()
            eval_set = [(X_train, y_train), (X_val_prep, y_val_prep)]

        # Train the model
        if verbose:
            logger.info(f"Training XGBoost model with {len(X_train)} samples")
            logger.info(f"Positive samples: {np.sum(y_train == 1)}")
            logger.info(f"Negative samples: {np.sum(y_train == 0)}")
            logger.info(f"Scale pos weight: {self.config.scale_pos_weight:.2f}")

        self.model.fit(
            X_train,
            y_train,
            eval_set=eval_set,
            verbose=verbose,
        )

        self.is_fitted = True

        # Calculate feature importance
        self._calculate_feature_importance()

        # Return training metrics
        train_metrics = self._calculate_metrics(X_train, y_train)

        if verbose:
            logger.info(f"Training metrics: {train_metrics}")

        return train_metrics

    def _calculate_feature_importance(self) -> None:
        """Calculate and store feature importance."""
        if self.model is None or not self.is_fitted:
            return

        importance_scores = self.model.feature_importances_
        self.feature_importance_ = {
            name: float(score)
            for name, score in zip(self.config.feature_names, importance_scores)
        }

    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Get binary predictions.

        Args:
            X: Input features

        Returns:
            Binary predictions array
        """
        if not self.is_fitted:
            raise ValueError("Model must be trained before prediction")

        X_prep = self.prepare_features(X)
        return self.model.predict(X_prep)

    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Get probability predictions.

        Args:
            X: Input features

        Returns:
            Probability array of shape (n_samples, 2)
        """
        if not self.is_fitted:
            raise ValueError("Model must be trained before prediction")

        X_prep = self.prepare_features(X)
        return self.model.predict_proba(X_prep)

    def get_confidence(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Get confidence scores for positive class.

        Args:
            X: Input features

        Returns:
            Confidence score array (0-1)
        """
        proba = self.predict_proba(X)
        return proba[:, 1]  # Probability of positive class

    def get_signals(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        threshold: Optional[float] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get trading signals based on confidence threshold.

        Args:
            X: Input features
            threshold: Confidence threshold (uses config default if None)

        Returns:
            Tuple of (signals, confidence_scores)
        """
        threshold = threshold or self.config.confidence_threshold
        confidence = self.get_confidence(X)
        signals = (confidence >= threshold).astype(int)
        return signals, confidence

    def _calculate_metrics(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> Dict[str, float]:
        """Calculate evaluation metrics."""
        y_pred = self.model.predict(X)
        y_proba = self.model.predict_proba(X)[:, 1]

        metrics = {
            "precision": float(precision_score(y, y_pred, zero_division=0)),
            "recall": float(recall_score(y, y_pred, zero_division=0)),
            "f1": float(f1_score(y, y_pred, zero_division=0)),
            "auc": float(roc_auc_score(y, y_proba)),
            "logloss": float(log_loss(y, y_proba)),
        }

        return metrics

    def evaluate(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate the model on test data.

        Args:
            X: Test features
            y: Test labels
            threshold: Confidence threshold for signal generation

        Returns:
            Dictionary with evaluation metrics
        """
        threshold = threshold or self.config.confidence_threshold

        X_prep = self.prepare_features(X)
        y_true = np.asarray(y).ravel()

        # Get predictions
        y_pred = self.model.predict(X_prep)
        y_proba = self.model.predict_proba(X_prep)[:, 1]

        # Calculate metrics
        metrics = {
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, zero_division=0)),
            "auc": float(roc_auc_score(y_true, y_proba)),
            "logloss": float(log_loss(y_true, y_proba)),
        }

        # Calculate metrics for high-confidence predictions
        high_conf_mask = y_proba >= threshold
        if np.sum(high_conf_mask) > 0:
            high_conf_pred = y_pred[high_conf_mask]
            high_conf_true = y_true[high_conf_mask]
            metrics["high_confidence_count"] = int(np.sum(high_conf_mask))
            metrics["high_confidence_precision"] = float(
                precision_score(high_conf_true, high_conf_pred, zero_division=0)
            )
            metrics["high_confidence_recall"] = float(
                recall_score(high_conf_true, high_conf_pred, zero_division=0)
            )

        # Confusion matrix
        cm = confusion_matrix(y_true, y_pred)
        metrics["confusion_matrix"] = {
            "tn": int(cm[0, 0]),
            "fp": int(cm[0, 1]),
            "fn": int(cm[1, 0]),
            "tp": int(cm[1, 1]),
        }

        return metrics

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance scores.

        Returns:
            Dictionary mapping feature names to importance scores
        """
        if self.feature_importance_ is None:
            self._calculate_feature_importance()
        return self.feature_importance_ or {}

    def save_model(self, path: Union[str, Path]) -> None:
        """
        Save the model to disk.

        Args:
            path: Path to save the model
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Save model
        model_path = path.with_suffix(".json")
        self.model.save_model(str(model_path))

        # Save config and scaler
        config_path = path.with_suffix(".config.json")
        with open(config_path, "w") as f:
            json.dump({
                "config": self.config.to_dict(),
                "scaler_mean": self.scaler.mean_.tolist() if self.scaler else None,
                "scaler_scale": self.scaler.scale_.tolist() if self.scaler else None,
                "is_fitted": self.is_fitted,
            }, f, indent=2)

        logger.info(f"Model saved to {path}")

    def load_model(self, path: Union[str, Path]) -> None:
        """
        Load the model from disk.

        Args:
            path: Path to load the model from
        """
        path = Path(path)

        # Load model
        model_path = path.with_suffix(".json")
        self.model.load_model(str(model_path))

        # Load config and scaler
        config_path = path.with_suffix(".config.json")
        with open(config_path, "r") as f:
            data = json.load(f)
            self.config = LeadXGBoostConfig.from_dict(data["config"])
            if data.get("scaler_mean") and data.get("scaler_scale"):
                self.scaler.mean_ = np.array(data["scaler_mean"])
                self.scaler.scale_ = np.array(data["scaler_scale"])
            self.is_fitted = data.get("is_fitted", True)

        self._calculate_feature_importance()
        logger.info(f"Model loaded from {path}")


class LeadXGBoostTrainer:
    """
    Training pipeline for LeadXGBoost model.

    Handles data preparation, training, validation, and evaluation
    for the XGBoost trigger model.
    """

    def __init__(
        self,
        config: Optional[LeadXGBoostConfig] = None,
        output_dir: Union[str, Path] = "checkpoints",
    ):
        """
        Initialize the trainer.

        Args:
            config: Model configuration
            output_dir: Directory to save models and results
        """
        self.config = config or LeadXGBoostConfig()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.model: Optional[LeadXGBoost] = None
        self.training_history: List[Dict[str, Any]] = []

    def prepare_training_data(
        self,
        data: pd.DataFrame,
        label_column: str = "label",
        test_size: float = 0.2,
        val_size: float = 0.1,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
        """
        Prepare data for training.

        Args:
            data: DataFrame with features and labels
            label_column: Name of the label column
            test_size: Proportion of data for testing
            val_size: Proportion of training data for validation

        Returns:
            Tuple of (X_train, X_test, X_val, y_train, y_test, y_val)
        """
        # Separate features and labels
        feature_cols = list(self.config.feature_names)
        X = data[feature_cols]
        y = data[label_column]

        # Split into train and test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=self.config.random_state,
            stratify=y
        )

        # Split train into train and validation
        X_train, X_val, y_train, y_val = train_test_split(
            X_train, y_train, test_size=val_size,
            random_state=self.config.random_state, stratify=y_train
        )

        logger.info(f"Training samples: {len(X_train)}")
        logger.info(f"Validation samples: {len(X_val)}")
        logger.info(f"Test samples: {len(X_test)}")

        return X_train, X_test, X_val, y_train, y_test, y_val

    def train(
        self,
        X_train: Union[pd.DataFrame, np.ndarray],
        y_train: Union[pd.Series, np.ndarray],
        X_val: Optional[Union[pd.DataFrame, np.ndarray]] = None,
        y_val: Optional[Union[pd.Series, np.ndarray]] = None,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        Train the model.

        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            verbose: Whether to print progress

        Returns:
            Training metrics
        """
        # Initialize model
        self.model = LeadXGBoost(self.config)

        # Train
        train_metrics = self.model.train(
            X_train, y_train, X_val, y_val, verbose=verbose
        )

        # Store history
        self.training_history.append({
            "timestamp": datetime.now().isoformat(),
            "train_metrics": train_metrics,
        })

        return train_metrics

    def evaluate(
        self,
        X_test: Union[pd.DataFrame, np.ndarray],
        y_test: Union[pd.Series, np.ndarray],
    ) -> Dict[str, Any]:
        """
        Evaluate the model on test data.

        Args:
            X_test: Test features
            y_test: Test labels

        Returns:
            Evaluation metrics
        """
        if self.model is None:
            raise ValueError("Model must be trained before evaluation")

        return self.model.evaluate(X_test, y_test)

    def save_model(self, name: str = "lead_xgboost") -> Path:
        """
        Save the trained model.

        Args:
            name: Name for the saved model

        Returns:
            Path to the saved model
        """
        if self.model is None:
            raise ValueError("Model must be trained before saving")

        path = self.output_dir / name
        self.model.save_model(path)
        return path

    def load_model(self, path: Union[str, Path]) -> None:
        """
        Load a trained model.

        Args:
            path: Path to the model
        """
        self.model = LeadXGBoost(self.config)
        self.model.load_model(path)


def generate_mock_data(
    n_samples: int = 10000,
    random_state: int = 42,
    positive_ratio: float = 0.15,
) -> pd.DataFrame:
    """
    Generate mock data for testing the model.

    Args:
        n_samples: Number of samples to generate
        random_state: Random seed for reproducibility
        positive_ratio: Ratio of positive samples

    Returns:
        DataFrame with features and labels
    """
    np.random.seed(random_state)

    # Generate base features
    n_pos = int(n_samples * positive_ratio)
    n_neg = n_samples - n_pos

    # Price features (with micro-spikes for positive samples)
    price_base = 100.0
    price = np.concatenate([
        price_base + np.random.randn(n_neg) * 0.5,  # Stable prices
        price_base + np.abs(np.random.randn(n_pos)) * 2.0,  # Spikes
    ])

    # Price velocity (higher for positive samples)
    price_velocity = np.concatenate([
        np.random.randn(n_neg) * 0.1,
        np.random.randn(n_pos) * 0.5 + 0.3,
    ])

    # Price acceleration (higher for positive samples)
    price_acceleration = np.concatenate([
        np.random.randn(n_neg) * 0.05,
        np.random.randn(n_pos) * 0.2 + 0.1,
    ])

    # Volume features (surge for positive samples)
    volume_base = 1000.0
    volume = np.concatenate([
        volume_base + np.random.exponential(200, n_neg),
        volume_base * 2 + np.random.exponential(500, n_pos),  # Volume surge
    ])

    volume_surge = np.concatenate([
        np.random.uniform(0, 0.3, n_neg),
        np.random.uniform(0.5, 1.0, n_pos),
    ])

    volume_velocity = np.concatenate([
        np.random.randn(n_neg) * 0.1,
        np.random.randn(n_pos) * 0.3 + 0.2,
    ])

    # Order flow features
    taker_buy_sell_ratio = np.concatenate([
        np.random.uniform(0.4, 0.6, n_neg),
        np.random.uniform(0.6, 0.9, n_pos),  # Buy pressure
    ])

    order_imbalance = np.concatenate([
        np.random.randn(n_neg) * 0.1,
        np.random.randn(n_pos) * 0.3 + 0.2,
    ])

    # Microstructure features
    trade_count = np.concatenate([
        np.random.poisson(50, n_neg),
        np.random.poisson(100, n_pos),  # More trades
    ])

    avg_trade_size = np.concatenate([
        volume[:n_neg] / trade_count[:n_neg],
        volume[n_neg:] / trade_count[n_neg:],
    ])

    trade_size_std = np.concatenate([
        np.random.exponential(10, n_neg),
        np.random.exponential(20, n_pos),
    ])

    # Derived features
    hurst_exponent = np.concatenate([
        np.random.uniform(0.4, 0.6, n_neg),
        np.random.uniform(0.55, 0.75, n_pos),  # Trending
    ])

    ema_crossings = np.concatenate([
        np.random.randint(0, 3, n_neg),
        np.random.randint(2, 6, n_pos),  # More crossings
    ])

    mean_reversion_score = np.concatenate([
        np.random.uniform(0.3, 0.7, n_neg),
        np.random.uniform(0.1, 0.4, n_pos),  # Less mean reversion
    ])

    # Create labels
    labels = np.concatenate([
        np.zeros(n_neg),
        np.ones(n_pos),
    ])

    # Create DataFrame
    df = pd.DataFrame({
        "price": price,
        "price_velocity": price_velocity,
        "price_acceleration": price_acceleration,
        "volume": volume,
        "volume_surge": volume_surge,
        "volume_velocity": volume_velocity,
        "taker_buy_sell_ratio": taker_buy_sell_ratio,
        "order_imbalance": order_imbalance,
        "trade_count": trade_count,
        "avg_trade_size": avg_trade_size,
        "trade_size_std": trade_size_std,
        "hurst_exponent": hurst_exponent,
        "ema_crossings": ema_crossings,
        "mean_reversion_score": mean_reversion_score,
        "label": labels,
    })

    # Shuffle
    df = df.sample(frac=1, random_state=random_state).reset_index(drop=True)

    return df


def train_xgboost_model(
    data: Optional[pd.DataFrame] = None,
    config: Optional[LeadXGBoostConfig] = None,
    output_dir: Union[str, Path] = "checkpoints",
    verbose: bool = True,
) -> Tuple[LeadXGBoost, Dict[str, Any]]:
    """
    Train an XGBoost model on the provided data.

    Args:
        data: Training data (generates mock data if None)
        config: Model configuration
        output_dir: Directory to save model
        verbose: Whether to print progress

    Returns:
        Tuple of (trained model, evaluation metrics)
    """
    # Generate mock data if not provided
    if data is None:
        if verbose:
            logger.info("Generating mock data for training")
        data = generate_mock_data()

    # Initialize trainer
    trainer = LeadXGBoostTrainer(config, output_dir)

    # Prepare data
    X_train, X_test, X_val, y_train, y_test, y_val = trainer.prepare_training_data(
        data, label_column="label"
    )

    # Train
    trainer.train(X_train, y_train, X_val, y_val, verbose=verbose)

    # Evaluate
    metrics = trainer.evaluate(X_test, y_test)

    if verbose:
        logger.info(f"Test metrics: {metrics}")

        # Print high-confidence metrics
        if "high_confidence_precision" in metrics:
            logger.info(
                f"High confidence (>{trainer.config.confidence_threshold}) "
                f"precision: {metrics['high_confidence_precision']:.4f}, "
                f"recall: {metrics['high_confidence_recall']:.4f}, "
                f"count: {metrics['high_confidence_count']}"
            )

    # Save model
    trainer.save_model("lead_xgboost")

    return trainer.model, metrics


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train LeadXGBoost model")
    parser.add_argument(
        "--data", type=str, default=None,
        help="Path to training data (CSV). If not provided, uses mock data."
    )
    parser.add_argument(
        "--output", type=str, default="checkpoints",
        help="Output directory for model"
    )
    parser.add_argument(
        "--n-estimators", type=int, default=100,
        help="Number of estimators"
    )
    parser.add_argument(
        "--max-depth", type=int, default=6,
        help="Max tree depth"
    )
    parser.add_argument(
        "--learning-rate", type=float, default=0.1,
        help="Learning rate"
    )
    parser.add_argument(
        "--threshold", type=float, default=0.85,
        help="Confidence threshold for signals"
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress output"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO if not args.quiet else logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create config
    config = LeadXGBoostConfig(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        confidence_threshold=args.threshold,
    )

    # Load data or use mock
    if args.data:
        data = pd.read_csv(args.data)
    else:
        data = None

    # Train
    model, metrics = train_xgboost_model(
        data=data,
        config=config,
        output_dir=args.output,
        verbose=not args.quiet,
    )

    # Print final metrics
    print("\n=== Final Evaluation Metrics ===")
    print(f"Precision: {metrics['precision']:.4f}")
    print(f"Recall: {metrics['recall']:.4f}")
    print(f"F1 Score: {metrics['f1']:.4f}")
    print(f"AUC: {metrics['auc']:.4f}")
    print(f"Log Loss: {metrics['logloss']:.4f}")

    if "high_confidence_precision" in metrics:
        print(f"\n=== High Confidence (>{args.threshold}) ===")
        print(f"Precision: {metrics['high_confidence_precision']:.4f}")
        print(f"Recall: {metrics['high_confidence_recall']:.4f}")
        print(f"Signal Count: {metrics['high_confidence_count']}")
