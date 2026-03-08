"""
Inference Worker Process.

This module runs in a separate process and handles model loading and prediction.
It communicates with the main process via multiprocessing.Queue.

Performance:
- Loads models once at startup
- Runs predictions in isolation
- Reports latency metrics
"""

from typing import Dict, Any, Optional
from multiprocessing import Queue
import time
import logging
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)


class InferenceWorker:
    """
    Worker process for running model predictions.
    
    This worker runs in a separate process to avoid blocking the main event loop.
    It loads XGBoost and LSTM models and runs predictions on request.
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
        Main worker loop.
        
        Args:
            request_queue: Queue to receive prediction requests
            response_queue: Queue to send prediction results
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
        
        # Load models
        xgb_model = None
        lstm_model = None
        
        try:
            # Load XGBoost model
            import xgboost as xgb
            import os
            
            if os.path.exists(xgb_model_path):
                xgb_model = xgb.XGBClassifier()
                xgb_model.load_model(xgb_model_path)
                logger.info(f"XGBoost model loaded from {xgb_model_path}")
            else:
                logger.warning(f"XGBoost model not found at {xgb_model_path}")
            
            # Load LSTM model
            import torch
            
            if os.path.exists(lstm_model_path):
                # Import LSTM model class
                import sys
                sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                from backend.models.lstm_model import RectangleLSTM, RectangleLSTMConfig
                
                # Load checkpoint
                checkpoint = torch.load(lstm_model_path, map_location='cpu')
                config = RectangleLSTMConfig(**checkpoint.get('config', {}))
                lstm_model = RectangleLSTM(config)
                lstm_model.load_state_dict(checkpoint['model_state_dict'])
                lstm_model.eval()
                logger.info(f"LSTM model loaded from {lstm_model_path}")
            else:
                logger.warning(f"LSTM model not found at {lstm_model_path}")
            
            logger.info("Inference worker ready")
            
            # Main loop
            while True:
                # Get request
                request_dict = request_queue.get()
                
                # Check for stop signal
                if request_dict is None:
                    logger.info("Received stop signal")
                    break
                
                # Process request
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
