"""
Sniper Execution - Logic for entering positions
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class OrderType(str, Enum):
    """Order types"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    FOK = "FOK"  # Fill or Kill
    IOC = "IOC"  # Immediate or Cancel


class OrderSide(str, Enum):
    """Order sides"""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class TradingSignal:
    """Trading signal from ML models"""
    ml_status: int  # 1 = signal, 0 = no signal
    xgb_confidence: float  # Confidence score from XGBoost
    lstm_probability: float  # Probability from LSTM
    poly_lag_confirmed: bool  # Polymarket lag confirmed
    box_top: float  # Top of golden box
    box_bottom: float  # Bottom of golden box
    timestamp: float  # Signal timestamp
    
    def is_valid(self) -> bool:
        """Check if signal meets entry conditions"""
        return (
            self.ml_status == 1 and
            self.xgb_confidence > 0.85 and
            self.poly_lag_confirmed
        )


@dataclass
class Order:
    """Order representation"""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    order_id: Optional[str] = None
    status: str = "pending"
    
    def to_polymarket_format(self) -> Dict[str, Any]:
        """Convert to Polymarket API format"""
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
        }


class SniperExecution:
    """
    Sniper Execution Engine
    
    Entry conditions:
    - ML_Status == 1
    - XGB_Conf > 0.85
    - Poly_Lag confirmed
    
    Sends FOK or IOC orders to Polymarket
    """
    
    def __init__(
        self,
        min_confidence: float = 0.85,
        order_type: OrderType = OrderType.FOK,
        position_size: float = 100.0,  # Default position size
    ):
        self.min_confidence = min_confidence
        self.order_type = order_type
        self.position_size = position_size
        self.active_orders: Dict[str, Order] = {}
        self.position: Optional[Dict[str, Any]] = None
        
    async def evaluate_signal(self, signal: TradingSignal) -> bool:
        """
        Evaluate if signal meets entry conditions
        
        Args:
            signal: Trading signal from ML models
            
        Returns:
            True if signal is valid for entry
        """
        if not signal.is_valid():
            logger.debug(
                f"Signal rejected: ml_status={signal.ml_status}, "
                f"xgb_conf={signal.xgb_confidence:.3f}, "
                f"poly_lag={signal.poly_lag_confirmed}"
            )
            return False
        
        logger.info(
            f"Valid signal detected: conf={signal.xgb_confidence:.3f}, "
            f"box=[{signal.box_bottom:.2f}, {signal.box_top:.2f}]"
        )
        return True
    
    async def create_order(
        self,
        signal: TradingSignal,
        symbol: str = "BTC_TARGET",
    ) -> Order:
        """
        Create order from signal
        
        Args:
            signal: Valid trading signal
            symbol: Market symbol
            
        Returns:
            Order object
        """
        # Calculate position size based on box height
        box_height = signal.box_top - signal.box_bottom
        quantity = self.position_size / box_height if box_height > 0 else self.position_size
        
        order = Order(
            symbol=symbol,
            side=OrderSide.BUY,
            order_type=self.order_type,
            quantity=quantity,
            price=signal.box_bottom,  # Buy at bottom of box
        )
        
        logger.info(
            f"Created {order.order_type.value} order: "
            f"{order.side.value} {order.quantity:.4f} @ {order.price:.2f}"
        )
        
        return order
    
    async def send_order(self, order: Order) -> Dict[str, Any]:
        """
        Send order to Polymarket (mock implementation)
        
        Args:
            order: Order to send
            
        Returns:
            Order response
        """
        # Mock: Simulate order submission
        await asyncio.sleep(0.05)  # 50ms latency
        
        order.order_id = f"order_{asyncio.get_event_loop().time():.0f}"
        order.status = "filled"
        
        self.active_orders[order.order_id] = order
        
        price_str = f"{order.price:.2f}" if order.price else "MARKET"
        logger.info(f"Order {order.order_id} filled: {order.quantity:.4f} @ {price_str}")
        
        return {
            "order_id": order.order_id,
            "status": order.status,
            "filled_quantity": order.quantity,
            "filled_price": order.price,
        }
    
    async def execute_signal(
        self,
        signal: TradingSignal,
        symbol: str = "BTC_TARGET",
    ) -> Optional[Dict[str, Any]]:
        """
        Execute trading signal
        
        Args:
            signal: Trading signal
            symbol: Market symbol
            
        Returns:
            Order result if executed, None otherwise
        """
        # Evaluate signal
        if not await self.evaluate_signal(signal):
            return None
        
        # Create order
        order = await self.create_order(signal, symbol)
        
        # Send order
        result = await self.send_order(order)
        
        # Update position
        if result["status"] == "filled":
            self.position = {
                "symbol": symbol,
                "quantity": order.quantity,
                "entry_price": order.price,
                "box_top": signal.box_top,
                "box_bottom": signal.box_bottom,
                "timestamp": signal.timestamp,
            }
        
        return result
    
    def get_position(self) -> Optional[Dict[str, Any]]:
        """Get current position"""
        return self.position
    
    def has_position(self) -> bool:
        """Check if has active position"""
        return self.position is not None
    
    async def close_position(self) -> Optional[Dict[str, Any]]:
        """Close current position (market sell)"""
        if not self.has_position():
            return None
        
        position = self.position
        
        order = Order(
            symbol=position["symbol"],
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=position["quantity"],
        )
        
        result = await self.send_order(order)
        
        if result["status"] == "filled":
            self.position = None
        
        return result