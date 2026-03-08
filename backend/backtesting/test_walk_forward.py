"""
Tests for Walk-Forward Optimization Engine
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from backend.backtesting.walk_forward import (
    WalkForwardOptimizer,
    WFOConfig,
    WFOPeriod,
)


@pytest.fixture
def config():
    """Create WFO config"""
    return WFOConfig(
        train_days=5,
        test_days=1,
        step_days=1,
        min_train_samples=100,
        retrain_threshold=0.75,
    )


@pytest.fixture
def mock_train_fn():
    """Mock training function"""
    async def train(data):
        # Simulate training
        await asyncio.sleep(0.01)
        return 0.85  # 85% accuracy
    return train


@pytest.fixture
def mock_test_fn():
    """Mock test function"""
    async def test(data):
        # Simulate testing
        await asyncio.sleep(0.01)
        return 0.80, 100.0  # 80% accuracy, $100 PnL
    return test


@pytest.fixture
def mock_data_loader():
    """Mock data loader"""
    async def load(start, end):
        # Simulate data loading
        await asyncio.sleep(0.01)
        # Return mock data (list of samples)
        days = (end - start).days
        return list(range(days * 100))  # 100 samples per day
    return load


class TestWFOConfig:
    """Tests for WFOConfig"""
    
    def test_default_config(self):
        """Test default configuration"""
        config = WFOConfig()
        assert config.train_days == 5
        assert config.test_days == 1
        assert config.step_days == 1
        assert config.min_train_samples == 1000
        assert config.retrain_threshold == 0.75


class TestWFOPeriod:
    """Tests for WFOPeriod"""
    
    def test_period_creation(self):
        """Test period creation"""
        now = datetime.now()
        period = WFOPeriod(
            period_id=0,
            train_start=now,
            train_end=now + timedelta(days=5),
            test_start=now + timedelta(days=5),
            test_end=now + timedelta(days=6),
        )
        
        assert period.period_id == 0
        assert period.status == "pending"
        assert period.train_samples == 0
        assert period.test_samples == 0


class TestWalkForwardOptimizer:
    """Tests for WalkForwardOptimizer"""
    
    def test_generate_periods(self, config, mock_train_fn, mock_test_fn, mock_data_loader):
        """Test period generation"""
        optimizer = WalkForwardOptimizer(
            config=config,
            train_fn=mock_train_fn,
            test_fn=mock_test_fn,
            data_loader_fn=mock_data_loader,
        )
        
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 15)  # 15 days
        
        periods = optimizer.generate_periods(start, end)
        
        # Should generate multiple periods
        assert len(periods) > 0
        
        # Check first period
        first = periods[0]
        assert first.period_id == 0
        assert first.train_start == start
        assert first.train_end == start + timedelta(days=5)
        assert first.test_start == start + timedelta(days=5)
        assert first.test_end == start + timedelta(days=6)
        
        # Check periods don't overlap incorrectly
        for i in range(len(periods) - 1):
            current = periods[i]
            next_period = periods[i + 1]
            
            # Test period should end before or at next test start
            assert current.test_end <= next_period.test_end
    
    @pytest.mark.asyncio
    async def test_run_period(self, config, mock_train_fn, mock_test_fn, mock_data_loader):
        """Test running single period"""
        optimizer = WalkForwardOptimizer(
            config=config,
            train_fn=mock_train_fn,
            test_fn=mock_test_fn,
            data_loader_fn=mock_data_loader,
        )
        
        start = datetime(2024, 1, 1)
        period = WFOPeriod(
            period_id=0,
            train_start=start,
            train_end=start + timedelta(days=5),
            test_start=start + timedelta(days=5),
            test_end=start + timedelta(days=6),
        )
        
        result = await optimizer.run_period(period)
        
        assert result.status == "completed"
        assert result.train_samples == 500  # 5 days * 100 samples
        assert result.test_samples == 100  # 1 day * 100 samples
        assert result.train_accuracy == 0.85
        assert result.test_accuracy == 0.80
        assert result.test_pnl == 100.0
    
    @pytest.mark.asyncio
    async def test_run_all(self, config, mock_train_fn, mock_test_fn, mock_data_loader):
        """Test running all periods"""
        optimizer = WalkForwardOptimizer(
            config=config,
            train_fn=mock_train_fn,
            test_fn=mock_test_fn,
            data_loader_fn=mock_data_loader,
        )
        
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 10)
        
        summary = await optimizer.run_all(start, end)
        
        assert "total_periods" in summary
        assert "completed_periods" in summary
        assert "avg_train_accuracy" in summary
        assert "avg_test_accuracy" in summary
        assert "total_pnl" in summary
        assert summary["completed_periods"] > 0
    
    def test_should_retrain(self, config, mock_train_fn, mock_test_fn, mock_data_loader):
        """Test retrain decision"""
        optimizer = WalkForwardOptimizer(
            config=config,
            train_fn=mock_train_fn,
            test_fn=mock_test_fn,
            data_loader_fn=mock_data_loader,
        )
        
        # Should retrain if accuracy < threshold
        assert optimizer.should_retrain(0.70) is True
        assert optimizer.should_retrain(0.75) is False
        assert optimizer.should_retrain(0.80) is False
    
    def test_get_progress(self, config, mock_train_fn, mock_test_fn, mock_data_loader):
        """Test progress tracking"""
        optimizer = WalkForwardOptimizer(
            config=config,
            train_fn=mock_train_fn,
            test_fn=mock_test_fn,
            data_loader_fn=mock_data_loader,
        )
        
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 10)
        
        optimizer.generate_periods(start, end)
        progress = optimizer.get_progress()
        
        assert "total_periods" in progress
        assert "completed" in progress
        assert "failed" in progress
        assert "is_running" in progress


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
