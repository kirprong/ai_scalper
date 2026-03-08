"""
Test script for Inference Engine.

This script tests the inference engine with mock data to verify:
- Latency < 20ms per prediction
- Correct signal generation
- Both XGBoost and LSTM predictions
"""

import asyncio
import numpy as np
from datetime import datetime

from backend.inference import InferenceEngine, InferenceConfig


async def test_inference_latency():
    """Test inference latency with mock features."""
    
    print("=" * 60)
    print("Inference Engine Latency Test")
    print("=" * 60)
    
    # Configure engine
    config = InferenceConfig(
        xgb_model_path="checkpoints/lead_xgboost.json",
        lstm_model_path="checkpoints/best_model.pt",
        max_latency_ms=20.0,
    )
    
    # Test features
    features = {
        "price": 50000.0,
        "price_velocity": 0.5,
        "price_acceleration": 0.01,
        "volume": 100.0,
        "volume_surge": 1.2,
        "volume_velocity": 0.3,
        "taker_buy_sell_ratio": 1.5,
        "order_imbalance": 0.2,
        "trade_count": 50,
        "avg_trade_size": 2.0,
        "trade_size_std": 0.5,
        "hurst_exponent": 0.45,
        "ema_crossings": 12,
        "mean_reversion_score": 0.65,
    }
    
    # Test sequence for LSTM
    sequence = np.random.randn(60, 10)  # 60 bars, 10 features
    
    print(f"\nConfiguration:")
    print(f"  Max latency: {config.max_latency_ms}ms")
    print(f"  XGB threshold: {config.xgb_confidence_threshold}")
    print(f"  LSTM threshold: {config.lstm_probability_threshold}")
    
    print(f"\nStarting inference engine...")
    
    try:
        async with InferenceEngine(config) as engine:
            print(f"Engine started (running: {engine.is_running})")
            
            # Run multiple predictions
            num_tests = 10
            latencies = []
            
            print(f"\nRunning {num_tests} predictions...")
            print("-" * 60)
            
            for i in range(num_tests):
                # Make prediction
                result = await engine.predict(features, sequence=sequence)
                
                latencies.append(result.prediction_time_ms)
                
                # Print result
                print(f"\n[{i+1}] Request: {result.request_id}")
                print(f"  Latency: {result.prediction_time_ms:.2f}ms")
                
                if result.error:
                    print(f"  Error: {result.error}")
                else:
                    print(f"  XGB: confidence={result.xgb_confidence:.3f}, signal={result.xgb_signal}")
                    print(f"  LSTM: probability={result.lstm_probability:.3f}, signal={result.lstm_signal}")
                    print(f"  Combined: signal={result.combined_signal}, confidence={result.combined_confidence:.3f}")
            
            # Calculate statistics
            print("\n" + "=" * 60)
            print("Performance Summary:")
            print("=" * 60)
            print(f"  Total predictions: {num_tests}")
            print(f"  Average latency: {np.mean(latencies):.2f}ms")
            print(f"  Min latency: {np.min(latencies):.2f}ms")
            print(f"  Max latency: {np.max(latencies):.2f}ms")
            print(f"  Std deviation: {np.std(latencies):.2f}ms")
            
            # Check if latency meets target
            avg_latency = np.mean(latencies)
            if avg_latency < config.max_latency_ms:
                print(f"\n✅ PASS: Average latency {avg_latency:.2f}ms < {config.max_latency_ms}ms target")
            else:
                print(f"\n❌ FAIL: Average latency {avg_latency:.2f}ms > {config.max_latency_ms}ms target")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def test_mock_prediction():
    """Test prediction with mock models (no real models needed)."""
    
    print("\n" + "=" * 60)
    print("Mock Prediction Test (no real models)")
    print("=" * 60)
    
    # Configure with non-existent models
    config = InferenceConfig(
        xgb_model_path="nonexistent_model.json",
        lstm_model_path="nonexistent_model.pt",
    )
    
    features = {"price": 50000.0}
    
    print("\nStarting engine with mock models...")
    
    try:
        async with InferenceEngine(config) as engine:
            print(f"Engine started (running: {engine.is_running})")
            
            # Make prediction
            result = await engine.predict(features)
            
            print(f"\nPrediction result:")
            print(f"  Request ID: {result.request_id}")
            print(f"  Latency: {result.prediction_time_ms:.2f}ms")
            
            if result.error:
                print(f"  Error: {result.error}")
            else:
                print(f"  XGB signal: {result.xgb_signal}")
                print(f"  LSTM signal: {result.lstm_signal}")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("INFERENCE ENGINE TEST SUITE")
    print("=" * 60)
    
    # Run tests
    asyncio.run(test_mock_prediction())
    asyncio.run(test_inference_latency())
    
    print("\n" + "=" * 60)
    print("Test suite complete")
    print("=" * 60)
