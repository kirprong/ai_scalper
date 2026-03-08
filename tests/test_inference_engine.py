"""
Tests for Inference Engine.

This module tests the async inference engine for XGBoost and LSTM predictions.
"""

import pytest
import asyncio
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from backend.inference import (
    InferenceEngine,
    InferenceConfig,
    PredictionRequest,
    PredictionResult,
)


class TestPredictionRequest:
    """Tests for PredictionRequest dataclass."""
    
    def test_create_request(self):
        """Test creating a prediction request."""
        features = {
            "price": 50000.0,
            "volume": 100.0,
            "taker_buy_sell_ratio": 1.5,
        }
        
        request = PredictionRequest(
            request_id="test_1",
            timestamp=datetime.now(),
            features=features,
        )
        
        assert request.request_id == "test_1"
        assert request.features == features
        assert request.sequence is None
    
    def test_create_request_with_sequence(self):
        """Test creating a request with LSTM sequence."""
        features = {"price": 50000.0}
        sequence = np.random.randn(60, 10)  # 60 bars, 10 features
        
        request = PredictionRequest(
            request_id="test_2",
            timestamp=datetime.now(),
            features=features,
            sequence=sequence,
        )
        
        assert request.sequence is not None
        assert request.sequence.shape == (60, 10)
    
    def test_request_serialization(self):
        """Test request serialization to dict."""
        features = {"price": 50000.0}
        sequence = np.array([[1.0, 2.0], [3.0, 4.0]])
        
        request = PredictionRequest(
            request_id="test_3",
            timestamp=datetime(2026, 3, 8, 12, 0, 0),
            features=features,
            sequence=sequence,
        )
        
        # Serialize
        request_dict = request.to_dict()
        
        assert request_dict["request_id"] == "test_3"
        assert request_dict["features"] == features
        assert request_dict["sequence"] == [[1.0, 2.0], [3.0, 4.0]]
        
        # Deserialize
        request2 = PredictionRequest.from_dict(request_dict)
        
        assert request2.request_id == request.request_id
        assert request2.features == request.features
        np.testing.assert_array_equal(request2.sequence, request.sequence)


class TestPredictionResult:
    """Tests for PredictionResult dataclass."""
    
    def test_create_result(self):
        """Test creating a prediction result."""
        result = PredictionResult(
            request_id="test_1",
            timestamp=datetime.now(),
            prediction_time_ms=15.5,
            xgb_confidence=0.92,
            xgb_signal=1,
            lstm_probability=0.75,
            lstm_signal=1,
            combined_signal=1,
            combined_confidence=0.835,
        )
        
        assert result.request_id == "test_1"
        assert result.prediction_time_ms == 15.5
        assert result.xgb_confidence == 0.92
        assert result.xgb_signal == 1
        assert result.lstm_probability == 0.75
        assert result.lstm_signal == 1
        assert result.combined_signal == 1
        assert result.combined_confidence == 0.835
    
    def test_result_with_error(self):
        """Test creating a result with error."""
        result = PredictionResult(
            request_id="test_2",
            timestamp=datetime.now(),
            prediction_time_ms=0.0,
            error="Model not loaded",
        )
        
        assert result.error == "Model not loaded"
        assert result.xgb_confidence is None
    
    def test_result_serialization(self):
        """Test result serialization to dict."""
        result = PredictionResult(
            request_id="test_3",
            timestamp=datetime(2026, 3, 8, 12, 0, 0),
            prediction_time_ms=12.3,
            xgb_confidence=0.88,
            xgb_signal=1,
        )
        
        # Serialize
        result_dict = result.to_dict()
        
        assert result_dict["request_id"] == "test_3"
        assert result_dict["prediction_time_ms"] == 12.3
        assert result_dict["xgb_confidence"] == 0.88
        assert result_dict["xgb_signal"] == 1
        
        # Deserialize
        result2 = PredictionResult.from_dict(result_dict)
        
        assert result2.request_id == result.request_id
        assert result2.prediction_time_ms == result.prediction_time_ms
        assert result2.xgb_confidence == result.xgb_confidence


class TestInferenceConfig:
    """Tests for InferenceConfig."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = InferenceConfig()
        
        assert config.max_latency_ms == 20.0
        assert config.xgb_confidence_threshold == 0.85
        assert config.lstm_probability_threshold == 0.5
        assert config.queue_maxsize == 1000
        assert len(config.feature_names) == 14
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = InferenceConfig(
            max_latency_ms=15.0,
            xgb_confidence_threshold=0.90,
            xgb_model_path="custom/model.json",
        )
        
        assert config.max_latency_ms == 15.0
        assert config.xgb_confidence_threshold == 0.90
        assert config.xgb_model_path == "custom/model.json"


class TestInferenceEngine:
    """Tests for InferenceEngine."""
    
    @pytest.mark.asyncio
    async def test_engine_lifecycle(self):
        """Test engine start and stop."""
        config = InferenceConfig(
            xgb_model_path="nonexistent.json",
            lstm_model_path="nonexistent.pt",
        )
        
        engine = InferenceEngine(config)
        
        # Start
        await engine.start()
        assert engine.is_running
        
        # Stop
        await engine.stop()
        assert not engine.is_running
    
    @pytest.mark.asyncio
    async def test_engine_context_manager(self):
        """Test engine as context manager."""
        config = InferenceConfig(
            xgb_model_path="nonexistent.json",
            lstm_model_path="nonexistent.pt",
        )
        
        async with InferenceEngine(config) as engine:
            assert engine.is_running
        
        assert not engine.is_running
    
    @pytest.mark.asyncio
    async def test_predict_without_start(self):
        """Test prediction without starting engine."""
        engine = InferenceEngine()
        
        with pytest.raises(RuntimeError, match="not running"):
            await engine.predict({"price": 50000.0})
    
    @pytest.mark.asyncio
    async def test_predict_with_mock_models(self):
        """Test prediction with mocked models."""
        config = InferenceConfig(
            xgb_model_path="checkpoints/lead_xgboost.json",
            lstm_model_path="checkpoints/best_model.pt",
        )
        
        # Mock the worker process
        with patch('backend.inference.engine.Process') as mock_process_class:
            # Setup mock process
            mock_process = MagicMock()
            mock_process_class.return_value = mock_process
            mock_process.pid = 12345
            mock_process.is_alive.return_value = True
            
            # Setup mock queues
            with patch('backend.inference.engine.Queue') as mock_queue_class:
                mock_request_queue = MagicMock()
                mock_response_queue = MagicMock()
                
                # Return different queues on each call
                mock_queue_class.side_effect = [mock_request_queue, mock_response_queue]
                
                # Mock response
                mock_response_queue.get.return_value = {
                    "request_id": "req_1_123",
                    "timestamp": datetime.now().isoformat(),
                    "prediction_time_ms": 12.5,
                    "xgb_confidence": 0.92,
                    "xgb_signal": 1,
                    "lstm_probability": None,
                    "lstm_signal": None,
                    "combined_signal": 1,
                    "combined_confidence": 0.92,
                    "error": None,
                }
                
                # Start engine
                engine = InferenceEngine(config)
                await engine.start()
                
                # Make prediction
                features = {
                    "price": 50000.0,
                    "volume": 100.0,
                    "taker_buy_sell_ratio": 1.5,
                }
                
                result = await engine.predict(features)
                
                # Verify result
                assert result.request_id == "req_1_123"
                assert result.prediction_time_ms == 12.5
                assert result.xgb_confidence == 0.92
                assert result.xgb_signal == 1
                assert result.combined_signal == 1
                
                # Stop engine
                await engine.stop()
    
    @pytest.mark.asyncio
    async def test_predict_with_sequence(self):
        """Test prediction with LSTM sequence."""
        config = InferenceConfig(
            xgb_model_path="checkpoints/lead_xgboost.json",
            lstm_model_path="checkpoints/best_model.pt",
        )
        
        # Mock the worker process
        with patch('backend.inference.engine.Process') as mock_process_class:
            mock_process = MagicMock()
            mock_process_class.return_value = mock_process
            mock_process.pid = 12345
            mock_process.is_alive.return_value = True
            
            with patch('backend.inference.engine.Queue') as mock_queue_class:
                mock_request_queue = MagicMock()
                mock_response_queue = MagicMock()
                mock_queue_class.side_effect = [mock_request_queue, mock_response_queue]
                
                # Mock response with both models
                mock_response_queue.get.return_value = {
                    "request_id": "req_1_456",
                    "timestamp": datetime.now().isoformat(),
                    "prediction_time_ms": 18.2,
                    "xgb_confidence": 0.88,
                    "xgb_signal": 1,
                    "lstm_probability": 0.76,
                    "lstm_signal": 1,
                    "combined_signal": 1,
                    "combined_confidence": 0.82,
                    "error": None,
                }
                
                engine = InferenceEngine(config)
                await engine.start()
                
                # Make prediction with sequence
                features = {"price": 50000.0}
                sequence = np.random.randn(60, 10)
                
                result = await engine.predict(features, sequence=sequence)
                
                # Verify result
                assert result.lstm_probability == 0.76
                assert result.lstm_signal == 1
                assert result.combined_signal == 1
                assert result.combined_confidence == 0.82
                
                await engine.stop()


class TestInferenceWorker:
    """Tests for InferenceWorker."""
    
    def test_worker_import(self):
        """Test that worker can be imported."""
        from backend.inference.worker import InferenceWorker
        
        assert InferenceWorker is not None
        assert hasattr(InferenceWorker, 'run')


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
