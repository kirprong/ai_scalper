"""
Fee Calculator.

This module calculates trading fees for paper trading simulation.
Fees include exchange fees, network fees, and other costs.

Polymarket Fees:
- Maker fee: 0.0%
- Taker fee: 0.0% (Polymarket has no trading fees)
- Network fee: Gas costs for transactions (estimated)
"""

from dataclasses import dataclass
from typing import Optional
import logging

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class FeeConfig:
    """Configuration for fee calculation."""
    
    # Polymarket has no trading fees
    maker_fee_pct: float = 0.0
    taker_fee_pct: float = 0.0
    
    # Network fees (gas costs)
    gas_fee_usd: float = 0.50  # Estimated gas cost per transaction
    
    # Slippage buffer (additional cost)
    slippage_buffer_pct: float = 0.0001  # 0.01%
    
    # Minimum fee
    min_fee_usd: float = 0.0


class FeeCalculator:
    """
    Calculates trading fees for paper trading.
    
    Polymarket has zero trading fees, but there are network costs
    (gas) for blockchain transactions.
    """
    
    def __init__(self, config: Optional[FeeConfig] = None):
        """Initialize fee calculator."""
        self.config = config or FeeConfig()
    
    def calculate_fee(
        self,
        price: float,
        quantity: float,
        side: str,
        order_type: str = "market",
    ) -> dict:
        """
        Calculate total fee for a trade.
        
        Args:
            price: Execution price
            quantity: Trade quantity
            side: Order side ("buy" or "sell")
            order_type: Order type ("market" or "limit")
        
        Returns:
            Dictionary with fee breakdown
        """
        # Trade value
        trade_value = price * quantity
        
        # Trading fee (0% for Polymarket)
        if order_type.lower() == "limit":
            trading_fee = trade_value * self.config.maker_fee_pct
            fee_type = "maker"
        else:
            trading_fee = trade_value * self.config.taker_fee_pct
            fee_type = "taker"
        
        # Network fee (gas)
        network_fee = self.config.gas_fee_usd
        
        # Slippage buffer
        slippage_cost = trade_value * self.config.slippage_buffer_pct
        
        # Total fee
        total_fee = trading_fee + network_fee + slippage_cost
        
        # Apply minimum fee
        total_fee = max(total_fee, self.config.min_fee_usd)
        
        # Fee as percentage of trade
        fee_pct = (total_fee / trade_value * 100) if trade_value > 0 else 0.0
        
        result = {
            "trade_value": trade_value,
            "trading_fee": trading_fee,
            "network_fee": network_fee,
            "slippage_cost": slippage_cost,
            "total_fee": total_fee,
            "fee_pct": fee_pct,
            "fee_type": fee_type,
        }
        
        logger.debug(
            f"Fee calculated: trade_value=${trade_value:.2f}, "
            f"total_fee=${total_fee:.2f} ({fee_pct:.4f}%)"
        )
        
        return result
    
    def calculate_pnl_adjustment(
        self,
        entry_price: float,
        exit_price: float,
        quantity: float,
    ) -> dict:
        """
        Calculate PnL adjustment for fees.
        
        Args:
            entry_price: Entry execution price
            exit_price: Exit execution price
            quantity: Trade quantity
        
        Returns:
            Dictionary with PnL and fee adjustments
        """
        # Calculate fees for entry and exit
        entry_fees = self.calculate_fee(entry_price, quantity, "buy", "market")
        exit_fees = self.calculate_fee(exit_price, quantity, "sell", "market")
        
        # Total fees
        total_fees = entry_fees["total_fee"] + exit_fees["total_fee"]
        
        # Gross PnL
        gross_pnl = (exit_price - entry_price) * quantity
        
        # Net PnL (after fees)
        net_pnl = gross_pnl - total_fees
        
        result = {
            "entry_fees": entry_fees,
            "exit_fees": exit_fees,
            "total_fees": total_fees,
            "gross_pnl": gross_pnl,
            "net_pnl": net_pnl,
            "fee_impact": total_fees / abs(gross_pnl) * 100 if gross_pnl != 0 else 0.0,
        }
        
        return result
