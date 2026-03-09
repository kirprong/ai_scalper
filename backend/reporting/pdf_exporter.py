"""
PDF Exporter Module

Generates professional PDF performance reports from trading data using reportlab.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from io import BytesIO
import logging
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
    KeepTogether,
    HRFlowable,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.widgets.markers import makeMarker

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import numpy as np

from backend.reporting.report_generator import (
    ReportData,
    PerformanceSummary,
    TradeRecord,
    ModelMetrics,
    ChartData,
    ReportType,
)

logger = logging.getLogger(__name__)


# Color scheme for professional reports
COLORS = {
    "primary": colors.HexColor("#1a365d"),  # Dark blue
    "secondary": colors.HexColor("#2c5282"),  # Medium blue
    "accent": colors.HexColor("#3182ce"),  # Light blue
    "success": colors.HexColor("#38a169"),  # Green
    "danger": colors.HexColor("#e53e3e"),  # Red
    "warning": colors.HexColor("#d69e2e"),  # Yellow
    "neutral": colors.HexColor("#718096"),  # Gray
    "background": colors.HexColor("#f7fafc"),  # Light gray
    "text": colors.HexColor("#1a202c"),  # Dark gray
}


class PDFExporter:
    """
    PDF Exporter for Performance Reports
    
    Generates professional PDF reports with charts and statistics
    from trading data.
    """
    
    def __init__(
        self,
        page_size: str = "letter",
        margin: float = 0.75 * inch,
        title: str = "Polymarket AI Lead-Lag Scalper",
        subtitle: str = "Performance Report",
    ):
        """
        Initialize PDF exporter.
        
        Args:
            page_size: Page size ('letter' or 'a4')
            margin: Page margin in inches
            title: Report title
            subtitle: Report subtitle
        """
        self.page_size = letter if page_size.lower() == "letter" else A4
        self.margin = margin
        self.title = title
        self.subtitle = subtitle
        self.styles = self._create_styles()
        
    def _create_styles(self) -> Dict[str, ParagraphStyle]:
        """Create custom paragraph styles"""
        styles = getSampleStyleSheet()
        
        # Title style
        styles.add(ParagraphStyle(
            name="ReportTitle",
            parent=styles["Heading1"],
            fontSize=24,
            textColor=COLORS["primary"],
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        ))
        
        # Subtitle style
        styles.add(ParagraphStyle(
            name="ReportSubtitle",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=COLORS["secondary"],
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName="Helvetica",
        ))
        
        # Section header style
        styles.add(ParagraphStyle(
            name="SectionHeader",
            parent=styles["Heading2"],
            fontSize=16,
            textColor=COLORS["primary"],
            spaceBefore=20,
            spaceAfter=10,
            fontName="Helvetica-Bold",
        ))
        
        # Subsection header style
        styles.add(ParagraphStyle(
            name="SubsectionHeader",
            parent=styles["Heading3"],
            fontSize=12,
            textColor=COLORS["secondary"],
            spaceBefore=12,
            spaceAfter=6,
            fontName="Helvetica-Bold",
        ))
        
        # Body text style
        styles.add(ParagraphStyle(
            name="BodyText",
            parent=styles["Normal"],
            fontSize=10,
            textColor=COLORS["text"],
            spaceAfter=6,
            fontName="Helvetica",
        ))
        
        # Metric label style
        styles.add(ParagraphStyle(
            name="MetricLabel",
            parent=styles["Normal"],
            fontSize=9,
            textColor=COLORS["neutral"],
            fontName="Helvetica",
        ))
        
        # Metric value style
        styles.add(ParagraphStyle(
            name="MetricValue",
            parent=styles["Normal"],
            fontSize=14,
            textColor=COLORS["text"],
            fontName="Helvetica-Bold",
        ))
        
        # Table header style
        styles.add(ParagraphStyle(
            name="TableHeader",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.white,
            fontName="Helvetica-Bold",
            alignment=TA_CENTER,
        ))
        
        # Table cell style
        styles.add(ParagraphStyle(
            name="TableCell",
            parent=styles["Normal"],
            fontSize=9,
            textColor=COLORS["text"],
            fontName="Helvetica",
            alignment=TA_CENTER,
        ))
        
        return styles
    
    def export_report(
        self,
        report_data: ReportData,
        output_path: str,
        include_trades_table: bool = True,
        include_model_metrics: bool = True,
    ) -> str:
        """
        Export report to PDF file.
        
        Args:
            report_data: Report data to export
            output_path: Output file path
            include_trades_table: Whether to include detailed trades table
            include_model_metrics: Whether to include ML model metrics
            
        Returns:
            Path to generated PDF file
        """
        # Create document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=self.page_size,
            rightMargin=self.margin,
            leftMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin,
        )
        
        # Build story (content)
        story = []
        
        # Add header
        story.extend(self._create_header(report_data.summary))
        
        # Add summary statistics
        story.extend(self._create_summary_section(report_data.summary))
        
        # Add charts
        story.extend(self._create_charts_section(report_data.charts))
        
        # Add trades table if requested
        if include_trades_table and report_data.trades:
            story.extend(self._create_trades_section(report_data.trades))
        
        # Add model metrics if requested
        if include_model_metrics and report_data.model_metrics:
            story.extend(self._create_model_metrics_section(report_data.model_metrics))
        
        # Add footer
        story.extend(self._create_footer(report_data.summary))
        
        # Build PDF
        doc.build(story)
        
        logger.info(f"PDF report exported to: {output_path}")
        return output_path
    
    def export_to_bytes(
        self,
        report_data: ReportData,
        include_trades_table: bool = True,
        include_model_metrics: bool = True,
    ) -> bytes:
        """
        Export report to bytes (for in-memory use).
        
        Args:
            report_data: Report data to export
            include_trades_table: Whether to include detailed trades table
            include_model_metrics: Whether to include ML model metrics
            
        Returns:
            PDF content as bytes
        """
        buffer = BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.page_size,
            rightMargin=self.margin,
            leftMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin,
        )
        
        story = []
        story.extend(self._create_header(report_data.summary))
        story.extend(self._create_summary_section(report_data.summary))
        story.extend(self._create_charts_section(report_data.charts))
        
        if include_trades_table and report_data.trades:
            story.extend(self._create_trades_section(report_data.trades))
        
        if include_model_metrics and report_data.model_metrics:
            story.extend(self._create_model_metrics_section(report_data.model_metrics))
        
        story.extend(self._create_footer(report_data.summary))
        
        doc.build(story)
        
        return buffer.getvalue()
    
    def _create_header(self, summary: PerformanceSummary) -> List:
        """Create report header"""
        elements = []
        
        # Title
        elements.append(Paragraph(self.title, self.styles["ReportTitle"]))
        elements.append(Paragraph(self.subtitle, self.styles["ReportSubtitle"]))
        
        # Report type and date range
        report_type_name = summary.report_type.value.capitalize()
        date_range = f"{summary.start_date.strftime('%Y-%m-%d')} to {summary.end_date.strftime('%Y-%m-%d')}"
        
        elements.append(Paragraph(
            f"<b>{report_type_name} Report</b> | {date_range}",
            self.styles["BodyText"],
        ))
        
        # Horizontal line
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(
            width="100%",
            thickness=2,
            color=COLORS["primary"],
            spaceBefore=5,
            spaceAfter=20,
        ))
        
        return elements
    
    def _create_summary_section(self, summary: PerformanceSummary) -> List:
        """Create summary statistics section"""
        elements = []
        
        elements.append(Paragraph("Performance Summary", self.styles["SectionHeader"]))
        
        # Create summary table with key metrics
        # Row 1: Key trading metrics
        row1_data = [
            self._create_metric_cell("Total Trades", str(summary.total_trades)),
            self._create_metric_cell("Win Rate", f"{summary.win_rate:.1%}"),
            self._create_metric_cell("Total PnL", f"${summary.total_pnl:,.2f}"),
            self._create_metric_cell("Return", f"{summary.return_percentage:.2f}%"),
        ]
        
        # Row 2: Risk metrics
        row2_data = [
            self._create_metric_cell("Profit Factor", f"{summary.profit_factor:.2f}"),
            self._create_metric_cell("Sharpe Ratio", f"{summary.sharpe_ratio:.2f}"),
            self._create_metric_cell("Max Drawdown", f"${summary.max_drawdown:,.2f}"),
            self._create_metric_cell("Avg Duration", f"{summary.avg_trade_duration/60:.1f} min"),
        ]
        
        # Row 3: Trade breakdown
        row3_data = [
            self._create_metric_cell("Winning Trades", str(summary.winning_trades), COLORS["success"]),
            self._create_metric_cell("Losing Trades", str(summary.losing_trades), COLORS["danger"]),
            self._create_metric_cell("Breakeven", str(summary.breakeven_trades), COLORS["warning"]),
            self._create_metric_cell("OCR", f"{summary.opportunity_capture_rate:.1%}"),
        ]
        
        # Create table
        table_data = [row1_data, row2_data, row3_data]
        
        # Flatten for Table
        flat_data = []
        for row in table_data:
            flat_row = []
            for cell in row:
                flat_row.append(cell)
            flat_data.append(flat_row)
        
        col_width = (self.page_size[0] - 2 * self.margin) / 4
        
        table = Table(flat_data, colWidths=[col_width] * 4)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLORS["background"]),
            ('BOX', (0, 0), (-1, -1), 1, COLORS["neutral"]),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLORS["neutral"]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 20))
        
        # Account summary
        elements.append(Paragraph("Account Summary", self.styles["SubsectionHeader"]))
        
        account_data = [
            ["Starting Balance", f"${summary.starting_balance:,.2f}"],
            ["Ending Balance", f"${summary.ending_balance:,.2f}"],
            ["Net Change", f"${summary.ending_balance - summary.starting_balance:,.2f}"],
        ]
        
        account_table = Table(account_data, colWidths=[2*inch, 2*inch])
        account_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), COLORS["background"]),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), COLORS["text"]),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BOX', (0, 0), (-1, -1), 1, COLORS["neutral"]),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLORS["neutral"]),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        elements.append(account_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_metric_cell(
        self,
        label: str,
        value: str,
        value_color: colors.Color = None,
    ) -> Table:
        """Create a metric cell with label and value"""
        if value_color is None:
            value_color = COLORS["text"]
        
        data = [
            [Paragraph(label, self.styles["MetricLabel"])],
            [Paragraph(f"<font color=\"{value_color.hexval()}\">{value}</font>", self.styles["MetricValue"])],
        ]
        
        table = Table(data, colWidths=[1.5*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        
        return table
    
    def _create_charts_section(self, charts: List[ChartData]) -> List:
        """Create charts section with matplotlib-generated images"""
        elements = []
        
        if not charts:
            return elements
        
        elements.append(Paragraph("Performance Charts", self.styles["SectionHeader"]))
        
        for chart in charts:
            try:
                img_data = self._generate_chart_image(chart)
                if img_data:
                    img = Image(img_data, width=6*inch, height=3*inch)
                    elements.append(Paragraph(chart.title, self.styles["SubsectionHeader"]))
                    elements.append(img)
                    elements.append(Spacer(1, 15))
            except Exception as e:
                logger.warning(f"Failed to generate chart '{chart.title}': {e}")
        
        return elements
    
    def _generate_chart_image(self, chart: ChartData) -> Optional[BytesIO]:
        """Generate chart image using matplotlib"""
        fig, ax = plt.subplots(figsize=(8, 4))
        
        try:
            if chart.chart_type == "line":
                self._plot_line_chart(ax, chart)
            elif chart.chart_type == "bar":
                self._plot_bar_chart(ax, chart)
            elif chart.chart_type == "pie":
                self._plot_pie_chart(ax, chart)
            elif chart.chart_type == "stacked_bar":
                self._plot_stacked_bar_chart(ax, chart)
            else:
                logger.warning(f"Unknown chart type: {chart.chart_type}")
                return None
            
            ax.set_title(chart.title)
            ax.set_xlabel(chart.x_label)
            ax.set_ylabel(chart.y_label)
            
            plt.tight_layout()
            
            # Save to bytes
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            plt.close(fig)
            
            return buffer
            
        except Exception as e:
            plt.close(fig)
            logger.error(f"Error generating chart: {e}")
            return None
    
    def _plot_line_chart(self, ax, chart: ChartData):
        """Plot line chart"""
        x_data = chart.x_data
        if x_data and isinstance(x_data[0], datetime):
            ax.plot(x_data, chart.y_data, marker='o', markersize=3, linewidth=1.5)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(x_data)//7)))
            plt.xticks(rotation=45)
        else:
            ax.plot(x_data, chart.y_data, marker='o', markersize=3, linewidth=1.5)
        
        # Add zero line
        ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
        
        # Color based on values
        if chart.y_data and min(chart.y_data) < 0:
            ax.fill_between(
                range(len(x_data)) if not isinstance(x_data[0], datetime) else x_data,
                chart.y_data,
                0,
                where=[y >= 0 for y in chart.y_data],
                alpha=0.3,
                color='green',
            )
            ax.fill_between(
                range(len(x_data)) if not isinstance(x_data[0], datetime) else x_data,
                chart.y_data,
                0,
                where=[y < 0 for y in chart.y_data],
                alpha=0.3,
                color='red',
            )
    
    def _plot_bar_chart(self, ax, chart: ChartData):
        """Plot bar chart"""
        colors_list = []
        for y in chart.y_data:
            if y > 0:
                colors_list.append('#38a169')  # Green
            elif y < 0:
                colors_list.append('#e53e3e')  # Red
            else:
                colors_list.append('#718096')  # Gray
        
        bars = ax.bar(chart.x_data, chart.y_data, color=colors_list)
        
        # Rotate x labels if many items
        if len(chart.x_data) > 5:
            plt.xticks(rotation=45, ha='right')
        
        # Add value labels on bars
        for bar, val in zip(bars, chart.y_data):
            height = bar.get_height()
            ax.annotate(
                f'{val:.0f}' if abs(val) >= 1 else f'{val:.2f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha='center',
                va='bottom',
                fontsize=8,
            )
    
    def _plot_pie_chart(self, ax, chart: ChartData):
        """Plot pie chart"""
        colors_map = {
            'win': '#38a169',
            'loss': '#e53e3e',
            'breakeven': '#718096',
        }
        
        pie_colors = []
        for label in chart.x_data:
            pie_colors.append(colors_map.get(label.lower(), '#3182ce'))
        
        wedges, texts, autotexts = ax.pie(
            chart.y_data,
            labels=chart.x_data,
            colors=pie_colors,
            autopct='%1.1f%%',
            startangle=90,
        )
        
        for autotext in autotexts:
            autotext.set_fontsize(9)
    
    def _plot_stacked_bar_chart(self, ax, chart: ChartData):
        """Plot stacked bar chart"""
        # Extract outcome data
        outcomes_data = chart.y_data
        categories = ['win', 'loss', 'breakeven']
        colors_map = {'win': '#38a169', 'loss': '#e53e3e', 'breakeven': '#718096'}
        
        # Prepare data
        bottom = np.zeros(len(chart.x_data))
        
        for category in categories:
            values = [d.get(category, 0) for d in outcomes_data]
            ax.bar(
                chart.x_data,
                values,
                bottom=bottom,
                label=category.capitalize(),
                color=colors_map[category],
            )
            bottom += np.array(values)
        
        ax.legend(loc='upper right')
        
        if len(chart.x_data) > 5:
            plt.xticks(rotation=45, ha='right')
    
    def _create_trades_section(self, trades: List[TradeRecord]) -> List:
        """Create detailed trades table section"""
        elements = []
        
        elements.append(Paragraph("Trade History", self.styles["SectionHeader"]))
        
        # Limit to last 50 trades for PDF
        display_trades = trades[-50:] if len(trades) > 50 else trades
        
        if len(trades) > 50:
            elements.append(Paragraph(
                f"Showing last 50 of {len(trades)} trades",
                self.styles["BodyText"],
            ))
        
        # Table header
        header = ["Time", "Market", "Side", "Size", "Entry", "Exit", "PnL", "Outcome"]
        
        # Table data
        data = [header]
        for trade in display_trades:
            row = [
                trade.timestamp.strftime("%m/%d %H:%M"),
                trade.market[:15] + "..." if len(trade.market) > 15 else trade.market,
                trade.side[:3],
                f"{trade.size:.2f}",
                f"{trade.entry_price:.4f}",
                f"{trade.exit_price:.4f}" if trade.exit_price else "-",
                f"${trade.pnl:.2f}",
                trade.outcome[:3].upper(),
            ]
            data.append(row)
        
        # Create table
        col_widths = [0.9*inch, 1.2*inch, 0.5*inch, 0.6*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.6*inch]
        
        table = Table(data, colWidths=col_widths)
        
        # Style table
        style_commands = [
            ('BACKGROUND', (0, 0), (-1, 0), COLORS["primary"]),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 1, COLORS["neutral"]),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLORS["neutral"]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]
        
        # Color rows based on outcome
        for i, trade in enumerate(display_trades, start=1):
            if trade.outcome == "win":
                style_commands.append(('BACKGROUND', (6, i), (6, i), colors.HexColor("#c6f6d5")))
            elif trade.outcome == "loss":
                style_commands.append(('BACKGROUND', (6, i), (6, i), colors.HexColor("#fed7d7")))
        
        table.setStyle(TableStyle(style_commands))
        
        elements.append(table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_model_metrics_section(self, metrics: List[ModelMetrics]) -> List:
        """Create ML model metrics section"""
        elements = []
        
        elements.append(Paragraph("ML Model Performance", self.styles["SectionHeader"]))
        
        # Table header
        header = ["Model", "Version", "Accuracy", "Precision", "Recall", "F1 Score", "Calibration"]
        
        data = [header]
        for m in metrics:
            row = [
                m.model_name[:12],
                m.version,
                f"{m.accuracy:.1%}",
                f"{m.precision:.1%}",
                f"{m.recall:.1%}",
                f"{m.f1_score:.2f}",
                f"{m.calibration_score:.2f}",
            ]
            data.append(row)
        
        col_widths = [1.1*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.7*inch, 0.9*inch]
        
        table = Table(data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLORS["secondary"]),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 1, COLORS["neutral"]),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLORS["neutral"]),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLORS["background"]]),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_footer(self, summary: PerformanceSummary) -> List:
        """Create report footer"""
        elements = []
        
        elements.append(Spacer(1, 20))
        elements.append(HRFlowable(
            width="100%",
            thickness=1,
            color=COLORS["neutral"],
            spaceBefore=10,
            spaceAfter=10,
        ))
        
        # Generation info
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elements.append(Paragraph(
            f"<i>Report generated on {generated_at}</i>",
            self.styles["MetricLabel"],
        ))
        
        elements.append(Paragraph(
            "<i>Polymarket AI Lead-Lag Scalper - Performance Analytics</i>",
            self.styles["MetricLabel"],
        ))
        
        return elements


def generate_sample_report(output_path: str = "sample_report.pdf") -> str:
    """
    Generate a sample report for testing purposes.
    
    Args:
        output_path: Output file path
        
    Returns:
        Path to generated PDF file
    """
    from backend.reporting.report_generator import ReportGenerator, TradeRecord, ModelMetrics
    
    # Create generator
    generator = ReportGenerator()
    
    # Add sample trades
    import random
    from datetime import timedelta
    
    base_date = datetime.now() - timedelta(days=7)
    markets = ["BTC-USD", "ETH-USD", "POLY-USD", "SOL-USD"]
    
    for i in range(50):
        pnl = random.uniform(-100, 150)
        trade = TradeRecord(
            trade_id=f"trade_{i}",
            timestamp=base_date + timedelta(hours=i*3, minutes=random.randint(0, 59)),
            market=random.choice(markets),
            side=random.choice(["BUY", "SELL"]),
            entry_price=random.uniform(0.5, 1.0),
            exit_price=random.uniform(0.4, 1.1),
            size=random.uniform(10, 100),
            pnl=pnl,
            fees=random.uniform(0.1, 2.0),
            duration=random.uniform(60, 3600),
            outcome="win" if pnl > 5 else ("loss" if pnl < -5 else "breakeven"),
            model_confidence=random.uniform(0.5, 0.95),
        )
        generator.add_trade(trade)
    
    # Add model metrics
    model = ModelMetrics(
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
    generator.add_model_metrics(model)
    
    # Generate report
    report_data = generator.generate_report(
        report_type=ReportType.WEEKLY,
        account_balance_start=10000.0,
    )
    
    # Export to PDF
    exporter = PDFExporter()
    return exporter.export_report(report_data, output_path)


if __name__ == "__main__":
    # Generate sample report when run directly
    output = generate_sample_report()
    print(f"Sample report generated: {output}")
