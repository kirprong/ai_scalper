"""
Main Dashboard for Rich Terminal UI
"""

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from datetime import datetime
import asyncio
from typing import Optional, Dict, Any

from .widgets import PnLWidget, MLStatusWidget, TradingStatsWidget, SystemStatusWidget


class Dashboard:
    """
    Main dashboard orchestrator for AI Lead Scalper terminal UI
    """
    
    def __init__(self):
        self.console = Console()
        
        # Initialize widgets
        self.pnl_widget = PnLWidget()
        self.ml_widget = MLStatusWidget()
        self.trading_widget = TradingStatsWidget()
        self.system_widget = SystemStatusWidget()
        
        # State
        self.running = False
        self.update_callback = None
    
    def set_update_callback(self, callback):
        """Set callback for fetching live data"""
        self.update_callback = callback
    
    def update_data(self, data: Dict[str, Any]):
        """
        Update all widgets with new data
        
        Expected data structure:
        {
            'pnl': {
                'realized': float,
                'unrealized': float,
                'trades': int,
                'win_rate': float
            },
            'ml': {
                'lstm_status': str,
                'xgb_status': str,
                'lstm_confidence': float,
                'xgb_confidence': float,
                'accuracy': float,
                'last_prediction': datetime
            },
            'trading': {
                'volume': float,
                'avg_size': float,
                'drawdown': float,
                'sharpe': float,
                'positions': int,
                'orders': int
            },
            'system': {
                'status': str,
                'uptime': int,
                'cpu': float,
                'memory': float,
                'latency': float,
                'errors': int,
                'last_error': str
            }
        }
        """
        if 'pnl' in data:
            self.pnl_widget.update(**data['pnl'])
        
        if 'ml' in data:
            self.ml_widget.update(**data['ml'])
        
        if 'trading' in data:
            self.trading_widget.update(**data['trading'])
        
        if 'system' in data:
            self.system_widget.update(**data['system'])
    
    def render_header(self) -> Panel:
        """Render header panel"""
        title = Text()
        title.append("🚀 AI LEAD SCALPER ", style="bold cyan")
        title.append("v1.0", style="dim cyan")
        
        subtitle = Text()
        subtitle.append(f"Terminal Dashboard | ", style="dim")
        subtitle.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), style="bold white")
        
        content = Text()
        content.append(title)
        content.append("\n")
        content.append(subtitle)
        
        return Panel(
            content,
            style="bold cyan",
            padding=(1, 2)
        )
    
    def render_layout(self) -> Layout:
        """Render complete dashboard layout"""
        layout = Layout()
        
        # Split into header and body
        layout.split(
            Layout(name="header", size=4),
            Layout(name="body", ratio=1)
        )
        
        # Split body into left and right columns
        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1)
        )
        
        # Split each column into rows
        layout["left"].split(
            Layout(name="pnl", ratio=1),
            Layout(name="ml", ratio=1)
        )
        
        layout["right"].split(
            Layout(name="trading", ratio=1),
            Layout(name="system", ratio=1)
        )
        
        # Populate widgets
        layout["header"].update(self.render_header())
        layout["pnl"].update(self.pnl_widget.render())
        layout["ml"].update(self.ml_widget.render())
        layout["trading"].update(self.trading_widget.render())
        layout["system"].update(self.system_widget.render())
        
        return layout
    
    async def run_async(self, refresh_rate: float = 1.0):
        """
        Run dashboard with live updates (async version)
        
        Args:
            refresh_rate: How often to refresh (seconds)
        """
        self.running = True
        
        with Live(
            self.render_layout(),
            console=self.console,
            refresh_per_second=1/refresh_rate,
            screen=True
        ) as live:
            while self.running:
                # Fetch new data if callback is set
                if self.update_callback:
                    try:
                        data = await self.update_callback()
                        self.update_data(data)
                    except Exception as e:
                        self.console.print(f"[red]Error fetching data: {e}[/red]")
                
                # Update display
                live.update(self.render_layout())
                
                # Wait for next update
                await asyncio.sleep(refresh_rate)
    
    def run(self, refresh_rate: float = 1.0):
        """
        Run dashboard with live updates (sync version)
        
        Args:
            refresh_rate: How often to refresh (seconds)
        """
        asyncio.run(self.run_async(refresh_rate))
    
    def stop(self):
        """Stop the dashboard"""
        self.running = False
    
    def render_static(self):
        """Render a single static frame (for testing)"""
        self.console.clear()
        self.console.print(self.render_layout())
