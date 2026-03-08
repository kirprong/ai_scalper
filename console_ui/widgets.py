"""
Reusable UI Widgets for Rich Terminal Dashboard
"""

from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text
from rich.layout import Layout
from datetime import datetime
from typing import Optional, Dict, Any


class PnLWidget:
    """Widget for displaying PnL information"""
    
    def __init__(self):
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        self.total_trades = 0
        self.win_rate = 0.0
    
    def update(self, realized: float, unrealized: float, trades: int, win_rate: float):
        """Update PnL data"""
        self.realized_pnl = realized
        self.unrealized_pnl = unrealized
        self.win_rate = win_rate
        self.total_trades = trades
    
    def render(self) -> Panel:
        """Render PnL panel"""
        total_pnl = self.realized_pnl + self.unrealized_pnl
        
        # Color based on PnL
        pnl_color = "green" if total_pnl >= 0 else "red"
        
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style=pnl_color, justify="right")
        
        table.add_row("Realized PnL", f"${self.realized_pnl:+.2f}")
        table.add_row("Unrealized PnL", f"${self.unrealized_pnl:+.2f}")
        table.add_row("Total PnL", f"${total_pnl:+.2f}")
        table.add_row("Total Trades", str(self.total_trades))
        table.add_row("Win Rate", f"{self.win_rate:.1%}")
        
        return Panel(
            table,
            title="[bold yellow]💰 PnL Dashboard[/bold yellow]",
            border_style="yellow",
            padding=(1, 2)
        )


class MLStatusWidget:
    """Widget for displaying ML model status"""
    
    def __init__(self):
        self.lstm_status = "IDLE"
        self.xgb_status = "IDLE"
        self.lstm_confidence = 0.0
        self.xgb_confidence = 0.0
        self.last_prediction = None
        self.model_accuracy = 0.0
    
    def update(self, lstm_status: str, xgb_status: str, 
               lstm_conf: float, xgb_conf: float,
               accuracy: float, last_pred: Optional[datetime] = None):
        """Update ML status"""
        self.lstm_status = lstm_status
        self.xgb_status = xgb_status
        self.lstm_confidence = lstm_conf
        self.xgb_confidence = xgb_conf
        self.model_accuracy = accuracy
        self.last_prediction = last_pred
    
    def render(self) -> Panel:
        """Render ML status panel"""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Model", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Confidence", justify="right")
        
        # LSTM row
        lstm_color = "green" if self.lstm_status == "ACTIVE" else "yellow"
        table.add_row(
            "LSTM",
            f"[{lstm_color}]{self.lstm_status}[/{lstm_color}]",
            f"{self.lstm_confidence:.2%}"
        )
        
        # XGBoost row
        xgb_color = "green" if self.xgb_status == "ACTIVE" else "yellow"
        table.add_row(
            "XGBoost",
            f"[{xgb_color}]{self.xgb_status}[/{xgb_color}]",
            f"{self.xgb_confidence:.2%}"
        )
        
        table.add_row("", "", "")
        table.add_row("Model Accuracy", f"[bold]{self.model_accuracy:.1%}[/bold]", "")
        
        if self.last_prediction:
            elapsed = (datetime.now() - self.last_prediction).total_seconds()
            table.add_row("Last Prediction", f"{elapsed:.1f}s ago", "")
        
        return Panel(
            table,
            title="[bold blue]🤖 ML Status[/bold blue]",
            border_style="blue",
            padding=(1, 2)
        )


class TradingStatsWidget:
    """Widget for displaying trading statistics"""
    
    def __init__(self):
        self.total_volume = 0.0
        self.avg_trade_size = 0.0
        self.max_drawdown = 0.0
        self.sharpe_ratio = 0.0
        self.active_positions = 0
        self.pending_orders = 0
    
    def update(self, volume: float, avg_size: float, drawdown: float,
               sharpe: float, positions: int, orders: int):
        """Update trading stats"""
        self.total_volume = volume
        self.avg_trade_size = avg_size
        self.max_drawdown = drawdown
        self.sharpe_ratio = sharpe
        self.active_positions = positions
        self.pending_orders = orders
    
    def render(self) -> Panel:
        """Render trading stats panel"""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")
        
        table.add_row("Total Volume", f"${self.total_volume:,.2f}")
        table.add_row("Avg Trade Size", f"${self.avg_trade_size:.2f}")
        
        # Color drawdown
        dd_color = "red" if self.max_drawdown > 0.05 else "green"
        table.add_row("Max Drawdown", f"[{dd_color}]{self.max_drawdown:.2%}[/{dd_color}]")
        
        # Color Sharpe
        sharpe_color = "green" if self.sharpe_ratio > 1.0 else "yellow"
        table.add_row("Sharpe Ratio", f"[{sharpe_color}]{self.sharpe_ratio:.2f}[/{sharpe_color}]")
        
        table.add_row("", "")
        table.add_row("Active Positions", f"[bold]{self.active_positions}[/bold]")
        table.add_row("Pending Orders", f"[bold]{self.pending_orders}[/bold]")
        
        return Panel(
            table,
            title="[bold magenta]📊 Trading Stats[/bold magenta]",
            border_style="magenta",
            padding=(1, 2)
        )


class SystemStatusWidget:
    """Widget for displaying system status"""
    
    def __init__(self):
        self.status = "INITIALIZING"
        self.uptime = 0
        self.cpu_usage = 0.0
        self.memory_usage = 0.0
        self.latency = 0.0
        self.errors_count = 0
        self.last_error = None
    
    def update(self, status: str, uptime: int, cpu: float, memory: float,
               latency: float, errors: int, last_error: Optional[str] = None):
        """Update system status"""
        self.status = status
        self.uptime = uptime
        self.cpu_usage = cpu
        self.memory_usage = memory
        self.latency = latency
        self.errors_count = errors
        self.last_error = last_error
    
    def render(self) -> Panel:
        """Render system status panel"""
        # Status color
        status_colors = {
            "RUNNING": "green",
            "HALTED": "red",
            "PAPER_TRADING": "yellow",
            "INITIALIZING": "blue"
        }
        status_color = status_colors.get(self.status, "white")
        
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")
        
        table.add_row("Status", f"[bold {status_color}]{self.status}[/bold {status_color}]")
        
        # Format uptime
        hours = self.uptime // 3600
        minutes = (self.uptime % 3600) // 60
        seconds = self.uptime % 60
        table.add_row("Uptime", f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
        # Resource usage with color coding
        cpu_color = "red" if self.cpu_usage > 80 else "green"
        mem_color = "red" if self.memory_usage > 80 else "green"
        
        table.add_row("CPU Usage", f"[{cpu_color}]{self.cpu_usage:.1f}%[/{cpu_color}]")
        table.add_row("Memory Usage", f"[{mem_color}]{self.memory_usage:.1f}%[/{mem_color}]")
        
        # Latency color
        lat_color = "green" if self.latency < 20 else "yellow" if self.latency < 50 else "red"
        table.add_row("Latency", f"[{lat_color}]{self.latency:.1f}ms[/{lat_color}]")
        
        # Errors
        err_color = "red" if self.errors_count > 0 else "green"
        table.add_row("Errors", f"[{err_color}]{self.errors_count}[/{err_color}]")
        
        if self.last_error:
            table.add_row("Last Error", f"[red]{self.last_error[:30]}[/red]")
        
        return Panel(
            table,
            title="[bold cyan]⚙️ System Status[/bold cyan]",
            border_style="cyan",
            padding=(1, 2)
        )
