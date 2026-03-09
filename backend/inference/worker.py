"""
Inference Worker Process.

This module runs in a separate process and handles model loading and prediction.
It communicates with the main process via multiprocessing.Queue.

Performance:
- Loads models once at startup
- Runs predictions in isolation
- Reports latency metrics
- Supports hot reload without restart

Hot Reload:
- Accepts RELOAD commands via queue
- Atomically swaps models in RAM
- No prediction interruption
"""

from typing import Dict, Any, Optional
from multiprocessing import Queue
import time
import logging
import numpy as np
import threading

# Configure logging
logger = logging.getLogger(__name__)


class InferenceWorker:
    """
    Worker process for running model predictions.
    
    This worker runs in a separate process to avoid blocking the main event loop.
    It loads XGBoost and LSTM models and runs predictions on request.
    
    Hot Reload Support:
    - Accepts RELOAD commands via queue
    - Atomically swaps models in RAM
    - Tracks current model versions
    - No prediction interruption during reload
    """
    
    @staticmethod
    def run(
        request_queue: Queue,
        response_queue: Queue,
        xgb_model_path: str,
        lstm_model_path: str,
        xgb_confidence_threshold: float,
        lstm_probability_threshold: float,
    ):
        """
        Main worker loop with hot reload support.
        
        Args:
            request_queue: Queue to receive prediction requests and reload commands
            response_queue: Queue to send prediction results and reload status
            xgb_model_path: Path to XGBoost model file
            lstm_model_path: Path to LSTM model checkpoint
            xgb_confidence_threshold: Threshold for XGBoost signals
            lstm_probability_threshold: Threshold for LSTM signals
        """
        # Setup logging in worker process
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        logger.info("Inference worker starting...")
        
        # Model state with thread-safe access
        class ModelState:
            def __init__(self):
                self.xgb_model = None
                self.lstm_model = None
                self.xgb_version = None
                self.lstm_version = None
                self.lock = threading.RLock()
            
            def get_models(self):
                with self.lock:
                    return self.xgb_model, self.lstm_model
            
            def set_models(self, xgb_model, lstm_model, xgb_version=None, lstm_version=None):
                with self.lock:
                    self.xgb_model = xgb_model
                    self.lstm_model = lstm_model
                    self.xgb_version = xgb_version
                    self.lstm_version = lstm_version
        
        state = ModelState()
        
        def load_xgb_model(path: str):
            """Load XGBoost model from path."""
            import xgboost as xgb
            import os
            
            if not path or not os.path.exists(path):
                logger.warning(f"XGBoost model not found at {path}")
                return None
            
            model = xgb.XGBClassifier()
            model.load_model(path)
            logger.info(f"XGBoost model loaded from {path}")
            return model
        
        def load_lstm_model(path: str):
            """Load LSTM model from path."""
            import torch
            import os
            
            if not path or not os.path.exists(path):
                logger.warning(f"LSTM model not found at {path}")
                return None
            
            # Import LSTM model class
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            from backend.models.lstm_model import RectangleLSTM, RectangleLSTMConfig
            
            # Load checkpoint
            checkpoint = torch.load(path, map_location='cpu')
            config = RectangleLSTMConfig(**checkpoint.get('config', {}))
            model = RectangleLSTM(config)
            model.load_state_dict(checkpoint['model_state_dict'])
            model.eval()
            logger.info(f"LSTM model loaded from {path}")
            return model
        
        try:
            # Initial model loading
            xgb_model = load_xgb_model(xgb_model_path)
            lstm_model = load_lstm_model(lstm_model_path)
            state.set_models(xgb_model, lstm_model)
            
            logger.info("Inference worker ready")
            
            # Main loop
            while True:
                # Get request
                request_dict = request_queue.get()
                
                # Check for stop signal
                if request_dict is None:
                    logger.info("Received stop signal")
                    break
                
                # Check for reload command
                if isinstance(request_dict, dict) and request_dict.get("command") == "RELOAD":
                    logger.info("=" * 60)
                    logger.info("Received RELOAD command")
                    logger.info("=" * 60)
                    
                    reload_start = time.time()
                    reload_success = True
                    error_message = None
                    
                    try:
                        # Get new model paths
                        new_xgb_path = request_dict.get("xgb_model_path")
                        new_lstm_path = request_dict.get("lstm_model_path")
                        
                        # Load new models
                        new_xgb = None
                        new_lstm = None
                        
                        if new_xgb_path:
                            new_xgb = load_xgb_model(new_xgb_path)
                            if new_xgb is None:
                                reload_success = False
                                error_message = f"Failed to load XGBoost from {new_xgb_path}"
                        
                        if new_lstm_path:
                            new_lstm = load_lstm_model(new_lstm_path)
                            if new_lstm is None:
                                reload_success = False
                                error_message = f"Failed to load LSTM from {new_lstm_path}"
                        
                        # Atomic swap if both loaded successfully
                        if reload_success:
                            # Keep old models if new ones not provided
                            current_xgb, current_lstm = state.get_models()
                            
                            state.set_models(
                                xgb_model=new_xgb if new_xgb else current_xgb,
                                lstm_model=new_lstm if new_lstm else current_lstm,
                                xgb_version=request_dict.get("xgb_version"),
                                lstm_version=request_dict.get("lstm_version"),
                            )
                            
                            reload_time_ms = (time.time() - reload_start) * 1000
                            
                            logger.info(f"Models reloaded successfully in {reload_time_ms:.2f}ms")
                            logger.info(f"  XGBoost: {request_dict.get('xgb_version', 'unchanged')}")
                            logger.info(f"  LSTM: {request_dict.get('lstm_version', 'unchanged')}")
                        else:
                            logger.error(f"Reload failed: {error_message}")
                    
                    except Exception as e:
                        reload_success = False
                        error_message = str(e)
                        logger.error(f"Reload error: {e}", exc_info=True)
                    
                    # Send reload response
                    response_queue.put({
                        "command": "RELOAD_RESPONSE",
                        "success": reload_success,
                        "error_message": error_message,
                        "reload_time_ms": (time.time() - reload_start) * 1000,
                    })
                    
                    continue
                
                # Process prediction request
                start_time = time.time()
                
                try:
                    # Parse request
                    from .engine import PredictionRequest, PredictionResult
                    from datetime import datetime
                    
                    request = PredictionRequest.from_dict(request_dict)
                    
                    # Initialize result
                    result = PredictionResult(
                        request_id=request.request_id,
                        timestamp=request.timestamp,
                        prediction_time_ms=0.0,
                    )
                    
                    # Get current models (thread-safe)
                    xgb_model, lstm_model = state.get_models()
                    
                    # Run XGBoost prediction
                    if xgb_model is not None:
                        # Prepare features
                        feature_vector = np.array([
                            request.features.get(name, 0.0)
                            for name in [
                                "price", "price_velocity", "price_acceleration",
                                "volume", "volume_surge", "volume_velocity",
                                "taker_buy_sell_ratio", "order_imbalance",
                                "trade_count", "avg_trade_size", "trade_size_std",
                                "hurst_exponent", "ema_crossings", "mean_reversion_score",
                            ]
                        ]).reshape(1, -1)
                        
                        # Predict
                        confidence = xgb_model.predict_proba(feature_vector)[0, 1]
                        signal = 1 if confidence >= xgb_confidence_threshold else 0
                        
                        result.xgb_confidence = float(confidence)
                        result.xgb_signal = int(signal)
                    
                    # Run LSTM prediction
                    if lstm_model is not None and request.sequence is not None:
                        import torch
                        
                        # Prepare sequence
                        sequence_tensor = torch.FloatTensor(request.sequence).unsqueeze(0)
                        
                        # Predict
                        with torch.no_grad():
                            probability = lstm_model(sequence_tensor).item()
                        
                        signal = 1 if probability >= lstm_probability_threshold else 0
                        
                        result.lstm_probability = float(probability)
                        result.lstm_signal = int(signal)
                    
                    # Combine signals
                    if result.xgb_signal is not None and result.lstm_signal is not None:
                        # Both models must agree
                        result.combined_signal = 1 if (result.xgb_signal == 1 and result.lstm_signal == 1) else 0
                        result.combined_confidence = (result.xgb_confidence + result.lstm_probability) / 2.0
                    elif result.xgb_signal is not None:
                        result.combined_signal = result.xgb_signal
                        result.combined_confidence = result.xgb_confidence
                    elif result.lstm_signal is not None:
                        result.combined_signal = result.lstm_signal
                        result.combined_confidence = result.lstm_probability
                    
                    # Calculate latency
                    result.prediction_time_ms = (time.time() - start_time) * 1000
                    
                    # Send response
                    response_queue.put(result.to_dict())
                    
                except Exception as e:
                    logger.error(f"Prediction error: {e}", exc_info=True)
                    
                    # Send error response
                    from .engine import PredictionResult
                    error_result = PredictionResult(
                        request_id=request_dict.get("request_id", "unknown"),
                        timestamp=datetime.now(),
                        prediction_time_ms=(time.time() - start_time) * 1000,
                        error=str(e),
                    )
                    response_queue.put(error_result.to_dict())
        
        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
        
        finally:
            logger.info("Inference worker stopped")
