"""
Slippage Engine.

This module calculates realistic slippage for paper trading simulation.
Slippage models the difference between expected and actual execution price.

Factors:
- Order size relative to market depth
- Market volatility
- Bid-ask spread
- Market impact
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import random
import logging

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class SlippageConfig:
    """Configuration for slippage calculation."""
    
    # Base slippage (in price units)
    base_slippage_cents: float = 0.01  # 0.01-0.02 cents
    
    # Maximum slippage (in price units)
    max_slippage_cents: float = 0.02
    
    # Slippage as percentage of price
    slippage_pct: float = 0.0001  # 0.01%
    
    # Market impact factor (larger orders = more slippage)
    impact_factor: float = 0.1
    
    # Volatility multiplier
    volatility_multiplier: float = 1.5
    
    # Random seed for reproducibility (None for random)
    random_seed: Optional[int] = None


class SlippageEngine:
    """
    Calculates realistic slippage for paper trading.
    
    Slippage is the difference between the expected execution price
    and the actual execution price. This engine models various factors
    that contribute to slippage in real markets.
    """
    
    def __init__(self, config: Optional[SlippageConfig] = None):
        """Initialize slippage engine."""
        self.config = config or SlippageConfig()
        
        # Set random seed if provided
        if self.config.random_seed is not None:
            random.seed(self.config.random_seed)
    
    def calculate_slippage(
        self,
        price: float,
        side: str,  # "buy" or "sell"
        order_size: float = 1.0,
        volatility: float = 0.0,
        spread: float = 0.0,
    ) -> Tuple[float, float]:
        """
        Calculate slippage for an order.
        
        Args:
            price: Expected execution price
            side: Order side ("buy" or "sell")
            order_size: Order size relative to average (1.0 = normal)
            volatility: Current market volatility (0-1)
            spread: Current bid-ask spread
        
        Returns:
            Tuple of (execution_price, slippage_amount)
        """
        # Base slippage (random within range)
        base_slip = random.uniform(
            self.config.base_slippage_cents,
            self.config.max_slippage_cents
        )
        
        # Market impact (larger orders = more slippage)
        impact_slip = base_slip * (order_size - 1.0) * self.config.impact_factor
        
        # Volatility adjustment
        volatility_slip = base_slip * volatility * self.config.volatility_multiplier
        
        # Spread adjustment
        spread_slip = spread * 0.5  # Half of spread
        
        # Total slippage
        total_slippage = base_slip + impact_slip + volatility_slip + spread_slip
        
        # Apply slippage based on side
        if side.lower() == "buy":
            # Buy orders execute at higher price
            execution_price = price + total_slippage
        else:
            # Sell orders execute at lower price
            execution_price = price - total_slippage
        
        logger.debug(
            f"Slippage calculated: side={side}, price={price:.4f}, "
            f"execution={execution_price:.4f}, slip={total_slippage:.4f}"
        )
        
        return execution_price, total_slippage
    
    def calculate_slippage_pct(
        self,
        price: float,
        side: str,
        order_size: float = 1.0,
        volatility: float = 0.0,
    ) -> Tuple[float, float]:
        """
        Calculate slippage as percentage of price.
        
        Args:
            price: Expected execution price
            side: Order side ("buy" or "sell")
            order_size: Order size relative to average
            volatility: Current market volatility (0-1)
        
        Returns:
            Tuple of (execution_price, slippage_pct)
        """
        # Calculate slippage percentage
        base_pct = self.config.slippage_pct
        
        # Adjust for order size
        size_pct = base_pct * (order_size - 1.0) * self.config.impact_factor
        
        # Adjust for volatility
        volatility_pct = base_pct * volatility * self.config.volatility_multiplier
        
        # Total slippage percentage
        total_pct = base_pct + size_pct + volatility_pct
        
        # Calculate execution price
        if side.lower() == "buy":
            execution_price = price * (1 + total_pct)
        else:
            execution_price = price * (1 - total_pct)
        
        return execution_price, total_pct
