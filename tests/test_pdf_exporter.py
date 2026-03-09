"""
Tests for PDF Performance Reports Exporter

Tests the report generator, PDF exporter, and templates.
"""

import pytest
from datetime import datetime, timedelta
from io import BytesIO
import os
import tempfile
import random

from backend.reporting.report_generator import (
    ReportGenerator,
    ReportType,
    TradeRecord,
    ModelMetrics,
    PerformanceSummary,
    ChartData,
    ReportData,
)
from backend.reporting.pdf_exporter import PDFExporter, generate_sample_report
from backend.reporting.templates.report_template import (
    ReportTemplate,
    DailyReportTemplate,
    WeeklyReportTemplate,
    MonthlyReportTemplate,
    TemplateConfig,
    get_template,
    list_templates,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_trades():
    """Generate sample trade records for testing"""
    trades = []
    base_date = datetime.now() - timedelta(days=7)
    markets = ["BTC-USD", "ETH-USD", "POLY-USD", "SOL-USD"]
    
    for i in range(20):
        pnl = random.uniform(-100, 150)
        trade = TradeRecord(
            trade_id=f"trade_{i}",
            timestamp=base_date + timedelta(hours=i*3),
            market=markets[i % len(markets)],
            side="BUY" if i % 2 == 0 else "SELL",
            entry_price=random.uniform(0.5, 1.0),
            exit_price=random.uniform(0.4, 1.1),
            size=random.uniform(10, 100),
            pnl=pnl,
            fees=random.uniform(0.1, 2.0),
            duration=random.uniform(60, 3600),
            outcome="win" if pnl > 5 else ("loss" if pnl < -5 else "breakeven"),
            model_confidence=random.uniform(0.5, 0.95),
        )
        trades.append(trade)
    
    return trades


@pytest.fixture
def sample_model_metrics():
    """Generate sample model metrics for testing"""
    return ModelMetrics(
        model_name="XGBoost Lead",
        version="v2.1.0",
        total_predictions=1000,
        correct_predictions=720,
        accuracy=0.72,
        precision=0.75,
        recall=0.68,
        f1_score=0.71,
        avg_confidence=0.78,
        calibration_score=0.82,
    )


@pytest.fixture
def report_generator(sample_trades, sample_model_metrics):
    """Create a report generator with sample data"""
    generator = ReportGenerator()
    generator.add_trades(sample_trades)
    generator.add_model_metrics(sample_model_metrics)
    return generator


@pytest.fixture
def pdf_exporter():
    """Create a PDF exporter instance"""
    return PDFExporter()


# =============================================================================
# ReportGenerator Tests
# =============================================================================

class TestReportGenerator:
    """Tests for ReportGenerator class"""
    
    def test_initialization(self):
        """Test report generator initialization"""
        generator = ReportGenerator()
        assert generator.min_trades_for_stats == 5
        assert generator.risk_free_rate == 0.02
        assert generator.get_trade_count() == 0
    
    def test_initialization_with_params(self):
        """Test report generator initialization with custom parameters"""
        generator = ReportGenerator(min_trades_for_stats=10, risk_free_rate=0.03)
        assert generator.min_trades_for_stats == 10
        assert generator.risk_free_rate == 0.03
    
    def test_add_trade(self):
        """Test adding a single trade"""
        generator = ReportGenerator()
        trade = TradeRecord(
            trade_id="test_1",
            timestamp=datetime.now(),
            market="BTC-USD",
            side="BUY",
            entry_price=0.75,
            exit_price=0.80,
            size=50.0,
            pnl=25.0,
            fees=1.0,
            duration=1800.0,
            outcome="win",
        )
        generator.add_trade(trade)
        assert generator.get_trade_count() == 1
    
    def test_add_trades(self, sample_trades):
        """Test adding multiple trades"""
        generator = ReportGenerator()
        generator.add_trades(sample_trades)
        assert generator.get_trade_count() == len(sample_trades)
    
    def test_load_trades_from_dict(self):
        """Test loading trades from dictionary format"""
        generator = ReportGenerator()
        trades_data = [
            {
                "trade_id": "t1",
                "timestamp": "2024-01-01T10:00:00",
                "market": "BTC-USD",
                "side": "BUY",
                "entry_price": 0.75,
                "exit_price": 0.80,
                "size": 50.0,
                "pnl": 25.0,
                "fees": 1.0,
                "duration": 1800.0,
            },
            {
                "trade_id": "t2",
                "timestamp": "2024-01-01T11:00:00",
                "market": "ETH-USD",
                "side": "SELL",
                "entry_price": 0.60,
                "exit_price": 0.55,
                "size": 100.0,
                "pnl": -50.0,
                "fees": 2.0,
                "duration": 3600.0,
            },
        ]
        generator.load_trades_from_dict(trades_data)
        assert generator.get_trade_count() == 2
    
    def test_generate_daily_report(self, report_generator):
        """Test generating a daily report"""
        report = report_generator.generate_report(
            report_type=ReportType.DAILY,
            account_balance_start=10000.0,
        )
        
        assert report is not None
        assert report.summary.report_type == ReportType.DAILY
        assert report.summary.start_date is not None
        assert report.summary.end_date is not None
    
    def test_generate_weekly_report(self, report_generator):
        """Test generating a weekly report"""
        report = report_generator.generate_report(
            report_type=ReportType.WEEKLY,
            account_balance_start=10000.0,
        )
        
        assert report is not None
        assert report.summary.report_type == ReportType.WEEKLY
    
    def test_generate_monthly_report(self, report_generator):
        """Test generating a monthly report"""
        report = report_generator.generate_report(
            report_type=ReportType.MONTHLY,
            account_balance_start=10000.0,
        )
        
        assert report is not None
        assert report.summary.report_type == ReportType.MONTHLY
    
    def test_summary_statistics(self, report_generator):
        """Test summary statistics calculation"""
        report = report_generator.generate_report(
            report_type=ReportType.WEEKLY,
            account_balance_start=10000.0,
        )
        
        summary = report.summary
        assert summary.total_trades > 0
        assert summary.winning_trades + summary.losing_trades + summary.breakeven_trades == summary.total_trades
        assert 0 <= summary.win_rate <= 1
        assert summary.starting_balance == 10000.0
    
    def test_chart_data_generation(self, report_generator):
        """Test chart data generation"""
        report = report_generator.generate_report(
            report_type=ReportType.WEEKLY,
        )
        
        assert len(report.charts) > 0
        # Should have PnL chart, pie chart, bar chart
        chart_types = [c.chart_type for c in report.charts]
        assert "line" in chart_types
        assert "pie" in chart_types
        assert "bar" in chart_types
    
    def test_additional_stats(self, report_generator):
        """Test additional statistics calculation"""
        report = report_generator.generate_report(
            report_type=ReportType.WEEKLY,
        )
        
        stats = report.additional_stats
        assert "avg_trade_size" in stats
        assert "total_fees" in stats
        assert "max_consecutive_wins" in stats
        assert "max_consecutive_losses" in stats
    
    def test_clear_data(self, report_generator):
        """Test clearing stored data"""
        assert report_generator.get_trade_count() > 0
        report_generator.clear()
        assert report_generator.get_trade_count() == 0
    
    def test_date_range(self, report_generator):
        """Test getting date range of trades"""
        start, end = report_generator.get_date_range()
        assert start is not None
        assert end is not None
        assert start <= end
    
    def test_empty_report(self):
        """Test generating report with no trades"""
        generator = ReportGenerator()
        report = generator.generate_report(ReportType.DAILY)
        
        assert report.summary.total_trades == 0
        assert report.summary.total_pnl == 0.0
        assert len(report.trades) == 0


class TestTradeRecord:
    """Tests for TradeRecord dataclass"""
    
    def test_trade_record_creation(self):
        """Test creating a trade record"""
        trade = TradeRecord(
            trade_id="test_1",
            timestamp=datetime.now(),
            market="BTC-USD",
            side="BUY",
            entry_price=0.75,
            exit_price=0.80,
            size=50.0,
            pnl=25.0,
            fees=1.0,
            duration=1800.0,
            outcome="win",
        )
        
        assert trade.trade_id == "test_1"
        assert trade.market == "BTC-USD"
        assert trade.pnl == 25.0
    
    def test_trade_record_optional_fields(self):
        """Test trade record with optional fields"""
        trade = TradeRecord(
            trade_id="test_2",
            timestamp=datetime.now(),
            market="ETH-USD",
            side="SELL",
            entry_price=0.60,
            exit_price=None,
            size=100.0,
            pnl=-50.0,
            fees=2.0,
            duration=3600.0,
            outcome="loss",
            model_confidence=0.85,
            golden_box_id="gb_123",
        )
        
        assert trade.exit_price is None
        assert trade.model_confidence == 0.85
        assert trade.golden_box_id == "gb_123"


class TestModelMetrics:
    """Tests for ModelMetrics dataclass"""
    
    def test_model_metrics_creation(self, sample_model_metrics):
        """Test creating model metrics"""
        metrics = sample_model_metrics
        
        assert metrics.model_name == "XGBoost Lead"
        assert metrics.version == "v2.1.0"
        assert metrics.accuracy == 0.72
        assert metrics.f1_score == 0.71


# =============================================================================
# PDFExporter Tests
# =============================================================================

class TestPDFExporter:
    """Tests for PDFExporter class"""
    
    def test_initialization(self):
        """Test PDF exporter initialization"""
        exporter = PDFExporter()
        assert exporter.title == "Polymarket AI Lead-Lag Scalper"
        assert exporter.subtitle == "Performance Report"
    
    def test_initialization_with_params(self):
        """Test PDF exporter initialization with custom parameters"""
        exporter = PDFExporter(
            page_size="a4",
            margin=1.0 * 72,  # 1 inch
            title="Custom Title",
            subtitle="Custom Subtitle",
        )
        assert exporter.title == "Custom Title"
        assert exporter.subtitle == "Custom Subtitle"
    
    def test_export_report_to_file(self, report_generator):
        """Test exporting report to file"""
        exporter = PDFExporter()
        report = report_generator.generate_report(
            report_type=ReportType.WEEKLY,
            account_balance_start=10000.0,
        )
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name
        
        try:
            result_path = exporter.export_report(report, output_path)
            assert result_path == output_path
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_export_report_to_bytes(self, report_generator):
        """Test exporting report to bytes"""
        exporter = PDFExporter()
        report = report_generator.generate_report(
            report_type=ReportType.WEEKLY,
            account_balance_start=10000.0,
        )
        
        pdf_bytes = exporter.export_to_bytes(report)
        
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        # Check PDF header
        assert pdf_bytes[:4] == b'%PDF'
    
    def test_export_without_trades_table(self, report_generator):
        """Test exporting without trades table"""
        exporter = PDFExporter()
        report = report_generator.generate_report(
            report_type=ReportType.WEEKLY,
        )
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name
        
        try:
            exporter.export_report(
                report,
                output_path,
                include_trades_table=False,
            )
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_export_without_model_metrics(self, report_generator):
        """Test exporting without model metrics"""
        exporter = PDFExporter()
        report = report_generator.generate_report(
            report_type=ReportType.WEEKLY,
        )
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name
        
        try:
            exporter.export_report(
                report,
                output_path,
                include_model_metrics=False,
            )
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_export_empty_report(self):
        """Test exporting empty report"""
        exporter = PDFExporter()
        generator = ReportGenerator()
        report = generator.generate_report(ReportType.DAILY)
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name
        
        try:
            exporter.export_report(report, output_path)
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_generate_sample_report(self):
        """Test sample report generation"""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name
        
        try:
            result = generate_sample_report(output_path)
            assert result == output_path
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


# =============================================================================
# Template Tests
# =============================================================================

class TestReportTemplates:
    """Tests for report templates"""
    
    def test_daily_template(self):
        """Test daily report template"""
        template = DailyReportTemplate()
        
        assert template.get_report_type() == "daily"
        
        end_date = datetime.now()
        start, end = template.get_date_range(end_date)
        assert (end - start).days == 1
        
        sections = template.get_sections()
        assert "header" in sections
        assert "summary" in sections
        assert "trades_table" in sections
    
    def test_weekly_template(self):
        """Test weekly report template"""
        template = WeeklyReportTemplate()
        
        assert template.get_report_type() == "weekly"
        
        end_date = datetime.now()
        start, end = template.get_date_range(end_date)
        assert (end - start).days == 7
    
    def test_monthly_template(self):
        """Test monthly report template"""
        template = MonthlyReportTemplate()
        
        assert template.get_report_type() == "monthly"
        
        end_date = datetime.now()
        start, end = template.get_date_range(end_date)
        assert (end - start).days == 30
    
    def test_template_config(self):
        """Test template configuration"""
        config = TemplateConfig(
            page_size="a4",
            margin=1.0 * 72,
            report_title="Test Report",
        )
        
        template = DailyReportTemplate(config)
        assert template.config.report_title == "Test Report"
        assert template.config.page_size == "a4"
    
    def test_get_template_factory(self):
        """Test template factory function"""
        daily = get_template("daily")
        assert isinstance(daily, DailyReportTemplate)
        
        weekly = get_template("weekly")
        assert isinstance(weekly, WeeklyReportTemplate)
        
        monthly = get_template("monthly")
        assert isinstance(monthly, MonthlyReportTemplate)
    
    def test_get_template_invalid(self):
        """Test template factory with invalid type"""
        with pytest.raises(ValueError):
            get_template("invalid_type")
    
    def test_list_templates(self):
        """Test listing available templates"""
        templates = list_templates()
        assert "daily" in templates
        assert "weekly" in templates
        assert "monthly" in templates
    
    def test_chart_configs(self):
        """Test chart configurations"""
        template = WeeklyReportTemplate()
        configs = template.get_chart_configs()
        
        assert len(configs) > 0
        chart_types = [c["type"] for c in configs]
        assert "line" in chart_types or "bar" in chart_types
    
    def test_summary_metrics(self):
        """Test summary metrics list"""
        template = MonthlyReportTemplate()
        metrics = template.get_summary_metrics()
        
        assert "total_trades" in metrics
        assert "win_rate" in metrics
        assert "total_pnl" in metrics
    
    def test_customize_for_performance(self):
        """Test performance-based customization"""
        template = WeeklyReportTemplate()
        
        # Good performance
        config = template.customize_for_performance(
            win_rate=0.7,
            total_pnl=1000.0,
            sharpe_ratio=2.5,
        )
        assert config is not None
        
        # Poor performance
        config = template.customize_for_performance(
            win_rate=0.3,
            total_pnl=-500.0,
            sharpe_ratio=-1.0,
        )
        assert config is not None


class TestTemplateConfig:
    """Tests for TemplateConfig dataclass"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = TemplateConfig()
        
        assert config.page_size == "letter"
        assert config.include_summary is True
        assert config.include_charts is True
        assert config.max_trades_in_table == 50
    
    def test_custom_config(self):
        """Test custom configuration values"""
        config = TemplateConfig(
            page_size="a4",
            margin=1.0 * 72,
            title_size=20,
            include_trades_table=False,
        )
        
        assert config.page_size == "a4"
        assert config.title_size == 20
        assert config.include_trades_table is False


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the complete reporting pipeline"""
    
    def test_full_report_generation_pipeline(self):
        """Test complete report generation from data to PDF"""
        # Create generator
        generator = ReportGenerator()
        
        # Add sample trades
        trades = []
        base_date = datetime.now() - timedelta(days=7)
        for i in range(30):
            pnl = random.uniform(-100, 150)
            trade = TradeRecord(
                trade_id=f"trade_{i}",
                timestamp=base_date + timedelta(hours=i*2),
                market=random.choice(["BTC-USD", "ETH-USD"]),
                side=random.choice(["BUY", "SELL"]),
                entry_price=random.uniform(0.5, 1.0),
                exit_price=random.uniform(0.4, 1.1),
                size=random.uniform(10, 100),
                pnl=pnl,
                fees=random.uniform(0.1, 2.0),
                duration=random.uniform(60, 3600),
                outcome="win" if pnl > 5 else ("loss" if pnl < -5 else "breakeven"),
            )
            trades.append(trade)
        
        generator.add_trades(trades)
        
        # Add model metrics
        model = ModelMetrics(
            model_name="XGBoost",
            version="v1.0",
            total_predictions=500,
            correct_predictions=350,
            accuracy=0.70,
            precision=0.72,
            recall=0.68,
            f1_score=0.70,
            avg_confidence=0.75,
            calibration_score=0.80,
        )
        generator.add_model_metrics(model)
        
        # Generate report
        report = generator.generate_report(
            report_type=ReportType.WEEKLY,
            account_balance_start=10000.0,
        )
        
        # Export to PDF
        exporter = PDFExporter()
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name
        
        try:
            result = exporter.export_report(report, output_path)
            
            # Verify
            assert os.path.exists(result)
            assert os.path.getsize(result) > 1000  # Should be substantial
            
            # Verify PDF structure
            with open(result, 'rb') as f:
                content = f.read()
                assert content[:4] == b'%PDF'
                assert b'%%EOF' in content
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_all_report_types(self):
        """Test generating all report types"""
        generator = ReportGenerator()
        
        # Add some trades
        for i in range(20):
            trade = TradeRecord(
                trade_id=f"t{i}",
                timestamp=datetime.now() - timedelta(hours=i),
                market="BTC-USD",
                side="BUY",
                entry_price=0.75,
                exit_price=0.80,
                size=50.0,
                pnl=random.uniform(-50, 100),
                fees=1.0,
                duration=1800.0,
                outcome="win",
            )
            generator.add_trade(trade)
        
        exporter = PDFExporter()
        
        for report_type in [ReportType.DAILY, ReportType.WEEKLY, ReportType.MONTHLY]:
            report = generator.generate_report(report_type)
            
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                output_path = f.name
            
            try:
                exporter.export_report(report, output_path)
                assert os.path.exists(output_path)
                assert os.path.getsize(output_path) > 0
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling"""
    
    def test_single_trade_report(self):
        """Test report with single trade"""
        generator = ReportGenerator()
        trade = TradeRecord(
            trade_id="single",
            timestamp=datetime.now(),
            market="BTC-USD",
            side="BUY",
            entry_price=0.75,
            exit_price=0.80,
            size=50.0,
            pnl=25.0,
            fees=1.0,
            duration=1800.0,
            outcome="win",
        )
        generator.add_trade(trade)
        
        report = generator.generate_report(ReportType.DAILY)
        assert report.summary.total_trades == 1
    
    def test_all_winning_trades(self):
        """Test report with all winning trades"""
        generator = ReportGenerator()
        
        for i in range(10):
            trade = TradeRecord(
                trade_id=f"win_{i}",
                timestamp=datetime.now() - timedelta(hours=i),
                market="BTC-USD",
                side="BUY",
                entry_price=0.75,
                exit_price=0.80,
                size=50.0,
                pnl=50.0,
                fees=1.0,
                duration=1800.0,
                outcome="win",
            )
            generator.add_trade(trade)
        
        report = generator.generate_report(ReportType.DAILY)
        assert report.summary.win_rate == 1.0
        assert report.summary.losing_trades == 0
    
    def test_all_losing_trades(self):
        """Test report with all losing trades"""
        generator = ReportGenerator()
        
        for i in range(10):
            trade = TradeRecord(
                trade_id=f"loss_{i}",
                timestamp=datetime.now() - timedelta(hours=i),
                market="BTC-USD",
                side="BUY",
                entry_price=0.75,
                exit_price=0.70,
                size=50.0,
                pnl=-50.0,
                fees=1.0,
                duration=1800.0,
                outcome="loss",
            )
            generator.add_trade(trade)
        
        report = generator.generate_report(ReportType.DAILY)
        assert report.summary.win_rate == 0.0
        assert report.summary.winning_trades == 0
    
    def test_very_large_pnl_values(self):
        """Test report with very large PnL values"""
        generator = ReportGenerator()
        
        for i in range(5):
            trade = TradeRecord(
                trade_id=f"large_{i}",
                timestamp=datetime.now() - timedelta(hours=i),
                market="BTC-USD",
                side="BUY",
                entry_price=0.75,
                exit_price=0.80,
                size=10000.0,
                pnl=100000.0,
                fees=100.0,
                duration=1800.0,
                outcome="win",
            )
            generator.add_trade(trade)
        
        report = generator.generate_report(ReportType.DAILY)
        assert report.summary.total_pnl == 500000.0
    
    def test_negative_balance(self):
        """Test report with negative ending balance"""
        generator = ReportGenerator()
        
        for i in range(10):
            trade = TradeRecord(
                trade_id=f"neg_{i}",
                timestamp=datetime.now() - timedelta(hours=i),
                market="BTC-USD",
                side="BUY",
                entry_price=0.75,
                exit_price=0.70,
                size=100.0,
                pnl=-200.0,
                fees=5.0,
                duration=1800.0,
                outcome="loss",
            )
            generator.add_trade(trade)
        
        report = generator.generate_report(
            ReportType.DAILY,
            account_balance_start=1000.0,
        )
        assert report.summary.ending_balance < report.summary.starting_balance
        assert report.summary.return_percentage < 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
