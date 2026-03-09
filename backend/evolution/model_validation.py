"""
Model Validation System - TASK-026

Validates retrained models on historical data before hot reload.
Runs backtest on 3 hours of historical data and checks if profit is confirmed.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import logging
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ValidationConfig:
    """Configuration for model validation."""
    
    # Validation window
    validation_hours: int = 3  # 3 hours of historical data
    
    # Profit thresholds
    min_profit_threshold: float = 0.0  # Minimum profit to confirm (0 = break-even)
    min_accuracy_threshold: float = 0.70  # Minimum accuracy (70%)
    min_sharpe_ratio: float = 0.5  # Minimum Sharpe ratio
    
    # Risk metrics
    max_drawdown_threshold: float = 0.10  # Maximum drawdown (10%)
    max_loss_streak: int = 5  # Maximum consecutive losses
    
    # Signal quality
    min_signal_count: int = 10  # Minimum signals to validate
    min_win_rate: float = 0.55  # Minimum win rate (55%)
    
    # Confidence thresholds
    xgb_confidence_threshold: float = 0.85
    lstm_probability_threshold: float = 0.5


@dataclass
class ValidationResult:
    """Result of model validation on historical data."""
    
    success: bool
    validation_time: datetime
    
    # Performance metrics
    total_profit: float = 0.0
    total_return_pct: float = 0.0
    accuracy: float = 0.0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    
    # Signal metrics
    total_signals: int = 0
    winning_signals: int = 0
    losing_signals: int = 0
    loss_streak: int = 0
    
    # Model metrics
    xgb_precision: float = 0.0
    xgb_recall: float = 0.0
    lstm_accuracy: float = 0.0
    
    # Details
    error_message: Optional[str] = None
    validation_hours: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "validation_time": self.validation_time.isoformat(),
            "total_profit": self.total_profit,
            "total_return_pct": self.total_return_pct,
            "accuracy": self.accuracy,
            "win_rate": self.win_rate,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "total_signals": self.total_signals,
            "winning_signals": self.winning_signals,
            "losing_signals": self.losing_signals,
            "loss_streak": self.loss_streak,
            "xgb_precision": self.xgb_precision,
            "xgb_recall": self.xgb_recall,
            "lstm_accuracy": self.lstm_accuracy,
            "error_message": self.error_message,
            "validation_hours": self.validation_hours,
            "details": self.details,
        }


class ModelValidator:
    """
    Validates retrained models on historical data.
    
    Runs backtest on 3 hours of historical data and checks:
    - Profit is positive (or meets threshold)
    - Accuracy meets minimum threshold
    - Risk metrics are acceptable
    - Signal quality is sufficient
    """
    
    def __init__(
        self,
        config: ValidationConfig,
        lstm_model: Optional[Any] = None,
        xgb_model: Optional[Any] = None,
    ):
        self.config = config
        self.lstm_model = lstm_model
        self.xgb_model = xgb_model
        self.validation_history: List[ValidationResult] = []
    
    def fetch_historical_data(
        self,
        hours: int = 3,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Fetch historical data for validation.
        
        Args:
            hours: Number of hours of historical data
            end_time: End time for validation period (default: now)
            
        Returns:
            Dictionary with historical data
        """
        end_time = end_time or datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        logger.info(f"Fetching historical data from {start_time} to {end_time}")
        
        # In production, this would fetch from ClickHouse
        # For now, generate mock data
        n_samples = hours * 3600  # 1 sample per second
        
        # Generate mock features
        np.random.seed(42)
        
        features = {
            "price": 100.0 + np.cumsum(np.random.randn(n_samples) * 0.1),
            "price_velocity": np.random.randn(n_samples) * 0.1,
            "price_acceleration": np.random.randn(n_samples) * 0.05,
            "volume": 1000.0 + np.random.exponential(200, n_samples),
            "volume_surge": np.random.uniform(0, 1, n_samples),
            "volume_velocity": np.random.randn(n_samples) * 0.1,
            "taker_buy_sell_ratio": np.random.uniform(0.4, 0.6, n_samples),
            "order_imbalance": np.random.randn(n_samples) * 0.1,
            "trade_count": np.random.poisson(50, n_samples),
            "avg_trade_size": np.random.exponential(20, n_samples),
            "trade_size_std": np.random.exponential(5, n_samples),
            "hurst_exponent": np.random.uniform(0.4, 0.6, n_samples),
            "ema_crossings": np.random.randint(0, 5, n_samples),
            "mean_reversion_score": np.random.uniform(0.3, 0.7, n_samples),
        }
        
        # Generate mock labels (Golden Box signals)
        # About 5% of samples are positive
        labels = (np.random.rand(n_samples) < 0.05).astype(int)
        
        # Generate mock returns (profit/loss for each signal)
        returns = np.random.randn(n_samples) * 0.02  # 2% std dev
        
        return {
            "features": features,
            "labels": labels,
            "returns": returns,
            "timestamps": [start_time + timedelta(seconds=i) for i in range(n_samples)],
            "start_time": start_time,
            "end_time": end_time,
        }
    
    def run_backtest(
        self,
        historical_data: Dict[str, Any],
    ) -> ValidationResult:
        """
        Run backtest on historical data.
        
        Args:
            historical_data: Dictionary with features, labels, returns
            
        Returns:
            ValidationResult with performance metrics
        """
        logger.info("Running backtest on historical data...")
        
        start_time = time.time()
        
        try:
            features = historical_data["features"]
            labels = historical_data["labels"]
            returns = historical_data["returns"]
            n_samples = len(labels)
            
            # Get model predictions
            xgb_signals = self._get_xgb_predictions(features)
            lstm_signals = self._get_lstm_predictions(features)
            
            # Combine signals (both must agree)
            combined_signals = np.logical_and(
                xgb_signals == 1,
                lstm_signals == 1
            ).astype(int)
            
            # Calculate metrics
            total_signals = np.sum(combined_signals)
            
            if total_signals < self.config.min_signal_count:
                logger.warning(f"Insufficient signals: {total_signals} < {self.config.min_signal_count}")
                return ValidationResult(
                    success=False,
                    validation_time=datetime.now(),
                    total_signals=total_signals,
                    error_message=f"Insufficient signals: {total_signals} < {self.config.min_signal_count}",
                    validation_hours=self.config.validation_hours,
                )
            
            # Calculate profit
            signal_returns = returns[combined_signals == 1]
            total_profit = np.sum(signal_returns)
            total_return_pct = total_profit * 100
            
            # Calculate win rate
            winning_signals = np.sum(signal_returns > 0)
            losing_signals = np.sum(signal_returns <= 0)
            win_rate = winning_signals / total_signals if total_signals > 0 else 0.0
            
            # Calculate accuracy
            correct_predictions = np.sum(combined_signals == labels)
            accuracy = correct_predictions / n_samples if n_samples > 0 else 0.0
            
            # Calculate Sharpe ratio
            if len(signal_returns) > 1:
                sharpe_ratio = np.mean(signal_returns) / np.std(signal_returns) * np.sqrt(252)
            else:
                sharpe_ratio = 0.0
            
            # Calculate max drawdown
            cumulative_returns = np.cumsum(signal_returns)
            running_max = np.maximum.accumulate(cumulative_returns)
            drawdown = cumulative_returns - running_max
            max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0.0
            
            # Calculate loss streak
            loss_streak = self._calculate_loss_streak(signal_returns)
            
            # Calculate XGBoost metrics
            xgb_correct = np.sum(xgb_signals == labels)
            xgb_precision = np.sum((xgb_signals == 1) & (labels == 1)) / np.sum(xgb_signals == 1) if np.sum(xgb_signals == 1) > 0 else 0.0
            xgb_recall = np.sum((xgb_signals == 1) & (labels == 1)) / np.sum(labels == 1) if np.sum(labels == 1) > 0 else 0.0
            
            # Calculate LSTM metrics
            lstm_correct = np.sum(lstm_signals == labels)
            lstm_accuracy = lstm_correct / n_samples if n_samples > 0 else 0.0
            
            # Determine success
            success = self._check_validation_success(
                total_profit=total_profit,
                accuracy=accuracy,
                win_rate=win_rate,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                loss_streak=loss_streak,
            )
            
            result = ValidationResult(
                success=success,
                validation_time=datetime.now(),
                total_profit=total_profit,
                total_return_pct=total_return_pct,
                accuracy=accuracy,
                win_rate=win_rate,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                total_signals=int(total_signals),
                winning_signals=int(winning_signals),
                losing_signals=int(losing_signals),
                loss_streak=loss_streak,
                xgb_precision=xgb_precision,
                xgb_recall=xgb_recall,
                lstm_accuracy=lstm_accuracy,
                validation_hours=self.config.validation_hours,
                details={
                    "xgb_signals": int(np.sum(xgb_signals)),
                    "lstm_signals": int(np.sum(lstm_signals)),
                    "combined_signals": int(total_signals),
                },
            )
            
            # Store in history
            self.validation_history.append(result)
            
            logger.info(f"Backtest complete: profit={total_profit:.4f}, accuracy={accuracy:.2%}, win_rate={win_rate:.2%}")
            
            return result
            
        except Exception as e:
            logger.error(f"Backtest failed: {e}", exc_info=True)
            return ValidationResult(
                success=False,
                validation_time=datetime.now(),
                error_message=str(e),
                validation_hours=self.config.validation_hours,
            )
    
    def _get_xgb_predictions(self, features: Dict[str, np.ndarray]) -> np.ndarray:
        """Get XGBoost predictions."""
        if self.xgb_model is None:
            # Mock predictions
            n_samples = len(features["price"])
            return (np.random.rand(n_samples) > 0.85).astype(int)
        
        # Prepare feature matrix
        feature_names = [
            "price", "price_velocity", "price_acceleration",
            "volume", "volume_surge", "volume_velocity",
            "taker_buy_sell_ratio", "order_imbalance",
            "trade_count", "avg_trade_size", "trade_size_std",
            "hurst_exponent", "ema_crossings", "mean_reversion_score",
        ]
        
        X = np.column_stack([features[name] for name in feature_names])
        
        # Get predictions
        confidence = self.xgb_model.get_confidence(X)
        signals = (confidence >= self.config.xgb_confidence_threshold).astype(int)
        
        return signals
    
    def _get_lstm_predictions(self, features: Dict[str, np.ndarray]) -> np.ndarray:
        """Get LSTM predictions."""
        if self.lstm_model is None:
            # Mock predictions
            n_samples = len(features["price"])
            return (np.random.rand(n_samples) > 0.5).astype(int)
        
        # Prepare sequences
        import torch
        
        feature_names = [
            "price_normalized", "volume_normalized", "std_dev_price",
            "velocity", "order_book_imbalance", "taker_buy_sell_ratio",
            "distance_to_target", "hurst_exponent", "ema_crossings",
            "mean_reversion_score",
        ]
        
        # Normalize features
        X = np.column_stack([features.get(name, features.get("price", np.zeros(len(features["price"])))) 
                            for name in feature_names])
        
        # Create sequences (seq_len=60)
        seq_len = 60
        n_samples = len(X) - seq_len + 1
        sequences = np.zeros((n_samples, seq_len, len(feature_names)))
        
        for i in range(n_samples):
            sequences[i] = X[i:i + seq_len]
        
        # Get predictions
        sequences_tensor = torch.FloatTensor(sequences)
        probabilities = self.lstm_model.predict_proba(sequences_tensor).numpy()
        
        # Pad to match original length
        predictions = np.zeros(len(features["price"]))
        predictions[seq_len - 1:] = (probabilities >= self.config.lstm_probability_threshold).astype(int).flatten()
        
        return predictions
    
    def _calculate_loss_streak(self, returns: np.ndarray) -> int:
        """Calculate maximum consecutive losses."""
        if len(returns) == 0:
            return 0
        
        max_streak = 0
        current_streak = 0
        
        for r in returns:
            if r <= 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak
    
    def _check_validation_success(
        self,
        total_profit: float,
        accuracy: float,
        win_rate: float,
        sharpe_ratio: float,
        max_drawdown: float,
        loss_streak: int,
    ) -> bool:
        """Check if validation meets all criteria."""
        checks = [
            ("profit", total_profit >= self.config.min_profit_threshold),
            ("accuracy", accuracy >= self.config.min_accuracy_threshold),
            ("win_rate", win_rate >= self.config.min_win_rate),
            ("sharpe_ratio", sharpe_ratio >= self.config.min_sharpe_ratio),
            ("max_drawdown", abs(max_drawdown) <= self.config.max_drawdown_threshold),
            ("loss_streak", loss_streak <= self.config.max_loss_streak),
        ]
        
        failed_checks = [name for name, passed in checks if not passed]
        
        if failed_checks:
            logger.warning(f"Validation failed checks: {failed_checks}")
            return False
        
        logger.info("All validation checks passed")
        return True
    
    def validate_model(
        self,
        lstm_model: Optional[Any] = None,
        xgb_model: Optional[Any] = None,
        hours: Optional[int] = None,
    ) -> ValidationResult:
        """
        Validate models on historical data.
        
        Args:
            lstm_model: LSTM model to validate (uses stored model if None)
            xgb_model: XGBoost model to validate (uses stored model if None)
            hours: Hours of historical data (uses config if None)
            
        Returns:
            ValidationResult with performance metrics
        """
        # Use provided models or stored models
        if lstm_model is not None:
            self.lstm_model = lstm_model
        if xgb_model is not None:
            self.xgb_model = xgb_model
        
        hours = hours or self.config.validation_hours
        
        logger.info(f"Starting model validation on {hours}h of historical data...")
        
        # Fetch historical data
        historical_data = self.fetch_historical_data(hours=hours)
        
        # Run backtest
        result = self.run_backtest(historical_data)
        
        return result
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of all validations."""
        if not self.validation_history:
            return {"total_validations": 0}
        
        successful = [v for v in self.validation_history if v.success]
        
        return {
            "total_validations": len(self.validation_history),
            "successful_validations": len(successful),
            "success_rate": len(successful) / len(self.validation_history),
            "avg_profit": np.mean([v.total_profit for v in self.validation_history]),
            "avg_accuracy": np.mean([v.accuracy for v in self.validation_history]),
            "last_validation": self.validation_history[-1].to_dict() if self.validation_history else None,
        }


# Import time for backtest timing
import time
