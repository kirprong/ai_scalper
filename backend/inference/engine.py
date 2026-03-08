"""
Inference Engine - Async Predict Loop.

This module provides async inference capabilities for running XGBoost and LSTM
predictions in a separate process with low latency (<20ms).

Architecture:
- Main process: Receives market data ticks
- Inference process: Runs model predictions
- Communication: multiprocessing.Queue for low-latency IPC

Performance:
- Target latency: <20ms per prediction
- Async design: Non-blocking predictions
- Process isolation: Models don't block main event loop
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
import asyncio
import multiprocessing as mp
from multiprocessing import Process, Queue
import logging
import time
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class PredictionRequest:
    """Request for model prediction."""
    
    request_id: str
    timestamp: datetime
    features: Dict[str, float]
    sequence: Optional[np.ndarray] = None  # For LSTM (seq_len, features)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "features": self.features,
            "sequence": self.sequence.tolist() if self.sequence is not None else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PredictionRequest":
        """Create from dictionary."""
        return cls(
            request_id=data["request_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            features=data["features"],
            sequence=np.array(data["sequence"]) if data.get("sequence") else None,
        )


@dataclass
class PredictionResult:
    """Result from model prediction."""
    
    request_id: str
    timestamp: datetime
    prediction_time_ms: float
    
    # XGBoost results
    xgb_confidence: Optional[float] = None
    xgb_signal: Optional[int] = None
    
    # LSTM results
    lstm_probability: Optional[float] = None
    lstm_signal: Optional[int] = None
    
    # Combined signal
    combined_signal: Optional[int] = None
    combined_confidence: Optional[float] = None
    
    # Error handling
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "prediction_time_ms": self.prediction_time_ms,
            "xgb_confidence": self.xgb_confidence,
            "xgb_signal": self.xgb_signal,
            "lstm_probability": self.lstm_probability,
            "lstm_signal": self.lstm_signal,
            "combined_signal": self.combined_signal,
            "combined_confidence": self.combined_confidence,
            "error": self.error,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PredictionResult":
        """Create from dictionary."""
        return cls(
            request_id=data["request_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            prediction_time_ms=data["prediction_time_ms"],
            xgb_confidence=data.get("xgb_confidence"),
            xgb_signal=data.get("xgb_signal"),
            lstm_probability=data.get("lstm_probability"),
            lstm_signal=data.get("lstm_signal"),
            combined_signal=data.get("combined_signal"),
            combined_confidence=data.get("combined_confidence"),
            error=data.get("error"),
        )


@dataclass
class InferenceConfig:
    """Configuration for inference engine."""
    
    # Model paths
    xgb_model_path: str = "checkpoints/lead_xgboost.json"
    lstm_model_path: str = "checkpoints/best_model.pt"
    
    # Performance settings
    max_latency_ms: float = 20.0
    batch_size: int = 1  # Process one tick at a time
    
    # Signal thresholds
    xgb_confidence_threshold: float = 0.85
    lstm_probability_threshold: float = 0.5
    
    # Queue settings
    queue_maxsize: int = 1000
    
    # Feature names (must match model training)
    feature_names: List[str] = field(default_factory=lambda: [
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
    ])


class InferenceEngine:
    """
    Async inference engine for running XGBoost and LSTM predictions.
    
    This engine runs in a separate process to avoid blocking the main event loop.
    It uses multiprocessing.Queue for low-latency inter-process communication.
    
    Usage:
        async with InferenceEngine(config) as engine:
            result = await engine.predict(features)
    """
    
    def __init__(self, config: Optional[InferenceConfig] = None):
        """Initialize inference engine."""
        self.config = config or InferenceConfig()
        
        # Queues for IPC
        self.request_queue: Optional[Queue] = None
        self.response_queue: Optional[Queue] = None
        
        # Worker process
        self.worker_process: Optional[Process] = None
        
        # State
        self._running = False
        self._request_counter = 0
        
        # Callbacks
        self._on_prediction: Optional[Callable] = None
    
    async def __aenter__(self) -> "InferenceEngine":
        """Start the inference engine."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Stop the inference engine."""
        await self.stop()
    
    async def start(self):
        """Start the inference worker process."""
        if self._running:
            logger.warning("Inference engine already running")
            return
        
        logger.info("Starting inference engine...")
        
        # Create queues
        self.request_queue = Queue(maxsize=self.config.queue_maxsize)
        self.response_queue = Queue(maxsize=self.config.queue_maxsize)
        
        # Import worker here to avoid circular imports
        from .worker import InferenceWorker
        
        # Start worker process
        self.worker_process = Process(
            target=InferenceWorker.run,
            args=(
                self.request_queue,
                self.response_queue,
                self.config.xgb_model_path,
                self.config.lstm_model_path,
                self.config.xgb_confidence_threshold,
                self.config.lstm_probability_threshold,
            ),
            daemon=True,
        )
        self.worker_process.start()
        
        self._running = True
        logger.info(f"Inference engine started (PID: {self.worker_process.pid})")
    
    async def stop(self):
        """Stop the inference worker process."""
        if not self._running:
            return
        
        logger.info("Stopping inference engine...")
        
        # Send stop signal
        if self.request_queue:
            self.request_queue.put(None)
        
        # Wait for worker to finish
        if self.worker_process:
            self.worker_process.join(timeout=5.0)
            if self.worker_process.is_alive():
                logger.warning("Worker process did not stop gracefully, terminating...")
                self.worker_process.terminate()
        
        self._running = False
        logger.info("Inference engine stopped")
    
    async def predict(
        self,
        features: Dict[str, float],
        sequence: Optional[np.ndarray] = None,
    ) -> PredictionResult:
        """
        Run prediction on features.
        
        Args:
            features: Feature dictionary for XGBoost
            sequence: Sequence array for LSTM (seq_len, features)
        
        Returns:
            PredictionResult with confidence scores and signals
        """
        if not self._running:
            raise RuntimeError("Inference engine not running")
        
        # Create request
        self._request_counter += 1
        request = PredictionRequest(
            request_id=f"req_{self._request_counter}_{time.time_ns()}",
            timestamp=datetime.now(),
            features=features,
            sequence=sequence,
        )
        
        # Send request
        start_time = time.time()
        self.request_queue.put(request.to_dict())
        
        # Wait for response (with timeout)
        timeout = self.config.max_latency_ms / 1000.0 * 2  # 2x buffer
        try:
            # Use asyncio to wait for queue (non-blocking)
            loop = asyncio.get_event_loop()
            response_dict = await loop.run_in_executor(
                None,
                lambda: self.response_queue.get(timeout=timeout),
            )
            
            result = PredictionResult.from_dict(response_dict)
            
            # Check latency
            latency_ms = (time.time() - start_time) * 1000
            if latency_ms > self.config.max_latency_ms:
                logger.warning(f"Prediction latency {latency_ms:.2f}ms exceeds target {self.config.max_latency_ms}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return PredictionResult(
                request_id=request.request_id,
                timestamp=request.timestamp,
                prediction_time_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )
    
    def on_prediction(self, callback: Callable[[PredictionResult], None]):
        """Set callback for prediction results."""
        self._on_prediction = callback
    
    @property
    def is_running(self) -> bool:
        """Check if engine is running."""
        return self._running and self.worker_process is not None and self.worker_process.is_alive()
