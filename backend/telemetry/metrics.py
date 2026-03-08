"""
Telemetry Calculation Block - AI Metrics
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class TelemetryMetrics:
    """Telemetry metrics container"""
    opportunity_capture_rate: float = 0.0
    edge_per_trade: float = 0.0
    box_stability: float = 0.0
    total_opportunities: int = 0
    captured_opportunities: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    total_pnl: float = 0.0
    avg_trade_duration: float = 0.0


class TelemetryCalculator:
    """
    Telemetry Calculation Block
    
    Calculates AI performance metrics:
    - Opportunity Capture Rate (OCR) > 70%
    - Edge per Trade
    - Box Stability
    """
    
    def __init__(
        self,
        ocr_threshold: float = 0.70,
        min_trades: int = 10,
    ):
        """
        Initialize telemetry calculator
        
        Args:
            ocr_threshold: Minimum OCR threshold (default 70%)
            min_trades: Minimum trades for valid statistics
        """
        self.ocr_threshold = ocr_threshold
        self.min_trades = min_trades
        self.metrics = TelemetryMetrics()
        
    def calculate_ocr(
        self,
        total_opportunities: int,
        captured_opportunities: int,
    ) -> float:
        """
        Calculate Opportunity Capture Rate
        
        Args:
            total_opportunities: Total number of golden boxes detected
            captured_opportunities: Number of golden boxes traded
            
        Returns:
            OCR as percentage
        """
        if total_opportunities == 0:
            return 0.0
            
        ocr = captured_opportunities / total_opportunities
        self.metrics.total_opportunities = total_opportunities
        self.metrics.captured_opportunities = captured_opportunities
        self.metrics.opportunity_capture_rate = ocr
        
        logger.info(
            f"OCR: {ocr:.2%} ({captured_opportunities}/{total_opportunities})"
        )
        
        return ocr
    
    def calculate_edge_per_trade(
        self,
        trades: List[Dict[str, Any]],
    ) -> float:
        """
        Calculate Edge per Trade
        
        Args:
            trades: List of trade dictionaries with 'pnl' key
            
        Returns:
            Average edge per trade
        """
        if not trades:
            return 0.0
            
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        edge = total_pnl / len(trades)
        
        self.metrics.total_trades = len(trades)
        self.metrics.total_pnl = total_pnl
        self.metrics.edge_per_trade = edge
        
        logger.info(
            f"Edge per trade: ${edge:.2f} (${total_pnl:.2f} / {len(trades)} trades)"
        )
        
        return edge
    
    def calculate_box_stability(
        self,
        boxes: List[Dict[str, Any]],
    ) -> float:
        """
        Calculate Box Stability
        
        Args:
            boxes: List of golden box dictionaries with 'duration' key
            
        Returns:
            Box stability score (0-1)
        """
        if not boxes:
            return 0.0
            
        # Calculate average duration
        durations = [b.get("duration", 0) for b in boxes]
        avg_duration = sum(durations) / len(durations)
        
        # Stability score based on duration consistency
        # Higher consistency = higher stability
        if len(durations) < 2:
            stability = 1.0
        else:
            variance = sum((d - avg_duration) ** 2 for d in durations) / len(durations)
            std_dev = variance ** 0.5
            
            # Normalize stability (lower std_dev = higher stability)
            stability = max(0, 1 - (std_dev / avg_duration)) if avg_duration > 0 else 0
        
        self.metrics.box_stability = stability
        
        logger.info(
            f"Box stability: {stability:.2%} (avg duration: {avg_duration:.2f}s)"
        )
        
        return stability
    
    def calculate_all(
        self,
        opportunities: List[Dict[str, Any]],
        trades: List[Dict[str, Any]],
        boxes: List[Dict[str, Any]],
    ) -> TelemetryMetrics:
        """
        Calculate all telemetry metrics
        
        Args:
            opportunities: List of opportunities (golden boxes)
            trades: List of executed trades
            boxes: List of golden boxes with duration
            
        Returns:
            TelemetryMetrics object
        """
        # OCR
        total_opps = len(opportunities)
        captured_opps = len([o for o in opportunities if o.get("captured", False)])
        self.calculate_ocr(total_opps, captured_opps)
        
        # Edge per trade
        self.calculate_edge_per_trade(trades)
        
        # Box stability
        self.calculate_box_stability(boxes)
        
        # Additional metrics
        if trades:
            self.metrics.winning_trades = len([t for t in trades if t.get("pnl", 0) > 0])
            
            durations = [t.get("duration", 0) for t in trades]
            self.metrics.avg_trade_duration = sum(durations) / len(durations) if durations else 0
        
        return self.metrics
    
    def is_ocr_healthy(self) -> bool:
        """Check if OCR meets threshold"""
        return self.metrics.opportunity_capture_rate >= self.ocr_threshold
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        return {
            "opportunity_capture_rate": self.metrics.opportunity_capture_rate,
            "edge_per_trade": self.metrics.edge_per_trade,
            "box_stability": self.metrics.box_stability,
            "total_opportunities": self.metrics.total_opportunities,
            "captured_opportunities": self.metrics.captured_opportunities,
            "total_trades": self.metrics.total_trades,
            "winning_trades": self.metrics.winning_trades,
            "total_pnl": self.metrics.total_pnl,
            "avg_trade_duration": self.metrics.avg_trade_duration,
            "ocr_healthy": self.is_ocr_healthy(),
        }
    
    def print_summary(self):
        """Print metrics summary"""
        print("\n" + "=" * 60)
        print("TELEMETRY METRICS")
        print("=" * 60)
        print(f"Opportunity Capture Rate: {self.metrics.opportunity_capture_rate:.2%}")
        print(f"  Threshold: {self.ocr_threshold:.2%}")
        print(f"  Status: {'✓ HEALTHY' if self.is_ocr_healthy() else '✗ BELOW THRESHOLD'}")
        print(f"\nEdge per Trade: ${self.metrics.edge_per_trade:.2f}")
        print(f"Box Stability: {self.metrics.box_stability:.2%}")
        print(f"\nTotal Opportunities: {self.metrics.total_opportunities}")
        print(f"Captured Opportunities: {self.metrics.captured_opportunities}")
        print(f"Total Trades: {self.metrics.total_trades}")
        print(f"Winning Trades: {self.metrics.winning_trades}")
        print(f"Total PnL: ${self.metrics.total_pnl:.2f}")
        print(f"Avg Trade Duration: {self.metrics.avg_trade_duration:.2f}s")
        print("=" * 60)
