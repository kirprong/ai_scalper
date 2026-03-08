"""
Paper Trading Simulator.

This module provides a realistic paper trading simulation with:
- Slippage engine (0.01-0.02 cents)
- Latency simulation (200-500ms)
- Fee calculation
- Position tracking
- PnL calculation
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime
import asyncio
import random
import logging
import time

from .slippage import SlippageEngine, SlippageConfig
from .fees import FeeCalculator, FeeConfig

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class PaperTradingConfig:
    """Configuration for paper trading simulator."""
    
    # Initial balance
    initial_balance: float = 10000.0
    
    # Latency simulation (milliseconds)
    min_latency_ms: int = 200
    max_latency_ms: int = 500
    
    # Slippage config
    slippage_config: SlippageConfig = field(default_factory=SlippageConfig)
    
    # Fee config
    fee_config: FeeConfig = field(default_factory=FeeConfig)
    
    # Random seed for reproducibility
    random_seed: Optional[int] = None


@dataclass
class Position:
    """Represents a trading position."""
    
    symbol: str
    side: str  # "long" or "short"
    quantity: float
    entry_price: float
    entry_time: datetime
    entry_slippage: float = 0.0
    entry_fee: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "entry_slippage": self.entry_slippage,
            "entry_fee": self.entry_fee,
        }


@dataclass
class Trade:
    """Represents a completed trade."""
    
    symbol: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    gross_pnl: float
    fees: float
    net_pnl: float
    slippage: float
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat(),
            "gross_pnl": self.gross_pnl,
            "fees": self.fees,
            "net_pnl": self.net_pnl,
            "slippage": self.slippage,
        }


class PaperTradingSimulator:
    """
    Paper trading simulator with realistic market conditions.
    
    Features:
    - Slippage simulation (0.01-0.02 cents)
    - Latency simulation (200-500ms)
    - Fee calculation
    - Position tracking
    - PnL tracking
    """
    
    def __init__(self, config: Optional[PaperTradingConfig] = None):
        """Initialize paper trading simulator."""
        self.config = config or PaperTradingConfig()
        
        # Initialize components
        self.slippage_engine = SlippageEngine(self.config.slippage_config)
        self.fee_calculator = FeeCalculator(self.config.fee_config)
        
        # Set random seed
        if self.config.random_seed is not None:
            random.seed(self.config.random_seed)
        
        # State
        self.balance: float = self.config.initial_balance
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.total_pnl: float = 0.0
        self.total_fees: float = 0.0
        self.total_slippage: float = 0.0
    
    async def simulate_latency(self) -> float:
        """
        Simulate network latency.
        
        Returns:
            Actual latency in milliseconds
        """
        latency_ms = random.randint(
            self.config.min_latency_ms,
            self.config.max_latency_ms
        )
        
        logger.debug(f"Simulating latency: {latency_ms}ms")
        
        # Simulate delay
        await asyncio.sleep(latency_ms / 1000.0)
        
        return latency_ms
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        order_type: str = "market",
        volatility: float = 0.0,
    ) -> dict:
        """
        Place a paper trading order.
        
        Args:
            symbol: Trading symbol
            side: Order side ("buy" or "sell")
            quantity: Order quantity
            price: Expected price
            order_type: Order type ("market" or "limit")
            volatility: Current market volatility (0-1)
        
        Returns:
            Dictionary with order result
        """
        start_time = time.time()
        
        # Simulate latency
        latency_ms = await self.simulate_latency()
        
        # Calculate slippage
        execution_price, slippage = self.slippage_engine.calculate_slippage(
            price=price,
            side=side,
            order_size=quantity,
            volatility=volatility,
        )
        
        # Calculate fees
        fee_result = self.fee_calculator.calculate_fee(
            price=execution_price,
            quantity=quantity,
            side=side,
            order_type=order_type,
        )
        
        # Update state
        total_cost = execution_price * quantity + fee_result["total_fee"]
        
        if side.lower() == "buy":
            # Check balance
            if total_cost > self.balance:
                return {
                    "success": False,
                    "error": "Insufficient balance",
                    "required": total_cost,
                    "available": self.balance,
                }
            
            # Deduct from balance
            self.balance -= total_cost
            
            # Create position
            position = Position(
                symbol=symbol,
                side="long",
                quantity=quantity,
                entry_price=execution_price,
                entry_time=datetime.now(),
                entry_slippage=slippage,
                entry_fee=fee_result["total_fee"],
            )
            
            self.positions[symbol] = position
            
            logger.info(
                f"BUY order executed: {symbol} {quantity}@{execution_price:.4f} "
                f"(slip={slippage:.4f}, fee=${fee_result['total_fee']:.2f})"
            )
        
        else:  # sell
            # Check position
            if symbol not in self.positions:
                return {
                    "success": False,
                    "error": "No position to sell",
                }
            
            position = self.positions[symbol]
            
            # Calculate PnL
            gross_pnl = (execution_price - position.entry_price) * quantity
            total_fees = position.entry_fee + fee_result["total_fee"]
            net_pnl = gross_pnl - total_fees
            
            # Update balance
            self.balance += execution_price * quantity - fee_result["total_fee"]
            
            # Create trade record
            trade = Trade(
                symbol=symbol,
                side="long",
                quantity=quantity,
                entry_price=position.entry_price,
                exit_price=execution_price,
                entry_time=position.entry_time,
                exit_time=datetime.now(),
                gross_pnl=gross_pnl,
                fees=total_fees,
                net_pnl=net_pnl,
                slippage=position.entry_slippage + slippage,
            )
            
            self.trades.append(trade)
            
            # Update totals
            self.total_pnl += net_pnl
            self.total_fees += total_fees
            self.total_slippage += trade.slippage
            
            # Remove position
            del self.positions[symbol]
            
            logger.info(
                f"SELL order executed: {symbol} {quantity}@{execution_price:.4f} "
                f"(PnL=${net_pnl:.2f}, fees=${total_fees:.2f})"
            )
        
        # Calculate execution time
        execution_time_ms = (time.time() - start_time) * 1000
        
        return {
            "success": True,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "expected_price": price,
            "execution_price": execution_price,
            "slippage": slippage,
            "fees": fee_result["total_fee"],
            "latency_ms": latency_ms,
            "execution_time_ms": execution_time_ms,
            "balance": self.balance,
        }
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get current position for symbol."""
        return self.positions.get(symbol)
    
    def get_stats(self) -> dict:
        """Get trading statistics."""
        winning_trades = [t for t in self.trades if t.net_pnl > 0]
        losing_trades = [t for t in self.trades if t.net_pnl <= 0]
        
        return {
            "balance": self.balance,
            "initial_balance": self.config.initial_balance,
            "total_pnl": self.total_pnl,
            "total_fees": self.total_fees,
            "total_slippage": self.total_slippage,
            "total_trades": len(self.trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": len(winning_trades) / len(self.trades) * 100 if self.trades else 0.0,
            "avg_pnl": self.total_pnl / len(self.trades) if self.trades else 0.0,
            "open_positions": len(self.positions),
        }
    
    def reset(self):
        """Reset simulator to initial state."""
        self.balance = self.config.initial_balance
        self.positions.clear()
        self.trades.clear()
        self.total_pnl = 0.0
        self.total_fees = 0.0
        self.total_slippage = 0.0
        
        logger.info("Paper trading simulator reset")