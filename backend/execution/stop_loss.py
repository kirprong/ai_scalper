"""
Exit Strategy B - Dynamic Market Stop-Loss
"""
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class StopLossType(str, Enum):
    """Stop loss types"""
    DYNAMIC = "DYNAMIC"
    FIXED = "FIXED"
    TRAILING = "TRAILING"


@dataclass
class StopLossOrder:
    """Stop loss order representation"""
    symbol: str
    quantity: float
    trigger_price: float
    stop_loss_type: StopLossType
    order_id: Optional[str] = None
    status: str = "pending"


class DynamicStopLoss:
    """
    Exit Strategy B - Dynamic Market Stop-Loss
    
    Triggers MARKET SELL when Binance drops >20% from box height
    """
    
    def __init__(
        self,
        drop_threshold: float = 0.20,  # 20% drop threshold
    ):
        self.drop_threshold = drop_threshold
        self.stop_loss_order: Optional[StopLossOrder] = None
        self.position: Optional[Dict[str, Any]] = None
        self.cancelled_limit_order: bool = False
        
    def calculate_trigger_price(self, box_bottom: float, box_height: float) -> float:
        """
        Calculate stop loss trigger price
        
        Args:
            box_bottom: Bottom of golden box
            box_height: Height of golden box
            
        Returns:
            Trigger price for stop loss
        """
        trigger_price = box_bottom - (box_height * self.drop_threshold)
        logger.info(
            f"Stop loss trigger price: {trigger_price:.4f} "
            f"(box_bottom={box_bottom:.4f}, threshold={self.drop_threshold*100:.0f}%)"
        )
        return trigger_price
    
    def create_stop_loss(
        self,
        position: Dict[str, Any],
    ) -> StopLossOrder:
        """
        Create stop loss order for position
        
        Args:
            position: Current position info
            
        Returns:
            Stop loss order
        """
        box_height = position["box_top"] - position["box_bottom"]
        trigger_price = self.calculate_trigger_price(
            position["box_bottom"],
            box_height
        )
        
        order = StopLossOrder(
            symbol=position["symbol"],
            quantity=position["quantity"],
            trigger_price=trigger_price,
            stop_loss_type=StopLossType.DYNAMIC,
        )
        
        self.position = position
        self.stop_loss_order = order
        
        logger.info(
            f"Created stop loss: MARKET SELL {order.quantity:.4f} "
            f"if price drops to {trigger_price:.4f}"
        )
        
        return order
    
    def should_trigger(
        self,
        current_price: float,
    ) -> bool:
        """
        Check if stop loss should be triggered
        
        Args:
            current_price: Current market price
            
        Returns:
            True if stop loss should trigger
        """
        if not self.stop_loss_order:
            return False
            
        if current_price <= self.stop_loss_order.trigger_price:
            logger.warning(
                f"STOP LOSS TRIGGERED: price {current_price:.4f} <= "
                f"trigger {self.stop_loss_order.trigger_price:.4f}"
            )
            return True
            
        return False
    
    async def execute_stop_loss(self) -> Dict[str, Any]:
        """
        Execute stop loss - cancel limit order and send market sell
        
        Returns:
            Execution result
        """
        if not self.stop_loss_order:
            return {"status": "error", "message": "No stop loss order"}
            
        logger.warning(
            f"EXECUTING STOP LOSS: MARKET SELL {self.stop_loss_order.quantity:.4f}"
        )
        
        # Mock: Cancel limit order
        self.cancelled_limit_order = True
        logger.info("Cancelled limit sell order")
        
        # Mock: Send market sell
        import asyncio
        await asyncio.sleep(0.05)  # 50ms latency
        
        result = {
            "status": "filled",
            "order_type": "MARKET_SELL",
            "quantity": self.stop_loss_order.quantity,
            "symbol": self.stop_loss_order.symbol,
        }
        
        logger.info(f"Stop loss executed: {result}")
        
        return result
    
    def update_trigger_price(
        self,
        new_box_bottom: float,
        new_box_height: float,
    ) -> Optional[StopLossOrder]:
        """
        Update stop loss trigger price
        
        Args:
            new_box_bottom: New box bottom
            new_box_height: New box height
            
        Returns:
            Updated stop loss order or None
        """
        if not self.stop_loss_order or not self.position:
            return None
            
        new_trigger = self.calculate_trigger_price(new_box_bottom, new_box_height)
        
        if new_trigger != self.stop_loss_order.trigger_price:
            logger.info(
                f"Updating stop loss trigger: {self.stop_loss_order.trigger_price:.4f} -> {new_trigger:.4f}"
            )
            self.stop_loss_order.trigger_price = new_trigger
            self.position["box_bottom"] = new_box_bottom
            
        return self.stop_loss_order
    
    def get_stop_loss_order(self) -> Optional[StopLossOrder]:
        """Get current stop loss order"""
        return self.stop_loss_order
    
    def has_stop_loss(self) -> bool:
        """Check if has stop loss order"""
        return self.stop_loss_order is not None
    
    def clear(self):
        """Clear stop loss order and position"""
        self.stop_loss_order = None
        self.position = None
        self.cancelled_limit_order = False
        logger.info("Stop loss cleared")
