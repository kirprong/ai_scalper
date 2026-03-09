"""
Report Generator Module

Collects data from telemetry/metrics and aggregates trading statistics
for PDF report generation.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Report type enumeration"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


@dataclass
class TradeRecord:
    """Individual trade record"""
    trade_id: str
    timestamp: datetime
    market: str
    side: str  # 'BUY' or 'SELL'
    entry_price: float
    exit_price: Optional[float]
    size: float
    pnl: float
    fees: float
    duration: float  # seconds
    outcome: str  # 'win', 'loss', 'breakeven'
    model_confidence: Optional[float] = None
    golden_box_id: Optional[str] = None


@dataclass
class ModelMetrics:
    """ML model performance metrics"""
    model_name: str
    version: str
    total_predictions: int
    correct_predictions: int
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    avg_confidence: float
    calibration_score: float  # How well calibrated are confidence scores


@dataclass
class PerformanceSummary:
    """Aggregated performance summary"""
    # Time period
    start_date: datetime
    end_date: datetime
    report_type: ReportType
    
    # Trading metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    win_rate: float = 0.0
    
    # PnL metrics
    total_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    
    # Risk metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    avg_trade_duration: float = 0.0
    
    # Opportunity metrics
    total_opportunities: int = 0
    captured_opportunities: int = 0
    opportunity_capture_rate: float = 0.0
    
    # ML metrics
    model_accuracy: float = 0.0
    avg_model_confidence: float = 0.0
    
    # Account metrics
    starting_balance: float = 0.0
    ending_balance: float = 0.0
    return_percentage: float = 0.0


@dataclass
class ChartData:
    """Data container for chart generation"""
    chart_type: str
    title: str
    x_data: List[Any]
    y_data: List[Any]
    x_label: str = ""
    y_label: str = ""
    series_name: str = ""


@dataclass
class ReportData:
    """Complete report data container"""
    summary: PerformanceSummary
    trades: List[TradeRecord] = field(default_factory=list)
    model_metrics: List[ModelMetrics] = field(default_factory=list)
    charts: List[ChartData] = field(default_factory=list)
    additional_stats: Dict[str, Any] = field(default_factory=dict)


class ReportGenerator:
    """
    Report Generator
    
    Collects data from telemetry/metrics and aggregates trading statistics
    for PDF report generation.
    """
    
    def __init__(
        self,
        min_trades_for_stats: int = 5,
        risk_free_rate: float = 0.02,  # Annual risk-free rate
    ):
        """
        Initialize report generator.
        
        Args:
            min_trades_for_stats: Minimum trades required for meaningful statistics
            risk_free_rate: Annual risk-free rate for Sharpe ratio calculation
        """
        self.min_trades_for_stats = min_trades_for_stats
        self.risk_free_rate = risk_free_rate
        self._trades: List[TradeRecord] = []
        self._model_metrics: List[ModelMetrics] = []
        
    def add_trade(self, trade: TradeRecord) -> None:
        """Add a trade record"""
        self._trades.append(trade)
        
    def add_trades(self, trades: List[TradeRecord]) -> None:
        """Add multiple trade records"""
        self._trades.extend(trades)
        
    def add_model_metrics(self, metrics: ModelMetrics) -> None:
        """Add model performance metrics"""
        self._model_metrics.append(metrics)
        
    def load_trades_from_dict(self, trades_data: List[Dict[str, Any]]) -> None:
        """
        Load trades from dictionary format.
        
        Args:
            trades_data: List of trade dictionaries
        """
        for data in trades_data:
            trade = TradeRecord(
                trade_id=data.get("trade_id", str(len(self._trades))),
                timestamp=self._parse_datetime(data.get("timestamp", datetime.now())),
                market=data.get("market", "UNKNOWN"),
                side=data.get("side", "BUY"),
                entry_price=float(data.get("entry_price", 0)),
                exit_price=float(data.get("exit_price", 0)) if data.get("exit_price") else None,
                size=float(data.get("size", 0)),
                pnl=float(data.get("pnl", 0)),
                fees=float(data.get("fees", 0)),
                duration=float(data.get("duration", 0)),
                outcome=self._determine_outcome(float(data.get("pnl", 0))),
                model_confidence=float(data.get("model_confidence", 0)) if data.get("model_confidence") else None,
                golden_box_id=data.get("golden_box_id"),
            )
            self._trades.append(trade)
            
    def _parse_datetime(self, dt: Any) -> datetime:
        """Parse datetime from various formats"""
        if isinstance(dt, datetime):
            return dt
        if isinstance(dt, str):
            try:
                return datetime.fromisoformat(dt.replace("Z", "+00:00"))
            except ValueError:
                return datetime.now()
        return datetime.now()
    
    def _determine_outcome(self, pnl: float, threshold: float = 0.01) -> str:
        """Determine trade outcome based on PnL"""
        if pnl > threshold:
            return "win"
        elif pnl < -threshold:
            return "loss"
        else:
            return "breakeven"
    
    def generate_report(
        self,
        report_type: ReportType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        account_balance_start: float = 10000.0,
        account_balance_end: Optional[float] = None,
    ) -> ReportData:
        """
        Generate a performance report.
        
        Args:
            report_type: Type of report (daily, weekly, monthly)
            start_date: Report start date (auto-calculated if None)
            end_date: Report end date (defaults to now)
            account_balance_start: Starting account balance
            account_balance_end: Ending account balance (calculated if None)
            
        Returns:
            ReportData object with complete report information
        """
        # Set date range
        end_date = end_date or datetime.now()
        start_date = start_date or self._calculate_start_date(report_type, end_date)
        
        # Filter trades by date range
        filtered_trades = [
            t for t in self._trades
            if start_date <= t.timestamp <= end_date
        ]
        
        # Calculate summary statistics
        summary = self._calculate_summary(
            filtered_trades,
            start_date,
            end_date,
            report_type,
            account_balance_start,
            account_balance_end,
        )
        
        # Generate chart data
        charts = self._generate_chart_data(filtered_trades, start_date, end_date)
        
        # Calculate additional statistics
        additional_stats = self._calculate_additional_stats(filtered_trades)
        
        return ReportData(
            summary=summary,
            trades=filtered_trades,
            model_metrics=self._model_metrics.copy(),
            charts=charts,
            additional_stats=additional_stats,
        )
    
    def _calculate_start_date(
        self,
        report_type: ReportType,
        end_date: datetime,
    ) -> datetime:
        """Calculate start date based on report type"""
        if report_type == ReportType.DAILY:
            return end_date - timedelta(days=1)
        elif report_type == ReportType.WEEKLY:
            return end_date - timedelta(weeks=1)
        elif report_type == ReportType.MONTHLY:
            return end_date - timedelta(days=30)
        else:
            return end_date - timedelta(days=1)
    
    def _calculate_summary(
        self,
        trades: List[TradeRecord],
        start_date: datetime,
        end_date: datetime,
        report_type: ReportType,
        starting_balance: float,
        ending_balance: Optional[float],
    ) -> PerformanceSummary:
        """Calculate performance summary statistics"""
        summary = PerformanceSummary(
            start_date=start_date,
            end_date=end_date,
            report_type=report_type,
            starting_balance=starting_balance,
        )
        
        if not trades:
            summary.ending_balance = ending_balance or starting_balance
            return summary
        
        # Basic trade counts
        summary.total_trades = len(trades)
        summary.winning_trades = len([t for t in trades if t.outcome == "win"])
        summary.losing_trades = len([t for t in trades if t.outcome == "loss"])
        summary.breakeven_trades = len([t for t in trades if t.outcome == "breakeven"])
        
        # Win rate
        if summary.total_trades > 0:
            summary.win_rate = summary.winning_trades / summary.total_trades
        
        # PnL metrics
        pnls = [t.pnl for t in trades]
        summary.total_pnl = sum(pnls)
        summary.gross_profit = sum(p for p in pnls if p > 0)
        summary.gross_loss = abs(sum(p for p in pnls if p < 0))
        
        # Average win/loss
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        summary.avg_win = sum(wins) / len(wins) if wins else 0
        summary.avg_loss = abs(sum(losses) / len(losses)) if losses else 0
        
        # Profit factor
        if summary.gross_loss > 0:
            summary.profit_factor = summary.gross_profit / summary.gross_loss
        else:
            summary.profit_factor = float('inf') if summary.gross_profit > 0 else 0
        
        # Max drawdown
        summary.max_drawdown = self._calculate_max_drawdown(pnls)
        
        # Risk metrics
        summary.sharpe_ratio = self._calculate_sharpe_ratio(pnls)
        summary.sortino_ratio = self._calculate_sortino_ratio(pnls)
        
        # Duration
        durations = [t.duration for t in trades]
        summary.avg_trade_duration = sum(durations) / len(durations) if durations else 0
        
        # Model metrics
        confidences = [t.model_confidence for t in trades if t.model_confidence is not None]
        summary.avg_model_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Account balance
        summary.ending_balance = ending_balance or (starting_balance + summary.total_pnl)
        if starting_balance > 0:
            summary.return_percentage = ((summary.ending_balance - starting_balance) / starting_balance) * 100
        
        return summary
    
    def _calculate_max_drawdown(self, pnls: List[float]) -> float:
        """Calculate maximum drawdown from PnL series"""
        if not pnls:
            return 0.0
        
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        
        for pnl in pnls:
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            drawdown = peak - cumulative
            if drawdown > max_dd:
                max_dd = drawdown
        
        return max_dd
    
    def _calculate_sharpe_ratio(
        self,
        pnls: List[float],
        periods_per_year: int = 252,
    ) -> float:
        """Calculate Sharpe ratio"""
        if len(pnls) < self.min_trades_for_stats:
            return 0.0
        
        import statistics
        
        avg_return = statistics.mean(pnls)
        std_return = statistics.stdev(pnls) if len(pnls) > 1 else 0
        
        if std_return == 0:
            return 0.0
        
        # Annualize
        risk_free_per_period = self.risk_free_rate / periods_per_year
        sharpe = (avg_return - risk_free_per_period) / std_return
        
        return sharpe * (periods_per_year ** 0.5)  # Annualized
    
    def _calculate_sortino_ratio(
        self,
        pnls: List[float],
        periods_per_year: int = 252,
    ) -> float:
        """Calculate Sortino ratio (downside deviation only)"""
        if len(pnls) < self.min_trades_for_stats:
            return 0.0
        
        import statistics
        
        avg_return = statistics.mean(pnls)
        negative_returns = [r for r in pnls if r < 0]
        
        if not negative_returns:
            return float('inf') if avg_return > 0 else 0.0
        
        downside_std = statistics.stdev(negative_returns) if len(negative_returns) > 1 else abs(sum(negative_returns) / len(negative_returns))
        
        if downside_std == 0:
            return 0.0
        
        risk_free_per_period = self.risk_free_rate / periods_per_year
        sortino = (avg_return - risk_free_per_period) / downside_std
        
        return sortino * (periods_per_year ** 0.5)
    
    def _generate_chart_data(
        self,
        trades: List[TradeRecord],
        start_date: datetime,
        end_date: datetime,
    ) -> List[ChartData]:
        """Generate data for various charts"""
        charts = []
        
        if not trades:
            return charts
        
        # 1. PnL Over Time
        cumulative_pnl = 0.0
        pnl_dates = []
        pnl_values = []
        for trade in sorted(trades, key=lambda t: t.timestamp):
            cumulative_pnl += trade.pnl
            pnl_dates.append(trade.timestamp)
            pnl_values.append(cumulative_pnl)
        
        charts.append(ChartData(
            chart_type="line",
            title="Cumulative PnL Over Time",
            x_data=pnl_dates,
            y_data=pnl_values,
            x_label="Date",
            y_label="Cumulative PnL ($)",
            series_name="PnL",
        ))
        
        # 2. Win/Loss Distribution
        outcomes = defaultdict(int)
        for trade in trades:
            outcomes[trade.outcome] += 1
        
        charts.append(ChartData(
            chart_type="pie",
            title="Trade Outcome Distribution",
            x_data=list(outcomes.keys()),
            y_data=list(outcomes.values()),
            series_name="Trades",
        ))
        
        # 3. Trade Distribution by Market
        market_counts = defaultdict(int)
        for trade in trades:
            market_counts[trade.market] += 1
        
        charts.append(ChartData(
            chart_type="bar",
            title="Trades by Market",
            x_data=list(market_counts.keys()),
            y_data=list(market_counts.values()),
            x_label="Market",
            y_label="Number of Trades",
            series_name="Trades",
        ))
        
        # 4. Daily PnL
        daily_pnl = defaultdict(float)
        for trade in trades:
            date_key = trade.timestamp.date()
            daily_pnl[date_key] += trade.pnl
        
        sorted_dates = sorted(daily_pnl.keys())
        charts.append(ChartData(
            chart_type="bar",
            title="Daily PnL",
            x_data=[d.isoformat() for d in sorted_dates],
            y_data=[daily_pnl[d] for d in sorted_dates],
            x_label="Date",
            y_label="PnL ($)",
            series_name="Daily PnL",
        ))
        
        # 5. Model Confidence vs Outcome (if available)
        confidences = [(t.model_confidence, t.outcome) for t in trades if t.model_confidence is not None]
        if confidences:
            # Group by confidence ranges
            confidence_ranges = defaultdict(lambda: {"win": 0, "loss": 0, "breakeven": 0})
            for conf, outcome in confidences:
                range_key = f"{int(conf * 10) * 10}-{int(conf * 10) * 10 + 10}%"
                confidence_ranges[range_key][outcome] += 1
            
            charts.append(ChartData(
                chart_type="stacked_bar",
                title="Model Confidence vs Trade Outcome",
                x_data=list(confidence_ranges.keys()),
                y_data=[confidence_ranges[k] for k in confidence_ranges.keys()],
                x_label="Confidence Range",
                y_label="Number of Trades",
                series_name="Outcomes",
            ))
        
        return charts
    
    def _calculate_additional_stats(self, trades: List[TradeRecord]) -> Dict[str, Any]:
        """Calculate additional statistics"""
        stats = {}
        
        if not trades:
            return stats
        
        # Trade size statistics
        sizes = [t.size for t in trades]
        stats["avg_trade_size"] = sum(sizes) / len(sizes) if sizes else 0
        stats["max_trade_size"] = max(sizes) if sizes else 0
        stats["min_trade_size"] = min(sizes) if sizes else 0
        
        # Fee analysis
        fees = [t.fees for t in trades]
        stats["total_fees"] = sum(fees)
        stats["avg_fee_per_trade"] = sum(fees) / len(fees) if fees else 0
        
        # Duration analysis
        durations = [t.duration for t in trades]
        stats["avg_duration_minutes"] = (sum(durations) / len(durations) / 60) if durations else 0
        stats["max_duration_minutes"] = (max(durations) / 60) if durations else 0
        stats["min_duration_minutes"] = (min(durations) / 60) if durations else 0
        
        # Best/worst trades
        sorted_trades = sorted(trades, key=lambda t: t.pnl, reverse=True)
        stats["best_trade"] = {
            "pnl": sorted_trades[0].pnl if sorted_trades else 0,
            "market": sorted_trades[0].market if sorted_trades else "",
        }
        stats["worst_trade"] = {
            "pnl": sorted_trades[-1].pnl if sorted_trades else 0,
            "market": sorted_trades[-1].market if sorted_trades else "",
        }
        
        # Consecutive wins/losses
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_wins = 0
        current_losses = 0
        
        for trade in trades:
            if trade.outcome == "win":
                current_wins += 1
                current_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
            elif trade.outcome == "loss":
                current_losses += 1
                current_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)
        
        stats["max_consecutive_wins"] = max_consecutive_wins
        stats["max_consecutive_losses"] = max_consecutive_losses
        
        return stats
    
    def clear(self) -> None:
        """Clear all stored data"""
        self._trades.clear()
        self._model_metrics.clear()
    
    def get_trade_count(self) -> int:
        """Get number of stored trades"""
        return len(self._trades)
    
    def get_date_range(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Get date range of stored trades"""
        if not self._trades:
            return None, None
        dates = [t.timestamp for t in self._trades]
        return min(dates), max(dates)
