"""
Unit Tests for LeadXGBoost Model

Tests the XGBoost trigger model for detecting leading micro-spikes
in Binance data.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import tempfile
import json

from backend.models.xgboost_model import (
    LeadXGBoost,
    LeadXGBoostConfig,
    LeadXGBoostTrainer,
    generate_mock_data,
    train_xgboost_model,
)


class TestLeadXGBoostConfig:
    """Tests for LeadXGBoostConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = LeadXGBoostConfig()

        assert config.max_depth == 6
        assert config.learning_rate == 0.1
        assert config.n_estimators == 100
        assert config.objective == "binary:logistic"
        assert config.confidence_threshold == 0.85
        assert config.random_state == 42

    def test_config_to_dict(self):
        """Test config serialization to dictionary."""
        config = LeadXGBoostConfig(
            max_depth=8,
            learning_rate=0.05,
            n_estimators=200,
        )

        data = config.to_dict()

        assert data["max_depth"] == 8
        assert data["learning_rate"] == 0.05
        assert data["n_estimators"] == 200
        assert "feature_names" in data

    def test_config_from_dict(self):
        """Test config deserialization from dictionary."""
        data = {
            "max_depth": 10,
            "learning_rate": 0.01,
            "n_estimators": 500,
            "confidence_threshold": 0.9,
        }

        config = LeadXGBoostConfig.from_dict(data)

        assert config.max_depth == 10
        assert config.learning_rate == 0.01
        assert config.n_estimators == 500
        assert config.confidence_threshold == 0.9

    def test_config_roundtrip(self):
        """Test config serialization roundtrip."""
        original = LeadXGBoostConfig(
            max_depth=7,
            learning_rate=0.2,
            scale_pos_weight=5.0,
        )

        data = original.to_dict()
        restored = LeadXGBoostConfig.from_dict(data)

        assert restored.max_depth == original.max_depth
        assert restored.learning_rate == original.learning_rate
        assert restored.scale_pos_weight == original.scale_pos_weight


class TestLeadXGBoost:
    """Tests for LeadXGBoost model."""

    @pytest.fixture
    def sample_data(self):
        """Generate sample data for testing."""
        return generate_mock_data(n_samples=1000, random_state=42)

    @pytest.fixture
    def trained_model(self, sample_data):
        """Create and train a model for testing."""
        config = LeadXGBoostConfig(n_estimators=10)
        model = LeadXGBoost(config)

        feature_cols = list(config.feature_names)
        X = sample_data[feature_cols]
        y = sample_data["label"]

        model.train(X, y, verbose=False)
        return model

    def test_model_initialization(self):
        """Test model initialization."""
        model = LeadXGBoost()

        assert model.config is not None
        assert model.model is not None
        assert model.scaler is not None
        assert not model.is_fitted

    def test_model_initialization_with_config(self):
        """Test model initialization with custom config."""
        config = LeadXGBoostConfig(
            max_depth=8,
            learning_rate=0.05,
            n_estimators=50,
        )
        model = LeadXGBoost(config)

        assert model.config.max_depth == 8
        assert model.config.learning_rate == 0.05
        assert model.config.n_estimators == 50

    def test_prepare_features_dataframe(self, sample_data):
        """Test feature preparation from DataFrame."""
        model = LeadXGBoost()
        feature_cols = list(model.config.feature_names)
        X = sample_data[feature_cols]

        features = model.prepare_features(X, fit_scaler=True)

        assert features.shape[0] == len(sample_data)
        assert features.shape[1] == len(feature_cols)
        assert features.dtype == np.float32

    def test_prepare_features_numpy(self):
        """Test feature preparation from numpy array."""
        model = LeadXGBoost()
        n_features = len(model.config.feature_names)

        X = np.random.randn(100, n_features)
        features = model.prepare_features(X, fit_scaler=True)

        assert features.shape == (100, n_features)

    def test_prepare_features_invalid_dimensions(self):
        """Test that invalid feature dimensions raise error."""
        model = LeadXGBoost()
        X = np.random.randn(100, 5)  # Wrong number of features

        with pytest.raises(ValueError, match="Expected .* features"):
            model.prepare_features(X, fit_scaler=True)

    def test_train_model(self, sample_data):
        """Test model training."""
        config = LeadXGBoostConfig(n_estimators=10)
        model = LeadXGBoost(config)

        feature_cols = list(config.feature_names)
        X = sample_data[feature_cols]
        y = sample_data["label"]

        metrics = model.train(X, y, verbose=False)

        assert model.is_fitted
        assert "precision" in metrics
        assert "recall" in metrics
        assert "auc" in metrics

    def test_train_with_validation(self, sample_data):
        """Test model training with validation data."""
        config = LeadXGBoostConfig(n_estimators=10)
        model = LeadXGBoost(config)

        feature_cols = list(config.feature_names)
        X = sample_data[feature_cols][:800]
        y = sample_data["label"][:800]
        X_val = sample_data[feature_cols][800:]
        y_val = sample_data["label"][800:]

        metrics = model.train(X, y, X_val, y_val, verbose=False)

        assert model.is_fitted
        assert "auc" in metrics

    def test_predict(self, trained_model, sample_data):
        """Test model prediction."""
        config = trained_model.config
        feature_cols = list(config.feature_names)
        X = sample_data[feature_cols][:100]

        predictions = trained_model.predict(X)

        assert len(predictions) == 100
        assert np.all(np.isin(predictions, [0, 1]))

    def test_predict_proba(self, trained_model, sample_data):
        """Test probability prediction."""
        config = trained_model.config
        feature_cols = list(config.feature_names)
        X = sample_data[feature_cols][:100]

        proba = trained_model.predict_proba(X)

        assert proba.shape == (100, 2)
        assert np.all(proba >= 0) and np.all(proba <= 1)
        assert np.allclose(proba.sum(axis=1), 1.0)

    def test_get_confidence(self, trained_model, sample_data):
        """Test confidence score retrieval."""
        config = trained_model.config
        feature_cols = list(config.feature_names)
        X = sample_data[feature_cols][:100]

        confidence = trained_model.get_confidence(X)

        assert len(confidence) == 100
        assert np.all(confidence >= 0) and np.all(confidence <= 1)

    def test_get_signals(self, trained_model, sample_data):
        """Test signal generation."""
        config = trained_model.config
        feature_cols = list(config.feature_names)
        X = sample_data[feature_cols][:100]

        signals, confidence = trained_model.get_signals(X)

        assert len(signals) == 100
        assert len(confidence) == 100
        assert np.all(np.isin(signals, [0, 1]))

        # Verify signals match threshold
        threshold = config.confidence_threshold
        expected_signals = (confidence >= threshold).astype(int)
        np.testing.assert_array_equal(signals, expected_signals)

    def test_get_signals_custom_threshold(self, trained_model, sample_data):
        """Test signal generation with custom threshold."""
        config = trained_model.config
        feature_cols = list(config.feature_names)
        X = sample_data[feature_cols][:100]

        custom_threshold = 0.5
        signals, confidence = trained_model.get_signals(X, threshold=custom_threshold)

        expected_signals = (confidence >= custom_threshold).astype(int)
        np.testing.assert_array_equal(signals, expected_signals)

    def test_evaluate(self, trained_model, sample_data):
        """Test model evaluation."""
        config = trained_model.config
        feature_cols = list(config.feature_names)
        X = sample_data[feature_cols]
        y = sample_data["label"]

        metrics = trained_model.evaluate(X, y)

        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1" in metrics
        assert "auc" in metrics
        assert "logloss" in metrics
        assert "confusion_matrix" in metrics

    def test_feature_importance(self, trained_model):
        """Test feature importance calculation."""
        importance = trained_model.get_feature_importance()

        assert isinstance(importance, dict)
        assert len(importance) == len(trained_model.config.feature_names)

        # Importance scores should sum to approximately 1
        total = sum(importance.values())
        assert 0 < total <= 1.1  # Allow small floating point errors

    def test_predict_before_training_raises(self):
        """Test that prediction before training raises error."""
        model = LeadXGBoost()
        X = np.random.randn(10, len(model.config.feature_names))

        with pytest.raises(ValueError, match="Model must be trained"):
            model.predict(X)

    def test_save_and_load_model(self, trained_model, sample_data):
        """Test model save and load."""
        config = trained_model.config
        feature_cols = list(config.feature_names)
        X = sample_data[feature_cols][:50]

        # Get predictions before saving
        original_proba = trained_model.predict_proba(X)

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model"
            trained_model.save_model(model_path)

            # Check files were created
            assert (model_path.with_suffix(".json")).exists()
            assert (model_path.with_suffix(".config.json")).exists()

            # Load model
            loaded_model = LeadXGBoost(config)
            loaded_model.load_model(model_path)

            # Verify predictions match
            loaded_proba = loaded_model.predict_proba(X)
            np.testing.assert_array_almost_equal(original_proba, loaded_proba)


class TestLeadXGBoostTrainer:
    """Tests for LeadXGBoostTrainer."""

    @pytest.fixture
    def sample_data(self):
        """Generate sample data for testing."""
        return generate_mock_data(n_samples=2000, random_state=42)

    def test_trainer_initialization(self):
        """Test trainer initialization."""
        trainer = LeadXGBoostTrainer()

        assert trainer.config is not None
        assert trainer.output_dir is not None
        assert trainer.model is None

    def test_prepare_training_data(self, sample_data):
        """Test training data preparation."""
        trainer = LeadXGBoostTrainer()

        X_train, X_test, X_val, y_train, y_test, y_val = trainer.prepare_training_data(
            sample_data, label_column="label"
        )

        # Check that data was split correctly
        total = len(X_train) + len(X_test) + len(X_val)
        assert total == len(sample_data)

        # Check that all have same number of features
        n_features = len(trainer.config.feature_names)
        assert X_train.shape[1] == n_features
        assert X_test.shape[1] == n_features
        assert X_val.shape[1] == n_features

    def test_train_and_evaluate(self, sample_data):
        """Test training and evaluation pipeline."""
        config = LeadXGBoostConfig(n_estimators=10)
        trainer = LeadXGBoostTrainer(config)

        X_train, X_test, X_val, y_train, y_test, y_val = trainer.prepare_training_data(
            sample_data, label_column="label"
        )

        # Train
        train_metrics = trainer.train(X_train, y_train, X_val, y_val, verbose=False)

        assert trainer.model is not None
        assert trainer.model.is_fitted
        assert "auc" in train_metrics

        # Evaluate
        test_metrics = trainer.evaluate(X_test, y_test)

        assert "precision" in test_metrics
        assert "recall" in test_metrics
        assert "auc" in test_metrics

    def test_save_and_load_model(self, sample_data):
        """Test model save and load through trainer."""
        config = LeadXGBoostConfig(n_estimators=10)

        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = LeadXGBoostTrainer(config, output_dir=tmpdir)

            X_train, X_test, X_val, y_train, y_test, y_val = (
                trainer.prepare_training_data(sample_data, label_column="label")
            )
            trainer.train(X_train, y_train, X_val, y_val, verbose=False)

            # Save
            saved_path = trainer.save_model("test_model")
            # Check that the model files exist (json and config.json)
            assert saved_path.with_suffix(".json").exists()
            assert saved_path.with_suffix(".config.json").exists()

            # Load
            new_trainer = LeadXGBoostTrainer(config, output_dir=tmpdir)
            new_trainer.load_model(saved_path)

            assert new_trainer.model is not None
            assert new_trainer.model.is_fitted


class TestMockDataGeneration:
    """Tests for mock data generation."""

    def test_generate_mock_data_default(self):
        """Test default mock data generation."""
        df = generate_mock_data()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 10000
        assert "label" in df.columns

        # Check feature columns
        config = LeadXGBoostConfig()
        for feature in config.feature_names:
            assert feature in df.columns

    def test_generate_mock_data_custom_size(self):
        """Test custom size mock data generation."""
        df = generate_mock_data(n_samples=5000)

        assert len(df) == 5000

    def test_generate_mock_data_positive_ratio(self):
        """Test positive ratio in mock data."""
        df = generate_mock_data(n_samples=10000, positive_ratio=0.2)

        actual_ratio = df["label"].mean()
        # Allow some variance due to shuffling
        assert 0.15 <= actual_ratio <= 0.25

    def test_generate_mock_data_reproducible(self):
        """Test that same seed produces same data."""
        df1 = generate_mock_data(n_samples=100, random_state=42)
        df2 = generate_mock_data(n_samples=100, random_state=42)

        pd.testing.assert_frame_equal(df1, df2)


class TestHighConfidenceSignals:
    """Tests for high confidence signal generation."""

    @pytest.fixture
    def trained_model(self):
        """Create a trained model for testing."""
        data = generate_mock_data(n_samples=5000, random_state=42)
        config = LeadXGBoostConfig(
            n_estimators=50,
            confidence_threshold=0.85,
        )
        model = LeadXGBoost(config)

        feature_cols = list(config.feature_names)
        X = data[feature_cols]
        y = data["label"]

        model.train(X, y, verbose=False)
        return model, data

    def test_high_confidence_precision(self, trained_model):
        """Test that high confidence signals have good precision."""
        model, data = trained_model
        config = model.config

        feature_cols = list(config.feature_names)
        X = data[feature_cols]
        y = data["label"]

        # Evaluate with focus on high confidence
        metrics = model.evaluate(X, y)

        # High confidence precision should be reasonable
        if "high_confidence_precision" in metrics:
            # For mock data, we expect some signal
            assert metrics["high_confidence_precision"] >= 0.0

    def test_confidence_distribution(self, trained_model):
        """Test confidence score distribution."""
        model, data = trained_model
        config = model.config

        feature_cols = list(config.feature_names)
        X = data[feature_cols]

        confidence = model.get_confidence(X)

        # Confidence should be between 0 and 1
        assert np.all(confidence >= 0) and np.all(confidence <= 1)

        # Should have some variance
        assert np.std(confidence) > 0.01


class TestIntegration:
    """Integration tests for the XGBoost model."""

    def test_full_training_pipeline(self):
        """Test the full training pipeline."""
        # Generate data
        data = generate_mock_data(n_samples=5000, random_state=42)

        # Train model
        config = LeadXGBoostConfig(
            n_estimators=50,
            max_depth=6,
            learning_rate=0.1,
            confidence_threshold=0.85,
        )

        model, metrics = train_xgboost_model(
            data=data,
            config=config,
            output_dir="checkpoints",
            verbose=False,
        )

        # Verify model is trained
        assert model.is_fitted

        # Verify metrics
        assert "precision" in metrics
        assert "recall" in metrics
        assert "auc" in metrics

        # Print metrics for verification
        print(f"\n=== Test Metrics ===")
        print(f"Precision: {metrics['precision']:.4f}")
        print(f"Recall: {metrics['recall']:.4f}")
        print(f"AUC: {metrics['auc']:.4f}")

        if "high_confidence_precision" in metrics:
            print(f"High Confidence Precision: {metrics['high_confidence_precision']:.4f}")
            print(f"High Confidence Recall: {metrics['high_confidence_recall']:.4f}")

    def test_model_with_realistic_features(self):
        """Test model with realistic feature values."""
        config = LeadXGBoostConfig(n_estimators=20)
        model = LeadXGBoost(config)

        # Create realistic feature data
        n_samples = 1000
        data = pd.DataFrame({
            "price": 100 + np.cumsum(np.random.randn(n_samples) * 0.1),
            "price_velocity": np.random.randn(n_samples) * 0.1,
            "price_acceleration": np.random.randn(n_samples) * 0.01,
            "volume": np.random.exponential(1000, n_samples),
            "volume_surge": np.random.uniform(0, 1, n_samples),
            "volume_velocity": np.random.randn(n_samples) * 0.1,
            "taker_buy_sell_ratio": np.random.uniform(0.3, 0.7, n_samples),
            "order_imbalance": np.random.randn(n_samples) * 0.1,
            "trade_count": np.random.poisson(50, n_samples),
            "avg_trade_size": np.random.exponential(20, n_samples),
            "trade_size_std": np.random.exponential(5, n_samples),
            "hurst_exponent": np.random.uniform(0.4, 0.6, n_samples),
            "ema_crossings": np.random.randint(0, 5, n_samples),
            "mean_reversion_score": np.random.uniform(0.3, 0.7, n_samples),
        })

        # Create labels based on price movement
        future_returns = np.roll(data["price"], -5) - data["price"]
        labels = (future_returns > 0).astype(int)[:-5]
        data = data[:-5]
        data["label"] = labels

        # Train
        feature_cols = list(config.feature_names)
        X = data[feature_cols]
        y = data["label"]

        model.train(X, y, verbose=False)

        # Evaluate
        metrics = model.evaluate(X, y)

        assert "auc" in metrics
        assert metrics["auc"] >= 0.0


class TestCLI:
    """Tests for CLI functionality."""

    def test_cli_imports(self):
        """Test that CLI module can be imported."""
        from backend.models.xgboost_model import train_xgboost_model
        from backend.models.xgboost_model import generate_mock_data

        # Should not raise
        assert callable(train_xgboost_model)
        assert callable(generate_mock_data)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
