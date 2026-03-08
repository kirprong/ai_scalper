"""
Unit tests for Panic Switch (TASK-028).

Tests cover:
- Recording trades
- Panic threshold detection
- System halt
- Telegram notifications
- Manual reset
- Rolling window behavior
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from backend.safety.panic_switch import (
    PanicSwitch,
    PanicSwitchConfig,
    TradeResult,
    SystemStatus,
)


class TestTradeResult:
    """Test TradeResult dataclass"""
    
    def test_trade_result_creation(self):
        """Test creating a trade result"""
        result = TradeResult(
            timestamp=datetime.now(),
            pnl=-10.50,
            symbol="BTC_TARGET",
            quantity=100.0,
            entry_price=50.0,
            exit_price=49.0,
        )
        
        assert result.pnl == -10.50
        assert result.symbol == "BTC_TARGET"
        assert result.is_loss is True
    
    def test_trade_result_is_loss(self):
        """Test is_loss property"""
        # Loss
        loss = TradeResult(timestamp=datetime.now(), pnl=-5.0)
        assert loss.is_loss is True
        
        # Win
        win = TradeResult(timestamp=datetime.now(), pnl=5.0)
        assert win.is_loss is False
        
        # Break-even
        breakeven = TradeResult(timestamp=datetime.now(), pnl=0.0)
        assert breakeven.is_loss is False


class TestPanicSwitchConfig:
    """Test PanicSwitchConfig"""
    
    def test_default_config(self):
        """Test default configuration"""
        config = PanicSwitchConfig()
        
        assert config.max_consecutive_losses == 3
        assert config.time_window_minutes == 15
        assert config.telegram_bot_token is None
        assert config.telegram_chat_id is None
        assert config.enable_telegram is True
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = PanicSwitchConfig(
            max_consecutive_losses=5,
            time_window_minutes=30,
            telegram_bot_token="test_token",
            telegram_chat_id="test_chat_id",
            enable_telegram=False,
        )
        
        assert config.max_consecutive_losses == 5
        assert config.time_window_minutes == 30
        assert config.telegram_bot_token == "test_token"
        assert config.telegram_chat_id == "test_chat_id"
        assert config.enable_telegram is False


class TestPanicSwitch:
    """Test PanicSwitch functionality"""
    
    @pytest.fixture
    def panic_switch(self):
        """Create a PanicSwitch instance for testing"""
        config = PanicSwitchConfig(
            max_consecutive_losses=3,
            time_window_minutes=15,
            enable_telegram=False,  # Disable for tests
        )
        return PanicSwitch(config)
    
    @pytest.fixture
    def panic_switch_with_telegram(self):
        """Create a PanicSwitch instance with Telegram enabled"""
        config = PanicSwitchConfig(
            max_consecutive_losses=3,
            time_window_minutes=15,
            telegram_bot_token="test_token",
            telegram_chat_id="test_chat_id",
            enable_telegram=True,
        )
        return PanicSwitch(config)
    
    def test_initialization(self, panic_switch):
        """Test PanicSwitch initialization"""
        assert panic_switch.status == SystemStatus.ACTIVE
        assert panic_switch.is_active is True
        assert panic_switch.is_halted is False
        assert len(panic_switch._losing_trades) == 0
    
    @pytest.mark.asyncio
    async def test_record_winning_trade(self, panic_switch):
        """Test recording a winning trade"""
        result = TradeResult(
            timestamp=datetime.now(),
            pnl=10.0,
        )
        
        panic_triggered = await panic_switch.record_trade(result)
        
        assert panic_triggered is False
        assert panic_switch.is_active is True
        assert len(panic_switch._losing_trades) == 0
        assert len(panic_switch._all_trades) == 1
    
    @pytest.mark.asyncio
    async def test_record_single_loss(self, panic_switch):
        """Test recording a single losing trade"""
        result = TradeResult(
            timestamp=datetime.now(),
            pnl=-10.0,
        )
        
        panic_triggered = await panic_switch.record_trade(result)
        
        assert panic_triggered is False
        assert panic_switch.is_active is True
        assert len(panic_switch._losing_trades) == 1
    
    @pytest.mark.asyncio
    async def test_record_two_losses(self, panic_switch):
        """Test recording two losing trades"""
        # First loss
        result1 = TradeResult(timestamp=datetime.now(), pnl=-10.0)
        panic_triggered = await panic_switch.record_trade(result1)
        assert panic_triggered is False
        
        # Second loss
        result2 = TradeResult(timestamp=datetime.now(), pnl=-15.0)
        panic_triggered = await panic_switch.record_trade(result2)
        assert panic_triggered is False
        
        assert panic_switch.is_active is True
        assert len(panic_switch._losing_trades) == 2
    
    @pytest.mark.asyncio
    async def test_panic_triggered_after_three_losses(self, panic_switch):
        """Test panic is triggered after 3 consecutive losses"""
        # Record 3 losses
        for i in range(3):
            result = TradeResult(
                timestamp=datetime.now(),
                pnl=-(10.0 + i),
            )
            panic_triggered = await panic_switch.record_trade(result)
            
            if i < 2:
                assert panic_triggered is False
                assert panic_switch.is_active is True
            else:
                # Third loss should trigger panic
                assert panic_triggered is True
                assert panic_switch.is_halted is True
    
    @pytest.mark.asyncio
    async def test_panic_blocks_trading(self, panic_switch):
        """Test that trading is blocked after panic"""
        # Trigger panic
        for i in range(3):
            result = TradeResult(timestamp=datetime.now(), pnl=-10.0)
            await panic_switch.record_trade(result)
        
        assert panic_switch.is_halted is True
        
        # Try to record another trade
        result = TradeResult(timestamp=datetime.now(), pnl=10.0)
        panic_triggered = await panic_switch.record_trade(result)
        
        # Should still be halted
        assert panic_triggered is True
        assert panic_switch.is_halted is True
    
    @pytest.mark.asyncio
    async def test_manual_reset(self, panic_switch):
        """Test manual reset after panic"""
        # Trigger panic
        for i in range(3):
            result = TradeResult(timestamp=datetime.now(), pnl=-10.0)
            await panic_switch.record_trade(result)
        
        assert panic_switch.is_halted is True
        
        # Reset
        await panic_switch.reset()
        
        assert panic_switch.is_active is True
        assert panic_switch.is_halted is False
        assert len(panic_switch._losing_trades) == 0
    
    @pytest.mark.asyncio
    async def test_rolling_window(self, panic_switch):
        """Test that old losses are removed from window"""
        # Record 2 losses
        old_time = datetime.now() - timedelta(minutes=20)
        
        result1 = TradeResult(timestamp=old_time, pnl=-10.0)
        await panic_switch.record_trade(result1)
        
        result2 = TradeResult(timestamp=old_time, pnl=-15.0)
        await panic_switch.record_trade(result2)
        
        assert len(panic_switch._losing_trades) == 2
        
        # Record a new loss (should clean old ones)
        result3 = TradeResult(timestamp=datetime.now(), pnl=-20.0)
        await panic_switch.record_trade(result3)
        
        # Old losses should be removed
        assert len(panic_switch._losing_trades) == 1
        assert panic_switch.is_active is True
    
    @pytest.mark.asyncio
    async def test_losses_outside_window_dont_trigger_panic(self, panic_switch):
        """Test that losses outside time window don't trigger panic"""
        # Record 3 losses, but spread over 20 minutes
        base_time = datetime.now() - timedelta(minutes=20)
        
        for i in range(3):
            result = TradeResult(
                timestamp=base_time + timedelta(minutes=i * 10),
                pnl=-10.0,
            )
            await panic_switch.record_trade(result)
        
        # Should not trigger panic (losses are outside window)
        assert panic_switch.is_active is True
    
    @pytest.mark.asyncio
    async def test_mixed_wins_and_losses(self, panic_switch):
        """Test that wins don't affect panic counter"""
        # Loss
        result1 = TradeResult(timestamp=datetime.now(), pnl=-10.0)
        await panic_switch.record_trade(result1)
        
        # Win
        result2 = TradeResult(timestamp=datetime.now(), pnl=20.0)
        await panic_switch.record_trade(result2)
        
        # Loss
        result3 = TradeResult(timestamp=datetime.now(), pnl=-15.0)
        await panic_switch.record_trade(result3)
        
        # Should have 2 losses in window
        assert len(panic_switch._losing_trades) == 2
        assert panic_switch.is_active is True
    
    def test_check_panic(self, panic_switch):
        """Test check_panic method"""
        # No losses
        assert panic_switch.check_panic() is False
        
        # Add losses manually
        for i in range(3):
            panic_switch._losing_trades.append(
                TradeResult(timestamp=datetime.now(), pnl=-10.0)
            )
        
        assert panic_switch.check_panic() is True
    
    def test_get_statistics(self, panic_switch):
        """Test get_statistics method"""
        stats = panic_switch.get_statistics()
        
        assert stats["status"] == "ACTIVE"
        assert stats["is_halted"] is False
        assert stats["losses_in_window"] == 0
        assert stats["max_losses"] == 3
        assert stats["time_window_minutes"] == 15
        assert stats["total_trades"] == 0
        assert stats["total_losses"] == 0
        assert stats["total_pnl"] == 0.0
        assert stats["win_rate"] == 0.0
    
    @pytest.mark.asyncio
    async def test_statistics_after_trades(self, panic_switch):
        """Test statistics after recording trades"""
        # Record some trades
        await panic_switch.record_trade(TradeResult(timestamp=datetime.now(), pnl=10.0))
        await panic_switch.record_trade(TradeResult(timestamp=datetime.now(), pnl=-5.0))
        await panic_switch.record_trade(TradeResult(timestamp=datetime.now(), pnl=15.0))
        await panic_switch.record_trade(TradeResult(timestamp=datetime.now(), pnl=-8.0))
        
        stats = panic_switch.get_statistics()
        
        assert stats["total_trades"] == 4
        assert stats["total_losses"] == 2
        assert stats["total_pnl"] == 12.0  # 10 - 5 + 15 - 8
        assert stats["win_rate"] == 50.0  # 2 wins out of 4


class TestTelegramNotifications:
    """Test Telegram notification functionality"""
    
    @pytest.fixture
    def panic_switch_with_mock_telegram(self):
        """Create PanicSwitch with mocked Telegram"""
        config = PanicSwitchConfig(
            max_consecutive_losses=3,
            time_window_minutes=15,
            telegram_bot_token="test_token",
            telegram_chat_id="test_chat_id",
            enable_telegram=True,
        )
        return PanicSwitch(config)
    
    @pytest.mark.asyncio
    async def test_send_telegram_notification_success(self, panic_switch_with_mock_telegram):
        """Test successful Telegram notification"""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value="OK")
            
            mock_post = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
            mock_session.return_value.__aexit__ = AsyncMock()
            mock_session.return_value.post = mock_post
            
            result = await panic_switch_with_mock_telegram.send_telegram_notification("Test message")
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_send_telegram_notification_failure(self, panic_switch_with_mock_telegram):
        """Test failed Telegram notification"""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value="Bad Request")
            
            mock_post = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
            mock_session.return_value.__aexit__ = AsyncMock()
            mock_session.return_value.post = mock_post
            
            result = await panic_switch_with_mock_telegram.send_telegram_notification("Test message")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_telegram_disabled(self):
        """Test that Telegram is skipped when disabled"""
        config = PanicSwitchConfig(
            enable_telegram=False,
        )
        panic_switch = PanicSwitch(config)
        
        result = await panic_switch.send_telegram_notification("Test message")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_telegram_no_credentials(self):
        """Test that Telegram is skipped when credentials missing"""
        config = PanicSwitchConfig(
            telegram_bot_token=None,
            telegram_chat_id=None,
            enable_telegram=True,
        )
        panic_switch = PanicSwitch(config)
        
        result = await panic_switch.send_telegram_notification("Test message")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_panic_sends_telegram_notification(self, panic_switch_with_mock_telegram):
        """Test that panic triggers Telegram notification"""
        with patch.object(
            panic_switch_with_mock_telegram,
            'send_telegram_notification',
            new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True
            
            # Trigger panic
            for i in range(3):
                result = TradeResult(timestamp=datetime.now(), pnl=-10.0)
                await panic_switch_with_mock_telegram.record_trade(result)
            
            # Should have sent notification
            mock_send.assert_called_once()
            
            # Check message content
            call_args = mock_send.call_args[0][0]
            assert "PANIC SWITCH ACTIVATED" in call_args
            assert "HALTED" in call_args
    
    @pytest.mark.asyncio
    async def test_reset_sends_telegram_notification(self, panic_switch_with_mock_telegram):
        """Test that reset sends Telegram notification"""
        with patch.object(
            panic_switch_with_mock_telegram,
            'send_telegram_notification',
            new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True
            
            # Trigger panic
            for i in range(3):
                result = TradeResult(timestamp=datetime.now(), pnl=-10.0)
                await panic_switch_with_mock_telegram.record_trade(result)
            
            # Reset
            await panic_switch_with_mock_telegram.reset()
            
            # Should have sent 2 notifications (panic + reset)
            assert mock_send.call_count == 2
            
            # Check reset message
            reset_call = mock_send.call_args_list[1][0][0]
            assert "PANIC SWITCH RESET" in reset_call
            assert "ACTIVE" in reset_call


class TestIntegration:
    """Integration tests"""
    
    @pytest.mark.asyncio
    async def test_full_panic_cycle(self):
        """Test full panic cycle: losses -> halt -> reset"""
        config = PanicSwitchConfig(
            max_consecutive_losses=3,
            time_window_minutes=15,
            enable_telegram=False,
        )
        panic_switch = PanicSwitch(config)
        
        # Initial state
        assert panic_switch.is_active is True
        
        # Record 2 losses
        for i in range(2):
            result = TradeResult(timestamp=datetime.now(), pnl=-10.0)
            await panic_switch.record_trade(result)
        
        assert panic_switch.is_active is True
        
        # Record 3rd loss - should trigger panic
        result = TradeResult(timestamp=datetime.now(), pnl=-15.0)
        panic_triggered = await panic_switch.record_trade(result)
        
        assert panic_triggered is True
        assert panic_switch.is_halted is True
        
        # Check statistics
        stats = panic_switch.get_statistics()
        assert stats["status"] == "HALTED"
        assert stats["losses_in_window"] == 3
        assert stats["total_losses"] == 3
        
        # Reset
        await panic_switch.reset()
        
        assert panic_switch.is_active is True
        assert panic_switch.is_halted is False
        
        # Can trade again
        result = TradeResult(timestamp=datetime.now(), pnl=10.0)
        panic_triggered = await panic_switch.record_trade(result)
        
        assert panic_triggered is False
        assert panic_switch.is_active is True
    
    @pytest.mark.asyncio
    async def test_concurrent_trades(self):
        """Test handling concurrent trade recordings"""
        config = PanicSwitchConfig(
            max_consecutive_losses=3,
            time_window_minutes=15,
            enable_telegram=False,
        )
        panic_switch = PanicSwitch(config)
        
        # Record trades concurrently
        tasks = []
        for i in range(5):
            result = TradeResult(
                timestamp=datetime.now(),
                pnl=-10.0 if i < 3 else 10.0,
            )
            tasks.append(panic_switch.record_trade(result))
        
        results = await asyncio.gather(*tasks)
        
        # Should have triggered panic
        assert panic_switch.is_halted is True
        assert any(results)  # At least one should return True
    
    @pytest.mark.asyncio
    async def test_close_resources(self):
        """Test closing resources"""
        config = PanicSwitchConfig(
            telegram_bot_token="test",
            telegram_chat_id="test",
            enable_telegram=True,
        )
        panic_switch = PanicSwitch(config)
        
        # Create session
        await panic_switch.send_telegram_notification("test")
        
        # Close
        await panic_switch.close()
        
        # Session should be closed
        assert panic_switch._telegram_session is None or panic_switch._telegram_session.closed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
