"""
Test Hardware Kill-Switch functionality.

Tests:
1. Signal handler installation
2. Graceful shutdown procedure
3. Order cancellation
4. Position liquidation
5. Resource cleanup
"""

import asyncio
import signal
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from backend.safety.kill_switch import HardwareKillSwitch, install_kill_switch


class TestHardwareKillSwitch:
    """Test suite for Hardware Kill-Switch."""
    
    @pytest.fixture
    def mock_polymarket_client(self):
        """Create mock Polymarket client."""
        client = Mock()
        client.cancel_all_orders = AsyncMock(return_value={"cancelled": 5})
        client.close = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_panic_switch(self):
        """Create mock PanicSwitch."""
        panic = Mock()
        panic.close = AsyncMock()
        panic._status = Mock()
        panic._status.HALTED = "HALTED"
        return panic
    
    @pytest.fixture
    def kill_switch(self, mock_polymarket_client, mock_panic_switch):
        """Create HardwareKillSwitch instance."""
        return HardwareKillSwitch(
            polymarket_client=mock_polymarket_client,
            panic_switch=mock_panic_switch
        )
    
    def test_initialization(self, kill_switch):
        """Test kill switch initialization."""
        assert kill_switch.polymarket_client is not None
        assert kill_switch.panic_switch is not None
        assert kill_switch._shutting_down is False
        assert kill_switch._shutdown_complete is False
        assert len(kill_switch._active_positions) == 0
    
    def test_install_signal_handlers(self, kill_switch):
        """Test signal handler installation."""
        with patch('signal.signal') as mock_signal:
            kill_switch.install()
            
            # Verify SIGINT handler installed
            mock_signal.assert_any_call(signal.SIGINT, kill_switch._signal_handler)
            
            # Verify SIGTERM handler installed
            mock_signal.assert_any_call(signal.SIGTERM, kill_switch._signal_handler)
    
    @pytest.mark.asyncio
    async def test_cancel_all_orders(self, kill_switch, mock_polymarket_client):
        """Test order cancellation."""
        await kill_switch._cancel_all_orders()
        
        mock_polymarket_client.cancel_all_orders.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cancel_all_orders_no_client(self):
        """Test order cancellation without client."""
        kill_switch = HardwareKillSwitch()
        await kill_switch._cancel_all_orders()
        # Should not raise error
    
    @pytest.mark.asyncio
    async def test_liquidate_positions(self, kill_switch):
        """Test position liquidation."""
        # Register some positions
        kill_switch.register_position("token_1")
        kill_switch.register_position("token_2")
        
        assert len(kill_switch._active_positions) == 2
        
        await kill_switch._liquidate_positions()
        
        assert len(kill_switch._active_positions) == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_resources(self, kill_switch, mock_polymarket_client, mock_panic_switch):
        """Test resource cleanup."""
        await kill_switch._cleanup_resources()
        
        mock_polymarket_client.close.assert_called_once()
        mock_panic_switch.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, kill_switch, mock_polymarket_client, mock_panic_switch):
        """Test complete graceful shutdown procedure."""
        # Register a position
        kill_switch.register_position("test_token")
        
        await kill_switch._graceful_shutdown()
        
        # Verify all steps executed
        mock_polymarket_client.cancel_all_orders.assert_called_once()
        mock_polymarket_client.close.assert_called_once()
        mock_panic_switch.close.assert_called_once()
        
        assert kill_switch._shutdown_complete is True
        assert len(kill_switch._active_positions) == 0
    
    def test_register_position(self, kill_switch):
        """Test position registration."""
        kill_switch.register_position("token_123")
        
        assert "token_123" in kill_switch._active_positions
    
    def test_unregister_position(self, kill_switch):
        """Test position unregistration."""
        kill_switch.register_position("token_123")
        kill_switch.unregister_position("token_123")
        
        assert "token_123" not in kill_switch._active_positions
    
    def test_properties(self, kill_switch):
        """Test property accessors."""
        assert kill_switch.is_shutting_down is False
        assert kill_switch.is_shutdown_complete is False
        
        kill_switch._shutting_down = True
        assert kill_switch.is_shutting_down is True
        
        kill_switch._shutdown_complete = True
        assert kill_switch.is_shutdown_complete is True
    
    def test_install_kill_switch_convenience_function(self, mock_polymarket_client, mock_panic_switch):
        """Test convenience function for installing kill switch."""
        with patch('signal.signal'):
            kill_switch = install_kill_switch(
                polymarket_client=mock_polymarket_client,
                panic_switch=mock_panic_switch
            )
            
            assert isinstance(kill_switch, HardwareKillSwitch)
            assert kill_switch.polymarket_client == mock_polymarket_client
            assert kill_switch.panic_switch == mock_panic_switch


class TestKillSwitchIntegration:
    """Integration tests for Kill Switch."""
    
    @pytest.mark.asyncio
    async def test_full_shutdown_workflow(self):
        """Test complete shutdown workflow."""
        # Create mock components
        mock_client = Mock()
        mock_client.cancel_all_orders = AsyncMock(return_value={"cancelled": 3})
        mock_client.close = AsyncMock()
        
        mock_panic = Mock()
        mock_panic.close = AsyncMock()
        mock_panic._status = Mock()
        mock_panic._status.HALTED = "HALTED"
        
        # Create kill switch
        kill_switch = HardwareKillSwitch(
            polymarket_client=mock_client,
            panic_switch=mock_panic
        )
        
        # Register positions
        kill_switch.register_position("BTC_TARGET")
        kill_switch.register_position("ETH_TARGET")
        
        # Execute shutdown
        await kill_switch._graceful_shutdown()
        
        # Verify all operations completed
        mock_client.cancel_all_orders.assert_called_once()
        mock_client.close.assert_called_once()
        mock_panic.close.assert_called_once()
        
        assert kill_switch._shutdown_complete is True
        assert len(kill_switch._active_positions) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
