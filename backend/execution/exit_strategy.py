"""
Exit Strategy A - Double Trap (Limit Sell Target)
"""
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ExitType(str, Enum):
    """Exit types"""
    LIMIT_SELL = "LIMIT_SELL"
    MARKET_SELL = "MARKET_SELL"
    STOP_LOSS = "STOP_LOSS"


@dataclass
class ExitOrder:
    """Exit order representation"""
    symbol: str
    quantity: float
    price: float
    exit_type: ExitType
    order_id: Optional[str] = None
    status: str = "pending"


class ExitStrategyA:
    """
    Exit Strategy A - Double Trap
    
    After buying, place Limit Sell at Top_of_Box - 0.01
    """
    
    def __init__(
        self,
        price_offset: float = 0.01,  # Offset from box top
    ):
        self.price_offset = price_offset
        self.exit_order: Optional[ExitOrder] = None
        self.position: Optional[Dict[str, Any]] = None
        
    def calculate_exit_price(self, box_top: float) -> float:
        """
        Calculate exit price
        
        Args:
            box_top: Top of golden box
            
        Returns:
            Exit price (box_top - offset)
        """
        exit_price = box_top - self.price_offset
        logger.info(f"Exit price calculated: {exit_price:.4f} (box_top={box_top:.4f}, offset={self.price_offset})")
        return exit_price
    
    def create_exit_order(
        self,
        position: Dict[str, Any],
    ) -> ExitOrder:
        """
        Create exit order for position
        
        Args:
            position: Current position info
            
        Returns:
            Exit order
        """
        box_top = position["box_top"]
        exit_price = self.calculate_exit_price(box_top)
        
        order = ExitOrder(
            symbol=position["symbol"],
            quantity=position["quantity"],
            price=exit_price,
            exit_type=ExitType.LIMIT_SELL,
        )
        
        self.position = position
        self.exit_order = order
        
        logger.info(
            f"Created exit order: LIMIT SELL {order.quantity:.4f} @ {order.price:.4f}"
        )
        
        return order
    
    def update_exit_order(self, new_box_top: float) -> Optional[ExitOrder]:
        """
        Update exit order if box top changed
        
        Args:
            new_box_top: New box top value
            
        Returns:
            Updated exit order or None
        """
        if not self.exit_order or not self.position:
            return None
            
        new_exit_price = self.calculate_exit_price(new_box_top)
        
        if new_exit_price != self.exit_order.price:
            logger.info(
                f"Updating exit order price: {self.exit_order.price:.4f} -> {new_exit_price:.4f}"
            )
            self.exit_order.price = new_exit_price
            self.position["box_top"] = new_box_top
            
        return self.exit_order
    
    def should_trigger_stop_loss(
        self,
        current_price: float,
        drop_threshold: float = 0.20,  # 20% drop
    ) -> bool:
        """
        Check if stop loss should be triggered
        
        Args:
            current_price: Current market price
            drop_threshold: Drop threshold as fraction
            
        Returns:
            True if stop loss should trigger
        """
        if not self.position:
            return False
            
        box_height = self.position["box_top"] - self.position["box_bottom"]
        drop_amount = self.position["box_bottom"] - current_price
        
        if drop_amount > box_height * drop_threshold:
            logger.warning(
                f"Stop loss triggered: price dropped {drop_amount:.4f} "
                f"(>{drop_threshold*100:.0f}% of box height {box_height:.4f})"
            )
            return True
            
        return False
    
    def get_exit_order(self) -> Optional[ExitOrder]:
        """Get current exit order"""
        return self.exit_order
    
    def has_exit_order(self) -> bool:
        """Check if has exit order"""
        return self.exit_order is not None
    
    def clear(self):
        """Clear exit order and position"""
        self.exit_order = None
        self.position = None
        logger.info("Exit strategy cleared")
