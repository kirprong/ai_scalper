"""
Unit Tests for RectangleLSTM Model

Tests for the LSTM model architecture, dataset, and training utilities.
"""

import pytest
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from backend.models.lstm_model import (
    RectangleLSTM,
    RectangleLSTMConfig,
    RectangleLSTMDataset,
    create_sequences,
    normalize_features,
    apply_normalization,
)

from backend.models.trainer import (
    RectangleLSTMTrainer,
    TrainingMetrics,
    TrainingResult,
    train_model,
    predict,
    save_model,
    load_model,
    generate_mock_data,
)


class TestRectangleLSTMConfig:
    """Tests for RectangleLSTMConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = RectangleLSTMConfig()
        
        assert config.input_size == 10
        assert config.seq_len == 60
        assert config.hidden_size_1 == 128
        assert config.hidden_size_2 == 64
        assert config.num_layers == 2
        assert config.dropout == 0.2
        assert config.fc_hidden_size == 32
        assert config.batch_size == 32
        assert config.learning_rate == 0.001
        assert config.epochs == 50
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = RectangleLSTMConfig(
            input_size=15,
            seq_len=30,
            hidden_size_1=256,
            hidden_size_2=128,
            dropout=0.3,
            batch_size=64,
            learning_rate=0.0005,
            epochs=100,
        )
        
        assert config.input_size == 15
        assert config.seq_len == 30
        assert config.hidden_size_1 == 256
        assert config.hidden_size_2 == 128
        assert config.dropout == 0.3
        assert config.batch_size == 64
        assert config.learning_rate == 0.0005
        assert config.epochs == 100
    
    def test_config_to_dict(self):
        """Test config serialization to dictionary."""
        config = RectangleLSTMConfig(
            input_size=12,
            seq_len=45,
            hidden_size_1=100,
        )
        
        d = config.to_dict()
        
        assert isinstance(d, dict)
        assert d["input_size"] == 12
        assert d["seq_len"] == 45
        assert d["hidden_size_1"] == 100
        assert "feature_names" in d
    
    def test_config_from_dict(self):
        """Test config deserialization from dictionary."""
        d = {
            "input_size": 8,
            "seq_len": 50,
            "hidden_size_1": 200,
            "hidden_size_2": 100,
            "dropout": 0.25,
        }
        
        config = RectangleLSTMConfig.from_dict(d)
        
        assert config.input_size == 8
        assert config.seq_len == 50
        assert config.hidden_size_1 == 200
        assert config.hidden_size_2 == 100
        assert config.dropout == 0.25


class TestRectangleLSTM:
    """Tests for RectangleLSTM model."""
    
    def test_model_initialization(self):
        """Test model initialization."""
        model = RectangleLSTM()
        
        assert isinstance(model, nn.Module)
        assert hasattr(model, "lstm1")
        assert hasattr(model, "lstm2")
        assert hasattr(model, "fc1")
        assert hasattr(model, "fc2")
    
    def test_model_forward_pass(self):
        """Test forward pass through the model."""
        config = RectangleLSTMConfig(batch_size=16, seq_len=60)
        model = RectangleLSTM(config)
        
        # Create dummy input
        batch_size = 16
        x = torch.randn(batch_size, config.seq_len, config.input_size)
        
        # Forward pass
        logits, hidden = model(x)
        
        # Check output shape
        assert logits.shape == (batch_size, 1)
        assert isinstance(hidden, tuple)
        assert len(hidden) == 2  # (h_n, c_n)
    
    def test_model_predict_proba(self):
        """Test probability prediction."""
        model = RectangleLSTM()
        model.eval()
        
        batch_size = 8
        x = torch.randn(batch_size, 60, 10)
        
        probs = model.predict_proba(x)
        
        assert probs.shape == (batch_size, 1)
        assert torch.all(probs >= 0) and torch.all(probs <= 1)
    
    def test_model_predict_binary(self):
        """Test binary prediction."""
        model = RectangleLSTM()
        model.eval()
        
        batch_size = 8
        x = torch.randn(batch_size, 60, 10)
        
        predictions = model.predict(x, threshold=0.5)
        
        assert predictions.shape == (batch_size, 1)
        assert torch.all((predictions == 0) | (predictions == 1))
    
    def test_model_with_custom_config(self):
        """Test model with custom configuration."""
        config = RectangleLSTMConfig(
            input_size=15,
            seq_len=30,
            hidden_size_1=256,
            hidden_size_2=128,
            fc_hidden_size=64,
        )
        model = RectangleLSTM(config)
        
        x = torch.randn(4, 30, 15)
        logits, _ = model(x)
        
        assert logits.shape == (4, 1)
    
    def test_model_gradient_flow(self):
        """Test that gradients flow through the model."""
        model = RectangleLSTM()
        model.train()
        
        x = torch.randn(4, 60, 10, requires_grad=True)
        logits, _ = model(x)
        
        # Compute loss and backward
        loss = logits.sum()
        loss.backward()
        
        # Check that gradients exist
        assert x.grad is not None
        assert x.grad.shape == x.shape


class TestRectangleLSTMDataset:
    """Tests for RectangleLSTMDataset."""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing."""
        n_samples = 200
        n_features = 10
        features = np.random.randn(n_samples, n_features).astype(np.float32)
        labels = np.random.randint(0, 2, n_samples).astype(np.float32)
        return features, labels
    
    def test_dataset_creation(self, sample_data):
        """Test dataset creation."""
        features, labels = sample_data
        dataset = RectangleLSTMDataset(features, labels, seq_len=60)
        
        assert len(dataset) == 200 - 60 + 1  # 141 valid sequences
    
    def test_dataset_getitem(self, sample_data):
        """Test dataset __getitem__ method."""
        features, labels = sample_data
        dataset = RectangleLSTMDataset(features, labels, seq_len=60)
        
        sequence, label = dataset[0]
        
        assert sequence.shape == (60, 10)
        assert label.shape == (1,)
        assert isinstance(sequence, torch.Tensor)
        assert isinstance(label, torch.Tensor)
    
    def test_dataset_sequence_indices(self, sample_data):
        """Test that sequences are correctly indexed."""
        features, labels = sample_data
        seq_len = 60
        dataset = RectangleLSTMDataset(features, labels, seq_len=seq_len)
        
        # Get first sequence
        sequence, label = dataset[0]
        
        # The label should correspond to the last element of the sequence
        end_idx = dataset.valid_indices[0]
        expected_label = labels[end_idx]
        
        assert label.item() == expected_label
    
    def test_dataset_too_short(self):
        """Test that dataset raises error for too short data."""
        features = np.random.randn(50, 10).astype(np.float32)
        labels = np.random.randint(0, 2, 50).astype(np.float32)
        
        with pytest.raises(ValueError, match="Not enough samples"):
            RectangleLSTMDataset(features, labels, seq_len=60)
    
    def test_dataset_mismatched_lengths(self):
        """Test that dataset raises error for mismatched lengths."""
        features = np.random.randn(100, 10).astype(np.float32)
        labels = np.random.randint(0, 2, 80).astype(np.float32)
        
        with pytest.raises(ValueError, match="same length"):
            RectangleLSTMDataset(features, labels, seq_len=60)


class TestSequenceCreation:
    """Tests for sequence creation utilities."""
    
    def test_create_sequences(self):
        """Test sequence creation."""
        n_samples = 100
        n_features = 10
        features = np.random.randn(n_samples, n_features).astype(np.float32)
        labels = np.random.randint(0, 2, n_samples).astype(np.float32)
        
        seq_len = 20
        sequences, seq_labels = create_sequences(features, labels, seq_len)
        
        expected_n_sequences = n_samples - seq_len + 1
        assert sequences.shape == (expected_n_sequences, seq_len, n_features)
        assert seq_labels.shape == (expected_n_sequences,)
    
    def test_create_sequences_too_short(self):
        """Test sequence creation with insufficient data."""
        features = np.random.randn(50, 10).astype(np.float32)
        labels = np.random.randint(0, 2, 50).astype(np.float32)
        
        with pytest.raises(ValueError, match="Not enough samples"):
            create_sequences(features, labels, seq_len=60)


class TestNormalization:
    """Tests for feature normalization."""
    
    def test_minmax_normalization(self):
        """Test min-max normalization."""
        features = np.random.randn(100, 10).astype(np.float32) * 10 + 5
        
        normalized, params = normalize_features(features, method="minmax")
        
        assert normalized.shape == features.shape
        assert np.all(normalized >= 0) and np.all(normalized <= 1)
        assert params["method"] == "minmax"
    
    def test_zscore_normalization(self):
        """Test z-score normalization."""
        features = np.random.randn(100, 10).astype(np.float32) * 10 + 5
        
        normalized, params = normalize_features(features, method="zscore")
        
        assert normalized.shape == features.shape
        assert params["method"] == "zscore"
        # Check approximate zero mean and unit std
        assert np.abs(np.mean(normalized)) < 0.1
    
    def test_robust_normalization(self):
        """Test robust normalization."""
        features = np.random.randn(100, 10).astype(np.float32) * 10 + 5
        
        normalized, params = normalize_features(features, method="robust")
        
        assert normalized.shape == features.shape
        assert params["method"] == "robust"
    
    def test_apply_normalization(self):
        """Test applying normalization parameters."""
        features = np.random.randn(100, 10).astype(np.float32) * 10 + 5
        
        normalized, params = normalize_features(features, method="minmax")
        
        # Apply same normalization
        new_features = np.random.randn(50, 10).astype(np.float32) * 10 + 5
        normalized_new = apply_normalization(new_features, params)
        
        assert normalized_new.shape == new_features.shape
    
    def test_invalid_normalization_method(self):
        """Test that invalid method raises error."""
        features = np.random.randn(100, 10).astype(np.float32)
        
        with pytest.raises(ValueError, match="Unknown normalization method"):
            normalize_features(features, method="invalid")


class TestRectangleLSTMTrainer:
    """Tests for RectangleLSTMTrainer."""
    
    @pytest.fixture
    def mock_data(self):
        """Create mock data for testing."""
        return generate_mock_data(n_samples=500, n_features=10, seed=42)
    
    def test_trainer_initialization(self):
        """Test trainer initialization."""
        trainer = RectangleLSTMTrainer()
        
        assert trainer.model is not None
        assert trainer.criterion is not None
        assert trainer.optimizer is not None
        assert trainer.scheduler is not None
    
    def test_trainer_prepare_data(self, mock_data):
        """Test data preparation."""
        features, labels = mock_data
        trainer = RectangleLSTMTrainer()
        
        train_loader, val_loader = trainer.prepare_data(
            features, labels, val_split=0.2, normalize=True
        )
        
        assert isinstance(train_loader, DataLoader)
        assert isinstance(val_loader, DataLoader)
        assert trainer.normalization_params is not None
    
    def test_trainer_train_epoch(self, mock_data):
        """Test training for one epoch."""
        features, labels = mock_data
        config = RectangleLSTMConfig(epochs=1, batch_size=32)
        trainer = RectangleLSTMTrainer(config)
        
        train_loader, val_loader = trainer.prepare_data(features, labels)
        
        loss, acc = trainer.train_epoch(train_loader)
        
        assert isinstance(loss, float)
        assert isinstance(acc, float)
        assert loss >= 0
        assert 0 <= acc <= 1
    
    def test_trainer_validate(self, mock_data):
        """Test validation."""
        features, labels = mock_data
        trainer = RectangleLSTMTrainer()
        
        train_loader, val_loader = trainer.prepare_data(features, labels)
        
        loss, acc = trainer.validate(val_loader)
        
        assert isinstance(loss, float)
        assert isinstance(acc, float)
        assert loss >= 0
        assert 0 <= acc <= 1
    
    def test_trainer_full_training(self, mock_data):
        """Test full training loop."""
        features, labels = mock_data
        config = RectangleLSTMConfig(epochs=3, batch_size=32)
        trainer = RectangleLSTMTrainer(config)
        
        result = trainer.train(
            features, labels,
            epochs=3,
            early_stopping_patience=5,
        )
        
        assert isinstance(result, TrainingResult)
        assert result.best_val_loss < float("inf")
        assert len(result.metrics_history) > 0
        assert result.training_time_seconds > 0


class TestTrainingFunctions:
    """Tests for training utility functions."""
    
    def test_train_model_function(self):
        """Test train_model convenience function."""
        features, labels = generate_mock_data(n_samples=300, seed=42)
        config = RectangleLSTMConfig(epochs=2, batch_size=32)
        
        result = train_model(
            features, labels,
            config=config,
            epochs=2,
            val_split=0.2,
        )
        
        assert isinstance(result, TrainingResult)
        assert result.config.epochs == 2
    
    def test_predict_function(self):
        """Test predict function."""
        features, labels = generate_mock_data(n_samples=200, seed=42)
        
        # Train a quick model
        config = RectangleLSTMConfig(epochs=2, batch_size=32)
        trainer = RectangleLSTMTrainer(config)
        trainer.train(features, labels, epochs=2)
        
        # Make predictions
        probs = predict(
            trainer.model,
            features,
            seq_len=config.seq_len,
            normalization_params=trainer.normalization_params,
        )
        
        assert probs.shape[0] == len(features) - config.seq_len + 1
        assert np.all(probs >= 0) and np.all(probs <= 1)
    
    def test_save_and_load_model(self, tmp_path):
        """Test model save and load."""
        features, labels = generate_mock_data(n_samples=200, seed=42)
        
        # Train
        config = RectangleLSTMConfig(epochs=2, batch_size=32)
        trainer = RectangleLSTMTrainer(config)
        trainer.prepare_data(features, labels)
        
        # Save
        model_path = str(tmp_path / "test_model.pt")
        save_model(
            trainer.model,
            config,
            model_path,
            trainer.normalization_params,
        )
        
        # Load
        loaded_model, loaded_config, loaded_params = load_model(model_path)
        
        assert isinstance(loaded_model, RectangleLSTM)
        assert loaded_config.seq_len == config.seq_len
        assert loaded_params is not None


class TestMockDataGeneration:
    """Tests for mock data generation."""
    
    def test_generate_mock_data_shape(self):
        """Test mock data shape."""
        features, labels = generate_mock_data(n_samples=100, n_features=10)
        
        assert features.shape == (100, 10)
        assert labels.shape == (100,)
    
    def test_generate_mock_data_positive_ratio(self):
        """Test positive ratio in mock data."""
        features, labels = generate_mock_data(
            n_samples=1000,
            positive_ratio=0.3,
        )
        
        positive_ratio = np.sum(labels) / len(labels)
        assert 0.25 <= positive_ratio <= 0.35  # Allow some variance
    
    def test_generate_mock_data_reproducibility(self):
        """Test reproducibility with seed."""
        features1, labels1 = generate_mock_data(n_samples=100, seed=42)
        features2, labels2 = generate_mock_data(n_samples=100, seed=42)
        
        np.testing.assert_array_equal(features1, features2)
        np.testing.assert_array_equal(labels1, labels2)


class TestTrainingMetrics:
    """Tests for TrainingMetrics dataclass."""
    
    def test_training_metrics_creation(self):
        """Test TrainingMetrics creation."""
        metrics = TrainingMetrics(
            epoch=1,
            train_loss=0.5,
            val_loss=0.6,
            train_accuracy=0.75,
            val_accuracy=0.70,
            learning_rate=0.001,
        )
        
        assert metrics.epoch == 1
        assert metrics.train_loss == 0.5
        assert metrics.val_loss == 0.6
        assert metrics.train_accuracy == 0.75
        assert metrics.val_accuracy == 0.70
        assert metrics.learning_rate == 0.001
        assert metrics.timestamp is not None
    
    def test_training_metrics_to_dict(self):
        """Test TrainingMetrics serialization."""
        metrics = TrainingMetrics(
            epoch=5,
            train_loss=0.3,
            val_loss=0.4,
            train_accuracy=0.85,
            val_accuracy=0.80,
            learning_rate=0.0005,
        )
        
        d = metrics.to_dict()
        
        assert d["epoch"] == 5
        assert d["train_loss"] == 0.3
        assert d["val_loss"] == 0.4
        assert "timestamp" in d


class TestTrainingResult:
    """Tests for TrainingResult dataclass."""
    
    def test_training_result_creation(self):
        """Test TrainingResult creation."""
        config = RectangleLSTMConfig()
        result = TrainingResult(
            model_path="/path/to/model.pt",
            config=config,
            best_val_loss=0.5,
            best_val_accuracy=0.75,
            final_train_loss=0.4,
            final_val_loss=0.5,
            metrics_history=[],
            normalization_params={},
            training_time_seconds=100.0,
        )
        
        assert result.model_path == "/path/to/model.pt"
        assert result.best_val_loss == 0.5
        assert result.best_val_accuracy == 0.75
        assert result.training_time_seconds == 100.0
    
    def test_training_result_to_dict(self):
        """Test TrainingResult serialization."""
        config = RectangleLSTMConfig()
        result = TrainingResult(
            model_path="/path/to/model.pt",
            config=config,
            best_val_loss=0.5,
            best_val_accuracy=0.75,
            final_train_loss=0.4,
            final_val_loss=0.5,
            metrics_history=[{"epoch": 1}],
            normalization_params={"method": "minmax"},
            training_time_seconds=100.0,
        )
        
        d = result.to_dict()
        
        assert d["model_path"] == "/path/to/model.pt"
        assert d["best_val_loss"] == 0.5
        assert "config" in d
        assert "metrics_history" in d


class TestModelIntegration:
    """Integration tests for the complete training pipeline."""
    
    @pytest.mark.slow
    def test_full_training_pipeline(self, tmp_path):
        """Test complete training pipeline from data to predictions."""
        # Generate data
        features, labels = generate_mock_data(n_samples=500, seed=42)
        
        # Configure and train
        config = RectangleLSTMConfig(
            epochs=5,
            batch_size=32,
            learning_rate=0.001,
        )
        
        checkpoint_dir = str(tmp_path / "checkpoints")
        trainer = RectangleLSTMTrainer(
            config=config,
            checkpoint_dir=checkpoint_dir,
        )
        
        result = trainer.train(
            features, labels,
            val_split=0.2,
            early_stopping_patience=10,
        )
        
        # Verify training completed
        assert result.best_val_loss < float("inf")
        assert len(result.metrics_history) > 0
        
        # Make predictions
        probs = predict(
            trainer.model,
            features[:100],
            seq_len=config.seq_len,
            normalization_params=trainer.normalization_params,
        )
        
        assert len(probs) > 0
        assert np.all(probs >= 0) and np.all(probs <= 1)
        
        # Save and load model
        model_path = str(tmp_path / "final_model.pt")
        save_model(trainer.model, config, model_path, trainer.normalization_params)
        
        loaded_model, loaded_config, loaded_params = load_model(model_path)
        
        # Verify loaded model works
        probs_loaded = predict(
            loaded_model,
            features[:100],
            seq_len=loaded_config.seq_len,
            normalization_params=loaded_params,
        )
        
        np.testing.assert_array_almost_equal(probs, probs_loaded, decimal=5)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
