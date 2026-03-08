"""
Tests for Simulation Matrix
"""
import pytest
import asyncio
from backend.backtesting.simulation_matrix import (
    SimulationMatrix,
    SimulationConfig,
    SimulationResult,
)


@pytest.fixture
def config():
    """Create simulation config"""
    return SimulationConfig(
        spread_levels=[0.01, 0.02, 0.03],
        latency_ms=200,
        fee_rate=0.001,
    )


@pytest.fixture
def mock_strategy():
    """Mock strategy function"""
    async def strategy(data, spread):
        # Simulate trades with different PnL based on spread
        trades = []
        for i in range(10):
            # Higher spread = lower PnL
            pnl = 100.0 - (spread * 1000) + (i * 10)
            trades.append({"pnl": pnl})
        return trades
    return strategy


@pytest.fixture
def mock_data_loader():
    """Mock data loader"""
    async def load(start, end):
        # Return mock data
        return list(range(100))
    return load


class TestSimulationConfig:
    """Tests for SimulationConfig"""
    
    def test_default_config(self):
        """Test default configuration"""
        config = SimulationConfig()
        assert config.spread_levels == [0.01, 0.02, 0.03]
        assert config.latency_ms == 200
        assert config.fee_rate == 0.001


class TestSimulationResult:
    """Tests for SimulationResult"""
    
    def test_result_creation(self):
        """Test result creation"""
        result = SimulationResult(spread_level=0.01)
        assert result.spread_level == 0.01
        assert result.total_trades == 0
        assert result.total_pnl == 0.0


class TestSimulationMatrix:
    """Tests for SimulationMatrix"""
    
    @pytest.mark.asyncio
    async def test_run_simulation(self, config, mock_strategy, mock_data_loader):
        """Test running single simulation"""
        matrix = SimulationMatrix(
            config=config,
            strategy_fn=mock_strategy,
            data_loader_fn=mock_data_loader,
        )
        
        data = list(range(100))
        result = await matrix.run_simulation(0.01, data)
        
        assert result.spread_level == 0.01
        assert result.total_trades == 10
        assert result.winning_trades > 0
        assert result.total_pnl > 0
        assert result.win_rate > 0
    
    @pytest.mark.asyncio
    async def test_run_all(self, config, mock_strategy, mock_data_loader):
        """Test running all simulations"""
        matrix = SimulationMatrix(
            config=config,
            strategy_fn=mock_strategy,
            data_loader_fn=mock_data_loader,
        )
        
        summary = await matrix.run_all()
        
        assert "spread_levels" in summary
        assert "results" in summary
        assert "best_spread" in summary
        assert len(summary["results"]) == 3  # 3 spread levels
    
    def test_get_result(self, config, mock_strategy, mock_data_loader):
        """Test getting result"""
        matrix = SimulationMatrix(
            config=config,
            strategy_fn=mock_strategy,
            data_loader_fn=mock_data_loader,
        )
        
        # Add mock result
        matrix.results[0.01] = SimulationResult(spread_level=0.01, total_trades=10)
        
        result = matrix.get_result(0.01)
        assert result is not None
        assert result.total_trades == 10
        
        # Non-existent spread
        result = matrix.get_result(0.05)
        assert result is None
    
    def test_get_all_results(self, config, mock_strategy, mock_data_loader):
        """Test getting all results"""
        matrix = SimulationMatrix(
            config=config,
            strategy_fn=mock_strategy,
            data_loader_fn=mock_data_loader,
        )
        
        # Add mock results
        matrix.results[0.01] = SimulationResult(spread_level=0.01)
        matrix.results[0.02] = SimulationResult(spread_level=0.02)
        
        results = matrix.get_all_results()
        assert len(results) == 2
        assert 0.01 in results
        assert 0.02 in results


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
