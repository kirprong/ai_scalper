"""
Console UI Entry Point - Rich Terminal Dashboard

Run: python console_ui/main.py
"""

import asyncio
import random
from datetime import datetime
from .dashboard import Dashboard


async def mock_data_generator():
    """
    Mock data generator for testing the dashboard.
    In production, this would fetch real data from the trading system.
    """
    # Simulate changing values
    return {
        'pnl': {
            'realized': random.uniform(-50, 150),
            'unrealized': random.uniform(-20, 50),
            'trades': random.randint(10, 50),
            'win_rate': random.uniform(0.55, 0.75)
        },
        'ml': {
            'lstm_status': random.choice(['ACTIVE', 'IDLE', 'TRAINING']),
            'xgb_status': random.choice(['ACTIVE', 'IDLE']),
            'lstm_conf': random.uniform(0.6, 0.95),
            'xgb_conf': random.uniform(0.7, 0.98),
            'accuracy': random.uniform(0.72, 0.88),
            'last_pred': datetime.now()
        },
        'trading': {
            'volume': random.uniform(5000, 25000),
            'avg_size': random.uniform(50, 200),
            'drawdown': random.uniform(0.01, 0.08),
            'sharpe': random.uniform(0.8, 2.5),
            'positions': random.randint(0, 3),
            'orders': random.randint(0, 5)
        },
        'system': {
            'status': 'RUNNING',
            'uptime': random.randint(3600, 7200),
            'cpu': random.uniform(15, 45),
            'memory': random.uniform(30, 60),
            'latency': random.uniform(5, 25),
            'errors': random.randint(0, 2),
            'last_error': None if random.random() > 0.3 else 'Connection timeout'
        }
    }


async def main():
    """Main entry point for console UI"""
    dashboard = Dashboard()
    
    # Set up data callback
    dashboard.set_update_callback(mock_data_generator)
    
    # Print welcome message
    print("\n" + "="*60)
    print("  AI LEAD SCALPER - Terminal Dashboard v1.0")
    print("="*60)
    print("\n  Starting dashboard...")
    print("  Press Ctrl+C to exit\n")
    
    try:
        # Run dashboard with 1 second refresh
        await dashboard.run_async(refresh_rate=1.0)
    except KeyboardInterrupt:
        print("\n\n  Dashboard stopped by user.")
        dashboard.stop()


if __name__ == "__main__":
    asyncio.run(main())
