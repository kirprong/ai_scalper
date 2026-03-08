"""
Panic Switch - Automatic safety mechanism to halt trading after consecutive losses.

This module implements:
- Rolling window tracking of losing trades (15 minutes)
- Automatic system halt after 3 consecutive losses
- Telegram notifications
- Manual reset capability
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Deque
import aiohttp

logger = logging.getLogger(__name__)


class SystemStatus(str, Enum):
    """System operational status"""
    ACTIVE = "ACTIVE"
    HALTED = "HALTED"


@dataclass
class TradeResult:
    """Represents a completed trade result"""
    timestamp: datetime
    pnl: float
    symbol: str = "BTC_TARGET"
    quantity: float = 0.0
    entry_price: float = 0.0
    exit_price: float = 0.0
    
    @property
    def is_loss(self) -> bool:
        """Check if trade was a loss"""
        return self.pnl < 0


@dataclass
class PanicSwitchConfig:
    """Configuration for Panic Switch"""
    
    # Number of consecutive losses to trigger panic
    max_consecutive_losses: int = 3
    
    # Time window in minutes for counting losses
    time_window_minutes: int = 15
    
    # Telegram bot token (from environment)
    telegram_bot_token: Optional[str] = None
    
    # Telegram chat ID (from environment)
    telegram_chat_id: Optional[str] = None
    
    # Enable Telegram notifications
    enable_telegram: bool = True


class PanicSwitch:
    """
    Panic Switch - Automatic safety mechanism.
    
    Monitors trading performance and halts system when:
    - 3 consecutive losing trades occur within 15 minutes
    
    Features:
    - Rolling window tracking with deque
    - Telegram notifications
    - Manual reset capability
    - Thread-safe operations
    """
    
    def __init__(self, config: Optional[PanicSwitchConfig] = None):
        """Initialize Panic Switch."""
        self.config = config or PanicSwitchConfig()
        
        # Rolling window of losing trades
        self._losing_trades: Deque[TradeResult] = deque()
        
        # System status
        self._status: SystemStatus = SystemStatus.ACTIVE
        
        # All trades history (for statistics)
        self._all_trades: List[TradeResult] = []
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Telegram session
        self._telegram_session: Optional[aiohttp.ClientSession] = None
        
        logger.info(
            f"PanicSwitch initialized: max_losses={self.config.max_consecutive_losses}, "
            f"window={self.config.time_window_minutes}min"
        )
    
    @property
    def status(self) -> SystemStatus:
        """Get current system status"""
        return self._status
    
    @property
    def is_halted(self) -> bool:
        """Check if system is halted"""
        return self._status == SystemStatus.HALTED
    
    @property
    def is_active(self) -> bool:
        """Check if system is active"""
        return self._status == SystemStatus.ACTIVE
    
    def _clean_old_trades(self) -> None:
        """Remove trades outside the time window"""
        cutoff_time = datetime.now() - timedelta(minutes=self.config.time_window_minutes)
        
        while self._losing_trades and self._losing_trades[0].timestamp < cutoff_time:
            self._losing_trades.popleft()
    
    async def record_trade(self, result: TradeResult) -> bool:
        """
        Record trade result and check for panic condition.
        
        Args:
            result: Trade result to record
            
        Returns:
            True if panic triggered, False otherwise
        """
        async with self._lock:
            # Record all trades
            self._all_trades.append(result)
            
            # If it's a loss, add to losing trades
            if result.is_loss:
                self._losing_trades.append(result)
                logger.warning(
                    f"Loss recorded: pnl={result.pnl:.2f}, "
                    f"total_losses_in_window={len(self._losing_trades)}"
                )
            
            # Clean old trades
            self._clean_old_trades()
            
            # Check panic condition
            if self.check_panic():
                await self.halt_system()
                return True
            
            return False
    
    def check_panic(self) -> bool:
        """
        Check if panic threshold reached.
        
        Returns:
            True if panic should be triggered
        """
        # Already halted
        if self.is_halted:
            return True
        
        # Check if we have enough consecutive losses
        if len(self._losing_trades) >= self.config.max_consecutive_losses:
            logger.critical(
                f"PANIC THRESHOLD REACHED: {len(self._losing_trades)} losses in "
                f"{self.config.time_window_minutes} minutes"
            )
            return True
        
        return False
    
    async def halt_system(self) -> None:
        """
        Halt all trading operations.
        
        This method:
        1. Sets system status to HALTED
        2. Sends Telegram notification
        3. Logs critical event
        """
        async with self._lock:
            if self.is_halted:
                logger.warning("System already halted")
                return
            
            self._status = SystemStatus.HALTED
            
            # Calculate loss summary
            total_loss = sum(t.pnl for t in self._losing_trades)
            loss_count = len(self._losing_trades)
            
            logger.critical(
                f"🚨 SYSTEM HALTED 🚨\n"
                f"Reason: {loss_count} consecutive losses in {self.config.time_window_minutes} minutes\n"
                f"Total loss: ${total_loss:.2f}"
            )
            
            # Send Telegram notification
            if self.config.enable_telegram:
                message = (
                    f"🚨 **PANIC SWITCH ACTIVATED** 🚨\n\n"
                    f"**System Status:** HALTED\n\n"
                    f"**Reason:** {loss_count} consecutive losses in {self.config.time_window_minutes} minutes\n\n"
                    f"**Loss Summary:**\n"
                    f"• Total Loss: ${abs(total_loss):.2f}\n"
                    f"• Trades: {loss_count}\n"
                    f"• Time Window: {self.config.time_window_minutes} min\n\n"
                    f"⚠️ **Trading is BLOCKED until manual reset**"
                )
                await self.send_telegram_notification(message)
    
    async def send_telegram_notification(self, message: str) -> bool:
        """
        Send notification to Telegram.
        
        Args:
            message: Message to send
            
        Returns:
            True if sent successfully
        """
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            logger.warning("Telegram credentials not configured, skipping notification")
            return False
        
        try:
            # Create session if needed
            if self._telegram_session is None or self._telegram_session.closed:
                self._telegram_session = aiohttp.ClientSession()
            
            url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
            
            payload = {
                "chat_id": self.config.telegram_chat_id,
                "text": message,
                "parse_mode": "Markdown",
            }
            
            async with self._telegram_session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info("Telegram notification sent successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send Telegram notification: {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
            return False
    
    async def reset(self) -> None:
        """
        Reset panic switch after manual intervention.
        
        This method:
        1. Clears losing trades history
        2. Sets system status to ACTIVE
        3. Logs reset event
        """
        async with self._lock:
            self._losing_trades.clear()
            self._status = SystemStatus.ACTIVE
            
            logger.info("✅ Panic Switch RESET - System is now ACTIVE")
            
            # Send Telegram notification
            if self.config.enable_telegram:
                message = (
                    "✅ **PANIC SWITCH RESET**\n\n"
                    "**System Status:** ACTIVE\n\n"
                    "Trading has been manually re-enabled.\n\n"
                    "⚠️ Monitor the system closely."
                )
                await self.send_telegram_notification(message)
    
    def get_statistics(self) -> dict:
        """
        Get panic switch statistics.
        
        Returns:
            Dictionary with statistics
        """
        self._clean_old_trades()
        
        total_trades = len(self._all_trades)
        total_losses = sum(1 for t in self._all_trades if t.is_loss)
        total_pnl = sum(t.pnl for t in self._all_trades)
        
        return {
            "status": self._status.value,
            "is_halted": self.is_halted,
            "losses_in_window": len(self._losing_trades),
            "max_losses": self.config.max_consecutive_losses,
            "time_window_minutes": self.config.time_window_minutes,
            "total_trades": total_trades,
            "total_losses": total_losses,
            "total_pnl": total_pnl,
            "win_rate": (total_trades - total_losses) / total_trades * 100 if total_trades > 0 else 0.0,
        }
    
    async def close(self) -> None:
        """Close resources"""
        if self._telegram_session and not self._telegram_session.closed:
            await self._telegram_session.close()
