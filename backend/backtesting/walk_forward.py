"""
Walk-Forward Optimization Engine
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class WFOConfig:
    """Walk-Forward Optimization configuration"""
    train_days: int = 5
    test_days: int = 1
    step_days: int = 1
    min_train_samples: int = 1000
    retrain_threshold: float = 0.75  # Retrain if accuracy < 75%


@dataclass
class WFOPeriod:
    """Single walk-forward period"""
    period_id: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_samples: int = 0
    test_samples: int = 0
    train_accuracy: float = 0.0
    test_accuracy: float = 0.0
    test_pnl: float = 0.0
    status: str = "pending"  # pending, training, testing, completed, failed


class WalkForwardOptimizer:
    """
    Walk-Forward Optimization Engine
    
    Prevents overfitting by training on one period and testing on the next.
    """
    
    def __init__(
        self,
        config: WFOConfig,
        train_fn: Callable,
        test_fn: Callable,
        data_loader_fn: Callable,
    ):
        """
        Initialize WFO engine
        
        Args:
            config: WFO configuration
            train_fn: Async function to train model (train_data) -> accuracy
            test_fn: Async function to test model (test_data) -> (accuracy, pnl)
            data_loader_fn: Function to load data (start, end) -> data
        """
        self.config = config
        self.train_fn = train_fn
        self.test_fn = test_fn
        self.data_loader_fn = data_loader_fn
        self.periods: List[WFOPeriod] = []
        self.current_period: Optional[WFOPeriod] = None
        self.is_running = False
        
    def generate_periods(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> List[WFOPeriod]:
        """
        Generate walk-forward periods
        
        Args:
            start_date: Start date for optimization
            end_date: End date for optimization
            
        Returns:
            List of WFOPeriod objects
        """
        periods = []
        period_id = 0
        
        current_start = start_date
        
        while True:
            # Training period
            train_start = current_start
            train_end = train_start + timedelta(days=self.config.train_days)
            
            # Test period (immediately after training)
            test_start = train_end
            test_end = test_start + timedelta(days=self.config.test_days)
            
            # Check if we have enough data for test period
            if test_end > end_date:
                break
                
            period = WFOPeriod(
                period_id=period_id,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )
            
            periods.append(period)
            period_id += 1
            
            # Move to next period
            current_start += timedelta(days=self.config.step_days)
            
        self.periods = periods
        logger.info(f"Generated {len(periods)} walk-forward periods")
        return periods
    
    async def run_period(self, period: WFOPeriod) -> WFOPeriod:
        """
        Run single walk-forward period
        
        Args:
            period: Period to run
            
        Returns:
            Updated period with results
        """
        logger.info(f"Running period {period.period_id}")
        
        try:
            # Load training data
            period.status = "training"
            logger.info(f"Loading training data: {period.train_start} to {period.train_end}")
            
            train_data = await self.data_loader_fn(period.train_start, period.train_end)
            period.train_samples = len(train_data) if train_data else 0
            
            if period.train_samples < self.config.min_train_samples:
                raise ValueError(
                    f"Insufficient training samples: {period.train_samples} < {self.config.min_train_samples}"
                )
            
            # Train model
            logger.info(f"Training on {period.train_samples} samples...")
            train_accuracy = await self.train_fn(train_data)
            period.train_accuracy = train_accuracy
            
            logger.info(f"Training accuracy: {train_accuracy:.2%}")
            
            # Load test data
            period.status = "testing"
            logger.info(f"Loading test data: {period.test_start} to {period.test_end}")
            
            test_data = await self.data_loader_fn(period.test_start, period.test_end)
            period.test_samples = len(test_data) if test_data else 0
            
            # Test model
            logger.info(f"Testing on {period.test_samples} samples...")
            test_accuracy, test_pnl = await self.test_fn(test_data)
            period.test_accuracy = test_accuracy
            period.test_pnl = test_pnl
            
            logger.info(f"Test accuracy: {test_accuracy:.2%}, PnL: {test_pnl:.2f}")
            
            period.status = "completed"
            
        except Exception as e:
            logger.error(f"Period {period.period_id} failed: {e}")
            period.status = "failed"
            
        return period
    
    async def run_all(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """
        Run all walk-forward periods
        
        Args:
            start_date: Start date for optimization
            end_date: End date for optimization
            
        Returns:
            Summary statistics
        """
        self.is_running = True
        
        # Generate periods
        periods = self.generate_periods(start_date, end_date)
        
        if not periods:
            logger.warning("No periods generated")
            return {"error": "No periods generated"}
        
        # Run each period
        for period in periods:
            self.current_period = period
            await self.run_period(period)
            
        self.is_running = False
        
        # Calculate summary statistics
        completed_periods = [p for p in self.periods if p.status == "completed"]
        
        if not completed_periods:
            return {"error": "No completed periods"}
        
        summary = {
            "total_periods": len(self.periods),
            "completed_periods": len(completed_periods),
            "failed_periods": len([p for p in self.periods if p.status == "failed"]),
            "avg_train_accuracy": sum(p.train_accuracy for p in completed_periods) / len(completed_periods),
            "avg_test_accuracy": sum(p.test_accuracy for p in completed_periods) / len(completed_periods),
            "total_pnl": sum(p.test_pnl for p in completed_periods),
            "avg_pnl_per_period": sum(p.test_pnl for p in completed_periods) / len(completed_periods),
            "periods": [
                {
                    "period_id": p.period_id,
                    "train_accuracy": p.train_accuracy,
                    "test_accuracy": p.test_accuracy,
                    "test_pnl": p.test_pnl,
                    "status": p.status,
                }
                for p in self.periods
            ],
        }
        
        logger.info(f"Walk-Forward Optimization completed:")
        logger.info(f"  Periods: {summary['completed_periods']}/{summary['total_periods']}")
        logger.info(f"  Avg Train Accuracy: {summary['avg_train_accuracy']:.2%}")
        logger.info(f"  Avg Test Accuracy: {summary['avg_test_accuracy']:.2%}")
        logger.info(f"  Total PnL: {summary['total_pnl']:.2f}")
        
        return summary
    
    def should_retrain(self, test_accuracy: float) -> bool:
        """
        Check if model should be retrained
        
        Args:
            test_accuracy: Test accuracy from last period
            
        Returns:
            True if should retrain
        """
        return test_accuracy < self.config.retrain_threshold
    
    def get_current_period(self) -> Optional[WFOPeriod]:
        """Get current running period"""
        return self.current_period
    
    def get_progress(self) -> Dict[str, Any]:
        """Get optimization progress"""
        completed = len([p for p in self.periods if p.status == "completed"])
        failed = len([p for p in self.periods if p.status == "failed"])
        
        return {
            "total_periods": len(self.periods),
            "completed": completed,
            "failed": failed,
            "current_period": self.current_period.period_id if self.current_period else None,
            "is_running": self.is_running,
        }
