"""
Tests for Telemetry Calculation Block
"""
import pytest
from backend.telemetry.metrics import (
    TelemetryCalculator,
    TelemetryMetrics,
)


@pytest.fixture
def calculator():
    """Create telemetry calculator"""
    return TelemetryCalculator(ocr_threshold=0.70, min_trades=10)


@pytest.fixture
def opportunities():
    """Create mock opportunities"""
    return [
        {"id": 1, "captured": True},
        {"id": 2, "captured": True},
        {"id": 3, "captured": False},
        {"id": 4, "captured": True},
        {"id": 5, "captured": False},
    ]


@pytest.fixture
def trades():
    """Create mock trades"""
    return [
        {"id": 1, "pnl": 100.0, "duration": 60},
        {"id": 2, "pnl": -50.0, "duration": 120},
        {"id": 3, "pnl": 150.0, "duration": 90},
        {"id": 4, "pnl": 75.0, "duration": 45},
        {"id": 5, "pnl": -25.0, "duration": 180},
    ]


@pytest.fixture
def boxes():
    """Create mock golden boxes"""
    return [
        {"id": 1, "duration": 900},
        {"id": 2, "duration": 920},
        {"id": 3, "duration": 880},
        {"id": 4, "duration": 910},
        {"id": 5, "duration": 890},
    ]


class TestTelemetryMetrics:
    """Tests for TelemetryMetrics"""
    
    def test_metrics_creation(self):
        """Test metrics creation"""
        metrics = TelemetryMetrics()
        assert metrics.opportunity_capture_rate == 0.0
        assert metrics.edge_per_trade == 0.0
        assert metrics.box_stability == 0.0


class TestTelemetryCalculator:
    """Tests for TelemetryCalculator"""
    
    def test_calculate_ocr(self, calculator, opportunities):
        """Test OCR calculation"""
        total = len(opportunities)
        captured = len([o for o in opportunities if o["captured"]])
        
        ocr = calculator.calculate_ocr(total, captured)
        
        # 3 captured out of 5 = 60%
        assert ocr == 0.60
        assert calculator.metrics.total_opportunities == 5
        assert calculator.metrics.captured_opportunities == 3
    
    def test_calculate_edge_per_trade(self, calculator, trades):
        """Test edge per trade calculation"""
        edge = calculator.calculate_edge_per_trade(trades)
        
        # Total PnL: 100 - 50 + 150 + 75 - 25 = 250
        # Edge: 250 / 5 = 50
        assert edge == 50.0
        assert calculator.metrics.total_trades == 5
        assert calculator.metrics.total_pnl == 250.0
    
    def test_calculate_box_stability(self, calculator, boxes):
        """Test box stability calculation"""
        stability = calculator.calculate_box_stability(boxes)
        
        # High stability due to consistent durations
        assert stability > 0.9
        assert stability <= 1.0
    
    def test_calculate_all(self, calculator, opportunities, trades, boxes):
        """Test calculating all metrics"""
        metrics = calculator.calculate_all(opportunities, trades, boxes)
        
        assert metrics.opportunity_capture_rate == 0.60
        assert metrics.edge_per_trade == 50.0
        assert metrics.box_stability > 0.9
        assert metrics.total_opportunities == 5
        assert metrics.captured_opportunities == 3
        assert metrics.total_trades == 5
        assert metrics.winning_trades == 3
        assert metrics.total_pnl == 250.0
    
    def test_is_ocr_healthy(self, calculator):
        """Test OCR health check"""
        # Below threshold
        calculator.metrics.opportunity_capture_rate = 0.60
        assert calculator.is_ocr_healthy() is False
        
        # At threshold
        calculator.metrics.opportunity_capture_rate = 0.70
        assert calculator.is_ocr_healthy() is True
        
        # Above threshold
        calculator.metrics.opportunity_capture_rate = 0.80
        assert calculator.is_ocr_healthy() is True
    
    def test_get_summary(self, calculator, opportunities, trades, boxes):
        """Test getting summary"""
        calculator.calculate_all(opportunities, trades, boxes)
        
        summary = calculator.get_summary()
        
        assert "opportunity_capture_rate" in summary
        assert "edge_per_trade" in summary
        assert "box_stability" in summary
        assert "ocr_healthy" in summary
        assert summary["ocr_healthy"] is False  # 60% < 70%


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
