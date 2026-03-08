"""
RectangleLSTM Trainer Module

This module provides training utilities for the RectangleLSTM model,
including training loop, evaluation, and model persistence.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List, Union
import os

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
from torch.optim import Adam
from torch.optim.lr_scheduler import ReduceLROnPlateau

from backend.models.lstm_model import (
    RectangleLSTM,
    RectangleLSTMConfig,
    RectangleLSTMDataset,
    create_sequences,
    normalize_features,
    apply_normalization,
)


logger = logging.getLogger(__name__)


@dataclass
class TrainingMetrics:
    """Container for training metrics."""
    
    epoch: int
    train_loss: float
    val_loss: float
    train_accuracy: float
    val_accuracy: float
    learning_rate: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "epoch": self.epoch,
            "train_loss": self.train_loss,
            "val_loss": self.val_loss,
            "train_accuracy": self.train_accuracy,
            "val_accuracy": self.val_accuracy,
            "learning_rate": self.learning_rate,
            "timestamp": self.timestamp,
        }


@dataclass
class TrainingResult:
    """Container for training results."""
    
    model_path: str
    config: RectangleLSTMConfig
    best_val_loss: float
    best_val_accuracy: float
    final_train_loss: float
    final_val_loss: float
    metrics_history: List[Dict[str, Any]]
    normalization_params: Dict[str, Any]
    training_time_seconds: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_path": self.model_path,
            "config": self.config.to_dict(),
            "best_val_loss": self.best_val_loss,
            "best_val_accuracy": self.best_val_accuracy,
            "final_train_loss": self.final_train_loss,
            "final_val_loss": self.final_val_loss,
            "metrics_history": self.metrics_history,
            "normalization_params": self.normalization_params,
            "training_time_seconds": self.training_time_seconds,
            "timestamp": self.timestamp,
        }


class RectangleLSTMTrainer:
    """
    Training pipeline for RectangleLSTM model.
    
    Handles data preparation, training loop, validation, and model persistence.
    """
    
    def __init__(
        self,
        config: Optional[RectangleLSTMConfig] = None,
        device: Optional[str] = None,
        checkpoint_dir: str = "checkpoints",
    ):
        """
        Initialize the trainer.
        
        Args:
            config: Model configuration
            device: Device to use ('cuda', 'cpu', or None for auto)
            checkpoint_dir: Directory for saving checkpoints
        """
        self.config = config or RectangleLSTMConfig()
        
        # Set device
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)
        
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize model
        self.model = RectangleLSTM(self.config).to(self.device)
        
        # Loss function (BCEWithLogitsLoss for numerical stability)
        self.criterion = nn.BCEWithLogitsLoss()
        
        # Optimizer
        self.optimizer = Adam(
            self.model.parameters(),
            lr=self.config.learning_rate,
        )
        
        # Learning rate scheduler
        self.scheduler = ReduceLROnPlateau(
            self.optimizer,
            mode="min",
            factor=0.5,
            patience=5,
        )
        
        # Training state
        self.best_val_loss = float("inf")
        self.best_val_accuracy = 0.0
        self.metrics_history: List[TrainingMetrics] = []
        self.normalization_params: Optional[Dict[str, Any]] = None
    
    def prepare_data(
        self,
        features: np.ndarray,
        labels: np.ndarray,
        val_split: float = 0.2,
        normalize: bool = True,
        norm_method: str = "minmax",
    ) -> Tuple[DataLoader, DataLoader]:
        """
        Prepare data loaders for training.
        
        Args:
            features: Feature array of shape (n_samples, n_features)
            labels: Label array of shape (n_samples,)
            val_split: Validation split ratio
            normalize: Whether to normalize features
            norm_method: Normalization method
        
        Returns:
            Tuple of (train_loader, val_loader)
        """
        # Normalize features if requested
        if normalize:
            features, self.normalization_params = normalize_features(
                features, method=norm_method
            )
            logger.info(f"Normalized features using {norm_method} method")
        
        # Create dataset
        dataset = RectangleLSTMDataset(
            features=features,
            labels=labels,
            seq_len=self.config.seq_len,
        )
        
        # Split into train and validation
        val_size = int(len(dataset) * val_split)
        train_size = len(dataset) - val_size
        
        train_dataset, val_dataset = random_split(
            dataset,
            [train_size, val_size],
            generator=torch.Generator().manual_seed(42),
        )
        
        # Create data loaders
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
            num_workers=0,
            pin_memory=True if self.device.type == "cuda" else False,
        )
        
        val_loader = DataLoader(
            val_dataset,
            batch_size=self.config.batch_size,
            shuffle=False,
            num_workers=0,
            pin_memory=True if self.device.type == "cuda" else False,
        )
        
        logger.info(
            f"Created data loaders: train={len(train_dataset)}, val={len(val_dataset)}"
        )
        
        return train_loader, val_loader
    
    def train_epoch(self, train_loader: DataLoader) -> Tuple[float, float]:
        """
        Train for one epoch.
        
        Args:
            train_loader: Training data loader
        
        Returns:
            Tuple of (average loss, accuracy)
        """
        self.model.train()
        total_loss = 0.0
        correct = 0
        total = 0
        
        for batch_idx, (sequences, labels) in enumerate(train_loader):
            # Move to device
            sequences = sequences.to(self.device)
            labels = labels.to(self.device)
            
            # Forward pass
            self.optimizer.zero_grad()
            logits, _ = self.model(sequences)
            loss = self.criterion(logits, labels)
            
            # Backward pass
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            
            self.optimizer.step()
            
            # Track metrics
            total_loss += loss.item() * sequences.size(0)
            predictions = (torch.sigmoid(logits) >= 0.5).float()
            correct += (predictions == labels).sum().item()
            total += labels.size(0)
        
        avg_loss = total_loss / total
        accuracy = correct / total
        
        return avg_loss, accuracy
    
    def validate(self, val_loader: DataLoader) -> Tuple[float, float]:
        """
        Validate the model.
        
        Args:
            val_loader: Validation data loader
        
        Returns:
            Tuple of (average loss, accuracy)
        """
        self.model.eval()
        total_loss = 0.0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for sequences, labels in val_loader:
                # Move to device
                sequences = sequences.to(self.device)
                labels = labels.to(self.device)
                
                # Forward pass
                logits, _ = self.model(sequences)
                loss = self.criterion(logits, labels)
                
                # Track metrics
                total_loss += loss.item() * sequences.size(0)
                predictions = (torch.sigmoid(logits) >= 0.5).float()
                correct += (predictions == labels).sum().item()
                total += labels.size(0)
        
        avg_loss = total_loss / total
        accuracy = correct / total
        
        return avg_loss, accuracy
    
    def train(
        self,
        features: np.ndarray,
        labels: np.ndarray,
        val_split: float = 0.2,
        epochs: Optional[int] = None,
        early_stopping_patience: int = 10,
        normalize: bool = True,
        norm_method: str = "minmax",
    ) -> TrainingResult:
        """
        Train the model.
        
        Args:
            features: Feature array of shape (n_samples, n_features)
            labels: Label array of shape (n_samples,)
            val_split: Validation split ratio
            epochs: Number of epochs (overrides config)
            early_stopping_patience: Patience for early stopping
            normalize: Whether to normalize features
            norm_method: Normalization method
        
        Returns:
            TrainingResult with training metrics
        """
        import time
        start_time = time.time()
        
        # Use provided epochs or config
        num_epochs = epochs or self.config.epochs
        
        # Prepare data
        train_loader, val_loader = self.prepare_data(
            features=features,
            labels=labels,
            val_split=val_split,
            normalize=normalize,
            norm_method=norm_method,
        )
        
        logger.info(f"Starting training for {num_epochs} epochs on {self.device}")
        
        # Training loop
        epochs_without_improvement = 0
        
        for epoch in range(1, num_epochs + 1):
            # Train
            train_loss, train_acc = self.train_epoch(train_loader)
            
            # Validate
            val_loss, val_acc = self.validate(val_loader)
            
            # Get current learning rate
            current_lr = self.optimizer.param_groups[0]["lr"]
            
            # Record metrics
            metrics = TrainingMetrics(
                epoch=epoch,
                train_loss=train_loss,
                val_loss=val_loss,
                train_accuracy=train_acc,
                val_accuracy=val_acc,
                learning_rate=current_lr,
            )
            self.metrics_history.append(metrics)
            
            # Log progress
            logger.info(
                f"Epoch {epoch}/{num_epochs} - "
                f"Train Loss: {train_loss:.4f}, Acc: {train_acc:.4f} - "
                f"Val Loss: {val_loss:.4f}, Acc: {val_acc:.4f} - "
                f"LR: {current_lr:.6f}"
            )
            
            # Update learning rate
            self.scheduler.step(val_loss)
            
            # Check for improvement
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self.best_val_accuracy = val_acc
                epochs_without_improvement = 0
                
                # Save best model
                self._save_checkpoint(epoch, is_best=True)
                logger.info(f"New best model saved with val_loss: {val_loss:.4f}")
            else:
                epochs_without_improvement += 1
            
            # Early stopping
            if epochs_without_improvement >= early_stopping_patience:
                logger.info(
                    f"Early stopping triggered after {epoch} epochs "
                    f"({early_stopping_patience} epochs without improvement)"
                )
                break
        
        training_time = time.time() - start_time
        
        # Save final model
        model_path = self._save_checkpoint(epoch, is_best=False)
        
        # Create result
        result = TrainingResult(
            model_path=str(model_path),
            config=self.config,
            best_val_loss=self.best_val_loss,
            best_val_accuracy=self.best_val_accuracy,
            final_train_loss=train_loss,
            final_val_loss=val_loss,
            metrics_history=[m.to_dict() for m in self.metrics_history],
            normalization_params=self.normalization_params or {},
            training_time_seconds=training_time,
        )
        
        logger.info(
            f"Training completed in {training_time:.2f}s - "
            f"Best Val Loss: {self.best_val_loss:.4f}, "
            f"Best Val Acc: {self.best_val_accuracy:.4f}"
        )
        
        return result
    
    def _save_checkpoint(self, epoch: int, is_best: bool = False) -> Path:
        """
        Save a model checkpoint.
        
        Args:
            epoch: Current epoch
            is_best: Whether this is the best model so far
        
        Returns:
            Path to saved checkpoint
        """
        checkpoint = {
            "epoch": epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "scheduler_state_dict": self.scheduler.state_dict(),
            "best_val_loss": self.best_val_loss,
            "best_val_accuracy": self.best_val_accuracy,
            "config": self.config.to_dict(),
            "normalization_params": self.normalization_params,
        }
        
        if is_best:
            path = self.checkpoint_dir / "best_model.pt"
        else:
            path = self.checkpoint_dir / f"model_epoch_{epoch}.pt"
        
        torch.save(checkpoint, path)
        return path


def train_model(
    features: np.ndarray,
    labels: np.ndarray,
    config: Optional[RectangleLSTMConfig] = None,
    val_split: float = 0.2,
    epochs: Optional[int] = None,
    checkpoint_dir: str = "checkpoints",
    device: Optional[str] = None,
) -> TrainingResult:
    """
    Train a RectangleLSTM model.
    
    Convenience function that creates a trainer and trains the model.
    
    Args:
        features: Feature array of shape (n_samples, n_features)
        labels: Label array of shape (n_samples,)
        config: Model configuration
        val_split: Validation split ratio
        epochs: Number of epochs
        checkpoint_dir: Directory for checkpoints
        device: Device to use
    
    Returns:
        TrainingResult with training metrics
    """
    trainer = RectangleLSTMTrainer(
        config=config,
        device=device,
        checkpoint_dir=checkpoint_dir,
    )
    
    return trainer.train(
        features=features,
        labels=labels,
        val_split=val_split,
        epochs=epochs,
    )


def predict(
    model: RectangleLSTM,
    features: np.ndarray,
    seq_len: int = 60,
    normalization_params: Optional[Dict[str, Any]] = None,
    device: Optional[str] = None,
) -> np.ndarray:
    """
    Make predictions with a trained model.
    
    Args:
        model: Trained RectangleLSTM model
        features: Feature array of shape (n_samples, n_features)
        seq_len: Sequence length
        normalization_params: Normalization parameters from training
        device: Device to use
    
    Returns:
        Probability predictions of shape (n_valid_samples,)
    """
    # Set device
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Apply normalization if provided
    if normalization_params:
        features = apply_normalization(features, normalization_params)
    
    # Create sequences
    sequences, _ = create_sequences(features, np.zeros(len(features)), seq_len)
    
    # Convert to tensor
    sequences_tensor = torch.FloatTensor(sequences).to(device)
    
    # Make predictions
    model.eval()
    model.to(device)
    
    with torch.no_grad():
        probs = model.predict_proba(sequences_tensor)
    
    return probs.cpu().numpy().flatten()


def save_model(
    model: RectangleLSTM,
    config: RectangleLSTMConfig,
    path: str,
    normalization_params: Optional[Dict[str, Any]] = None,
):
    """
    Save a trained model to disk.
    
    Args:
        model: Trained RectangleLSTM model
        config: Model configuration
        path: Path to save the model
        normalization_params: Normalization parameters from training
    """
    checkpoint = {
        "model_state_dict": model.state_dict(),
        "config": config.to_dict(),
        "normalization_params": normalization_params,
    }
    
    torch.save(checkpoint, path)
    logger.info(f"Model saved to {path}")


def load_model(
    path: str,
    device: Optional[str] = None,
) -> Tuple[RectangleLSTM, RectangleLSTMConfig, Optional[Dict[str, Any]]]:
    """
    Load a trained model from disk.
    
    Args:
        path: Path to the saved model
        device: Device to load the model to
    
    Returns:
        Tuple of (model, config, normalization_params)
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    checkpoint = torch.load(path, map_location=device)
    
    config = RectangleLSTMConfig.from_dict(checkpoint["config"])
    model = RectangleLSTM(config)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    
    normalization_params = checkpoint.get("normalization_params")
    
    logger.info(f"Model loaded from {path}")
    
    return model, config, normalization_params


def generate_mock_data(
    n_samples: int = 1000,
    n_features: int = 10,
    positive_ratio: float = 0.3,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate mock data for testing.
    
    Args:
        n_samples: Number of samples to generate
        n_features: Number of features
        positive_ratio: Ratio of positive samples
        seed: Random seed
    
    Returns:
        Tuple of (features, labels)
    """
    np.random.seed(seed)
    
    # Generate random features
    features = np.random.randn(n_samples, n_features).astype(np.float32)
    
    # Generate labels with specified ratio
    n_positive = int(n_samples * positive_ratio)
    labels = np.zeros(n_samples, dtype=np.float32)
    labels[:n_positive] = 1.0
    np.random.shuffle(labels)
    
    # Add some signal to positive samples
    for i in range(n_samples):
        if labels[i] == 1:
            # Add pattern signal
            features[i, 0] += 0.5  # Price signal
            features[i, 2] -= 0.3  # std_dev signal
            features[i, 4] += 0.4  # order_book signal
    
    return features, labels


def main():
    """CLI entry point for training."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Train RectangleLSTM model")
    parser.add_argument(
        "--epochs", type=int, default=50, help="Number of training epochs"
    )
    parser.add_argument(
        "--batch-size", type=int, default=32, help="Batch size"
    )
    parser.add_argument(
        "--lr", type=float, default=0.001, help="Learning rate"
    )
    parser.add_argument(
        "--seq-len", type=int, default=60, help="Sequence length"
    )
    parser.add_argument(
        "--val-split", type=float, default=0.2, help="Validation split"
    )
    parser.add_argument(
        "--checkpoint-dir", type=str, default="checkpoints",
        help="Checkpoint directory"
    )
    parser.add_argument(
        "--device", type=str, default=None, help="Device (cuda/cpu)"
    )
    parser.add_argument(
        "--mock-data", action="store_true", help="Use mock data for testing"
    )
    parser.add_argument(
        "--mock-samples", type=int, default=1000, help="Number of mock samples"
    )
    parser.add_argument(
        "--output", type=str, default="training_result.json",
        help="Output file for training results"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Create config
    config = RectangleLSTMConfig(
        seq_len=args.seq_len,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        epochs=args.epochs,
    )
    
    # Get data
    if args.mock_data:
        logger.info(f"Generating {args.mock_samples} mock samples")
        features, labels = generate_mock_data(n_samples=args.mock_samples)
    else:
        # TODO: Load real data from database
        logger.warning("No real data available, using mock data")
        features, labels = generate_mock_data(n_samples=args.mock_samples)
    
    # Train
    result = train_model(
        features=features,
        labels=labels,
        config=config,
        val_split=args.val_split,
        epochs=args.epochs,
        checkpoint_dir=args.checkpoint_dir,
        device=args.device,
    )
    
    # Save results
    with open(args.output, "w") as f:
        json.dump(result.to_dict(), f, indent=2)
    
    logger.info(f"Training results saved to {args.output}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("TRAINING SUMMARY")
    print("=" * 60)
    print(f"Best Validation Loss: {result.best_val_loss:.4f}")
    print(f"Best Validation Accuracy: {result.best_val_accuracy:.4f}")
    print(f"Final Training Loss: {result.final_train_loss:.4f}")
    print(f"Final Validation Loss: {result.final_val_loss:.4f}")
    print(f"Training Time: {result.training_time_seconds:.2f}s")
    print(f"Model saved to: {result.model_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
