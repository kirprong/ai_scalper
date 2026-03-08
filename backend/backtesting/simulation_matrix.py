"""
Simulation Matrix - Research on slippage levels
"""
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class SimulationConfig:
    """Simulation configuration"""
    spread_levels: List[float] = field(default_factory=lambda: [0.01, 0.02, 0.03])
    latency_ms: int = 200
    fee_rate: float = 0.001  # 0.1%


@dataclass
class SimulationResult:
    """Single simulation result"""
    spread_level: float
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    avg_pnl_per_trade: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0


class SimulationMatrix:
    """
    Simulation Matrix - runs strategy through different spread levels
    """
    
    def __init__(
        self,
        config: SimulationConfig,
        strategy_fn: Callable,
        data_loader_fn: Callable,
    ):
        """
        Initialize simulation matrix
        
        Args:
            config: Simulation configuration
            strategy_fn: Async function to run strategy (data, spread) -> trades
            data_loader_fn: Function to load data (start, end) -> data
        """
        self.config = config
        self.strategy_fn = strategy_fn
        self.data_loader_fn = data_loader_fn
        self.results: Dict[float, SimulationResult] = {}
        
    async def run_simulation(
        self,
        spread_level: float,
        data: List[Any],
    ) -> SimulationResult:
        """
        Run single simulation with specific spread level
        
        Args:
            spread_level: Spread level to simulate
            data: Market data
            
        Returns:
            Simulation result
        """
        logger.info(f"Running simulation with spread {spread_level:.2%}")
        
        # Run strategy
        trades = await self.strategy_fn(data, spread_level)
        
        if not trades:
            logger.warning(f"No trades generated for spread {spread_level:.2%}")
            return SimulationResult(spread_level=spread_level)
        
        # Calculate metrics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in trades if t.get("pnl", 0) < 0]
        
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        avg_win = (
            sum(t.get("pnl", 0) for t in winning_trades) / len(winning_trades)
            if winning_trades else 0
        )
        
        avg_loss = (
            sum(t.get("pnl", 0) for t in losing_trades) / len(losing_trades)
            if losing_trades else 0
        )
        
        # Profit factor
        gross_profit = sum(t.get("pnl", 0) for t in winning_trades)
        gross_loss = abs(sum(t.get("pnl", 0) for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Max drawdown
        cumulative_pnl = 0
        max_pnl = 0
        max_drawdown = 0
        
        for trade in trades:
            cumulative_pnl += trade.get("pnl", 0)
            max_pnl = max(max_pnl, cumulative_pnl)
            drawdown = max_pnl - cumulative_pnl
            max_drawdown = max(max_drawdown, drawdown)
        
        # Sharpe ratio (simplified)
        returns = [t.get("pnl", 0) for t in trades]
        avg_return = sum(returns) / len(returns) if returns else 0
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns) if returns else 0
        std_dev = variance ** 0.5
        sharpe_ratio = avg_return / std_dev if std_dev > 0 else 0
        
        result = SimulationResult(
            spread_level=spread_level,
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            total_pnl=total_pnl,
            avg_pnl_per_trade=avg_pnl,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
        )
        
        logger.info(
            f"Spread {spread_level:.2%}: "
            f"{total_trades} trades, "
            f"PnL ${total_pnl:.2f}, "
            f"Win rate {win_rate:.2%}"
        )
        
        return result
    
    async def run_all(
        self,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Run all simulations
        
        Args:
            start_date: Start date for data
            end_date: End date for data
            
        Returns:
            Summary with all results
        """
        logger.info(f"Running simulation matrix with {len(self.config.spread_levels)} spread levels")
        
        # Load data
        data = await self.data_loader_fn(start_date, end_date)
        
        if not data:
            logger.warning("No data loaded")
            return {"error": "No data loaded"}
        
        logger.info(f"Loaded {len(data)} data points")
        
        # Run simulation for each spread level
        for spread in self.config.spread_levels:
            result = await self.run_simulation(spread, data)
            self.results[spread] = result
        
        # Generate summary
        summary = {
            "spread_levels": self.config.spread_levels,
            "results": {
                spread: {
                    "total_trades": r.total_trades,
                    "winning_trades": r.winning_trades,
                    "losing_trades": r.losing_trades,
                    "total_pnl": r.total_pnl,
                    "avg_pnl_per_trade": r.avg_pnl_per_trade,
                    "win_rate": r.win_rate,
                    "profit_factor": r.profit_factor,
                    "max_drawdown": r.max_drawdown,
                    "sharpe_ratio": r.sharpe_ratio,
                }
                for spread, r in self.results.items()
            },
            "best_spread": max(
                self.results.items(),
                key=lambda x: x[1].total_pnl
            )[0] if self.results else None,
        }
        
        logger.info("Simulation matrix completed:")
        logger.info(f"  Best spread: {summary['best_spread']:.2%}")
        
        return summary
    
    def get_result(self, spread_level: float) -> Optional[SimulationResult]:
        """Get result for specific spread level"""
        return self.results.get(spread_level)
    
    def get_all_results(self) -> Dict[float, SimulationResult]:
        """Get all results"""
        return self.results
    
    def print_summary(self):
        """Print summary table"""
        print("\n" + "=" * 80)
        print("SIMULATION MATRIX RESULTS")
        print("=" * 80)
        print(f"{'Spread':<10} {'Trades':<10} {'Win Rate':<12} {'Total PnL':<15} {'Profit Factor':<15}")
        print("-" * 80)
        
        for spread, result in sorted(self.results.items()):
            print(
                f"{spread:.2%}     "
                f"{result.total_trades:<10} "
                f"{result.win_rate:.2%}       "
                f"${result.total_pnl:>10.2f}   "
                f"{result.profit_factor:>10.2f}"
            )
        
        print("=" * 80)
