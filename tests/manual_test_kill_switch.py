"""
Manual test for Hardware Kill-Switch.

This script demonstrates the Ctrl+C (SIGINT) handler behavior.

Run: python tests/manual_test_kill_switch.py
Then press Ctrl+C to trigger the kill switch.
"""

import asyncio
import logging
from unittest.mock import Mock, AsyncMock

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from backend.safety.kill_switch import install_kill_switch
from backend.safety.panic_switch import PanicSwitch, PanicSwitchConfig


async def main():
    """Run manual test."""
    print("\n" + "="*60)
    print("HARDWARE KILL-SWITCH MANUAL TEST")
    print("="*60)
    print("\nPress Ctrl+C to trigger the kill switch...\n")
    
    # Create mock Polymarket client
    mock_client = Mock()
    mock_client.cancel_all_orders = AsyncMock(return_value={"cancelled": 5})
    mock_client.close = AsyncMock()
    
    # Create real PanicSwitch
    panic_config = PanicSwitchConfig(
        enable_telegram=False  # Disable Telegram for test
    )
    panic_switch = PanicSwitch(panic_config)
    
    # Install kill switch
    kill_switch = install_kill_switch(
        polymarket_client=mock_client,
        panic_switch=panic_switch
    )
    
    # Register some test positions
    kill_switch.register_position("BTC_TARGET")
    kill_switch.register_position("ETH_TARGET")
    
    print(f"✅ Kill switch installed")
    print(f"✅ Registered {len(kill_switch._active_positions)} test positions")
    print(f"\nSystem is running. Press Ctrl+C to test emergency shutdown...\n")
    
    # Keep running until interrupted
    try:
        while True:
            await asyncio.sleep(1)
            print(".", end="", flush=True)
    except asyncio.CancelledError:
        print("\n\nAsyncio cancelled - shutting down...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # This should be caught by the kill switch
        pass
