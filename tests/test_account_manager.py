"""
Tests for Multi-Account Support

This module tests:
- Account configuration loading and validation
- Account registry operations
- Account manager initialization and rotation
- Failover scenarios
"""

import os
import json
import pytest
import asyncio
import tempfile
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from dataclasses import asdict

from backend.config.accounts import (
    AccountConfig,
    AccountRegistry,
    AccountStatus,
    load_accounts_from_env,
    load_accounts_from_file,
    load_accounts_from_vault,
)
from backend.trading.account_manager import (
    AccountManager,
    AccountState,
    RotationStrategy,
    FailoverResult,
)


# ==================== Test Fixtures ====================

@pytest.fixture
def sample_account_config():
    """Create a sample account configuration."""
    return AccountConfig(
        name="test_account",
        api_key="test_api_key_12345",
        api_secret="test_api_secret_12345",
        wallet_address="0x1234567890123456789012345678901234567890",
        private_key="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        priority=1,
        weight=1.0,
        chain_id=137,
    )


@pytest.fixture
def sample_account_config_2():
    """Create a second sample account configuration."""
    return AccountConfig(
        name="test_account_2",
        api_key="test_api_key_67890",
        api_secret="test_api_secret_67890",
        wallet_address="0x0987654321098765432109876543210987654321",
        private_key="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        priority=2,
        weight=2.0,
        chain_id=137,
    )


@pytest.fixture
def account_registry(sample_account_config, sample_account_config_2):
    """Create an account registry with sample accounts."""
    registry = AccountRegistry()
    registry.add_account(sample_account_config)
    registry.add_account(sample_account_config_2)
    return registry


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    config_data = {
        "accounts": [
            {
                "name": "file_account_1",
                "api_key": "file_key_1",
                "api_secret": "file_secret_1",
                "wallet_address": "0x1111111111111111111111111111111111111111",
                "priority": 1,
                "weight": 1.0,
            },
            {
                "name": "file_account_2",
                "api_key": "file_key_2",
                "api_secret": "file_secret_2",
                "wallet_address": "0x2222222222222222222222222222222222222222",
                "priority": 2,
                "weight": 2.0,
            },
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        yield f.name
    
    os.unlink(f.name)


# ==================== AccountConfig Tests ====================

class TestAccountConfig:
    """Tests for AccountConfig class."""
    
    def test_create_account_config(self, sample_account_config):
        """Test creating an account configuration."""
        assert sample_account_config.name == "test_account"
        assert sample_account_config.api_key == "test_api_key_12345"
        assert sample_account_config.wallet_address.startswith("0x")
        assert sample_account_config.priority == 1
        assert sample_account_config.weight == 1.0
        assert sample_account_config.status == AccountStatus.ACTIVE
    
    def test_account_config_validation_missing_name(self):
        """Test validation fails with missing name."""
        with pytest.raises(ValueError, match="Account name is required"):
            AccountConfig(
                name="",
                api_key="key",
                api_secret="secret",
                wallet_address="0x1234567890123456789012345678901234567890",
            )
    
    def test_account_config_validation_missing_api_key(self):
        """Test validation fails with missing API key."""
        with pytest.raises(ValueError, match="API key is required"):
            AccountConfig(
                name="test",
                api_key="",
                api_secret="secret",
                wallet_address="0x1234567890123456789012345678901234567890",
            )
    
    def test_account_config_validation_invalid_wallet(self):
        """Test validation fails with invalid wallet address."""
        with pytest.raises(ValueError, match="Invalid wallet address format"):
            AccountConfig(
                name="test",
                api_key="key",
                api_secret="secret",
                wallet_address="invalid_address",
            )
    
    def test_account_config_validation_negative_weight(self):
        """Test validation fails with negative weight."""
        with pytest.raises(ValueError, match="Weight must be positive"):
            AccountConfig(
                name="test",
                api_key="key",
                api_secret="secret",
                wallet_address="0x1234567890123456789012345678901234567890",
                weight=-1.0,
            )
    
    def test_is_active(self, sample_account_config):
        """Test is_active method."""
        # Not active without private key
        sample_account_config.private_key = None
        assert not sample_account_config.is_active()
        
        # Active with private key
        sample_account_config.private_key = "test_key"
        assert sample_account_config.is_active()
        
        # Not active if status is not ACTIVE
        sample_account_config.status = AccountStatus.DISABLED
        assert not sample_account_config.is_active()
    
    def test_to_dict(self, sample_account_config):
        """Test to_dict method masks sensitive data."""
        d = sample_account_config.to_dict()
        
        assert d["name"] == "test_account"
        assert "..." in d["api_key"]  # Masked
        assert "private_key" not in d
        assert d["wallet_address"] == sample_account_config.wallet_address


# ==================== AccountRegistry Tests ====================

class TestAccountRegistry:
    """Tests for AccountRegistry class."""
    
    def test_add_account(self, sample_account_config):
        """Test adding an account to the registry."""
        registry = AccountRegistry()
        registry.add_account(sample_account_config)
        
        assert len(registry) == 1
        assert "test_account" in registry
    
    def test_add_duplicate_account(self, sample_account_config):
        """Test adding duplicate account raises error."""
        registry = AccountRegistry()
        registry.add_account(sample_account_config)
        
        with pytest.raises(ValueError, match="already exists"):
            registry.add_account(sample_account_config)
    
    def test_remove_account(self, account_registry):
        """Test removing an account."""
        removed = account_registry.remove_account("test_account")
        
        assert removed is not None
        assert removed.name == "test_account"
        assert len(account_registry) == 1
    
    def test_remove_nonexistent_account(self, account_registry):
        """Test removing nonexistent account returns None."""
        removed = account_registry.remove_account("nonexistent")
        assert removed is None
    
    def test_get_account(self, account_registry):
        """Test getting an account by name."""
        account = account_registry.get_account("test_account")
        
        assert account is not None
        assert account.name == "test_account"
    
    def test_get_all_accounts(self, account_registry):
        """Test getting all accounts."""
        accounts = account_registry.get_all_accounts()
        
        assert len(accounts) == 2
        assert accounts[0].name == "test_account"
        assert accounts[1].name == "test_account_2"
    
    def test_get_active_accounts(self, account_registry):
        """Test getting active accounts."""
        account_registry.update_status("test_account", AccountStatus.DISABLED)
        
        active = account_registry.get_active_accounts()
        
        assert len(active) == 1
        assert active[0].name == "test_account_2"
    
    def test_get_accounts_by_priority(self, account_registry):
        """Test getting accounts sorted by priority."""
        sorted_accounts = account_registry.get_accounts_by_priority()
        
        assert sorted_accounts[0].name == "test_account_2"  # priority 2
        assert sorted_accounts[1].name == "test_account"    # priority 1
    
    def test_get_weighted_accounts(self, account_registry):
        """Test getting weighted accounts."""
        weighted = account_registry.get_weighted_accounts()
        
        assert len(weighted) == 2
        # Total weight = 3.0, so weights should be 1/3 and 2/3
        assert weighted[0][1] == pytest.approx(1/3, rel=0.01)
        assert weighted[1][1] == pytest.approx(2/3, rel=0.01)
    
    def test_update_status(self, account_registry):
        """Test updating account status."""
        result = account_registry.update_status("test_account", AccountStatus.ERROR)
        
        assert result is True
        account = account_registry.get_account("test_account")
        assert account.status == AccountStatus.ERROR
    
    def test_set_private_key(self, account_registry):
        """Test setting private key."""
        result = account_registry.set_private_key("test_account", "new_key")
        
        assert result is True
        account = account_registry.get_account("test_account")
        assert account.private_key == "new_key"


# ==================== Load Functions Tests ====================

class TestLoadFunctions:
    """Tests for account loading functions."""
    
    def test_load_accounts_from_env(self, monkeypatch):
        """Test loading accounts from environment variables."""
        # Set up environment variables
        env_vars = {
            "POLYMARKET_ACCOUNT_1_NAME": "env_account_1",
            "POLYMARKET_ACCOUNT_1_API_KEY": "env_key_1",
            "POLYMARKET_ACCOUNT_1_API_SECRET": "env_secret_1",
            "POLYMARKET_ACCOUNT_1_WALLET_ADDRESS": "0x1111111111111111111111111111111111111111",
            "POLYMARKET_ACCOUNT_1_PRIORITY": "1",
            "POLYMARKET_ACCOUNT_1_WEIGHT": "1.5",
            
            "POLYMARKET_ACCOUNT_2_NAME": "env_account_2",
            "POLYMARKET_ACCOUNT_2_API_KEY": "env_key_2",
            "POLYMARKET_ACCOUNT_2_API_SECRET": "env_secret_2",
            "POLYMARKET_ACCOUNT_2_WALLET_ADDRESS": "0x2222222222222222222222222222222222222222",
        }
        
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)
        
        registry = load_accounts_from_env()
        
        assert len(registry) == 2
        account1 = registry.get_account("env_account_1")
        assert account1 is not None
        assert account1.weight == 1.5
    
    def test_load_accounts_from_file(self, temp_config_file):
        """Test loading accounts from JSON file."""
        registry = load_accounts_from_file(temp_config_file)
        
        assert len(registry) == 2
        account1 = registry.get_account("file_account_1")
        assert account1 is not None
        assert account1.priority == 1
    
    def test_load_accounts_from_file_not_found(self):
        """Test loading from nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            load_accounts_from_file("nonexistent.json")
    
    def test_load_accounts_from_vault(self):
        """Test loading accounts from vault variables."""
        vault_vars = {
            "POLYMARKET_ACCOUNT_1_NAME": "vault_account_1",
            "POLYMARKET_ACCOUNT_1_API_KEY": "vault_key_1",
            "POLYMARKET_ACCOUNT_1_API_SECRET": "vault_secret_1",
            "POLYMARKET_ACCOUNT_1_WALLET_ADDRESS": "0x3333333333333333333333333333333333333333",
            "POLYMARKET_ACCOUNT_1_PRIVATE_KEY": "vault_private_key_1",
        }
        
        registry = load_accounts_from_vault(vault_vars)
        
        assert len(registry) == 1
        account = registry.get_account("vault_account_1")
        assert account is not None
        assert account.private_key == "vault_private_key_1"


# ==================== AccountState Tests ====================

class TestAccountState:
    """Tests for AccountState class."""
    
    def test_create_account_state(self):
        """Test creating account state."""
        state = AccountState(account_name="test")
        
        assert state.account_name == "test"
        assert state.balance == 0.0
        assert state.consecutive_errors == 0
    
    def test_is_healthy(self):
        """Test is_healthy method."""
        state = AccountState(account_name="test")
        
        assert state.is_healthy()
        
        state.consecutive_errors = 3
        assert not state.is_healthy()
        
        state.consecutive_errors = 2
        assert state.is_healthy(max_consecutive_errors=3)
    
    def test_record_success(self):
        """Test recording a successful operation."""
        state = AccountState(account_name="test")
        
        state.record_success(volume=100.0)
        
        assert state.consecutive_errors == 0
        assert state.total_trades == 1
        assert state.total_volume == 100.0
        assert state.last_used is not None
    
    def test_record_error(self):
        """Test recording an error."""
        state = AccountState(account_name="test")
        
        state.record_error("Test error")
        
        assert state.consecutive_errors == 1
        assert state.error_count == 1
        assert state.last_error == "Test error"
    
    def test_reset_daily_stats(self):
        """Test resetting daily statistics."""
        state = AccountState(
            account_name="test",
            daily_volume=1000.0,
            daily_trades=10
        )
        
        state.reset_daily_stats()
        
        assert state.daily_volume == 0.0
        assert state.daily_trades == 0


# ==================== AccountManager Tests ====================

class TestAccountManager:
    """Tests for AccountManager class."""
    
    @pytest.mark.asyncio
    async def test_initialize_account_manager(self, account_registry):
        """Test initializing the account manager."""
        manager = AccountManager(account_registry)
        
        with patch.object(manager, '_initialize_account', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = True
            await manager.initialize()
            
            assert mock_init.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_active_accounts(self, account_registry):
        """Test getting active accounts."""
        manager = AccountManager(account_registry)
        
        # Mock states
        manager._states = {
            "test_account": AccountState(account_name="test_account"),
            "test_account_2": AccountState(account_name="test_account_2"),
        }
        
        active = manager.get_active_accounts()
        
        assert len(active) == 2
    
    @pytest.mark.asyncio
    async def test_rotation_strategies(self, account_registry):
        """Test different rotation strategies."""
        manager = AccountManager(account_registry)
        
        # Mock states
        manager._states = {
            "test_account": AccountState(account_name="test_account"),
            "test_account_2": AccountState(account_name="test_account_2"),
        }
        
        # Test round robin
        manager.rotation_strategy = RotationStrategy.ROUND_ROBIN
        name1 = manager._select_round_robin(["test_account", "test_account_2"])
        name2 = manager._select_round_robin(["test_account", "test_account_2"])
        assert name1 != name2  # Should rotate
        
        # Test priority
        manager.rotation_strategy = RotationStrategy.PRIORITY
        name = manager._select_priority(["test_account", "test_account_2"])
        assert name == "test_account_2"  # Higher priority
        
        # Test least used
        manager.rotation_strategy = RotationStrategy.LEAST_USED
        manager._states["test_account"].last_used = datetime.utcnow()
        manager._states["test_account_2"].last_used = None
        name = manager._select_least_used(["test_account", "test_account_2"])
        assert name == "test_account_2"  # Never used
    
    @pytest.mark.asyncio
    async def test_weighted_random_selection(self, account_registry):
        """Test weighted random selection."""
        manager = AccountManager(account_registry)
        
        manager._states = {
            "test_account": AccountState(account_name="test_account"),
            "test_account_2": AccountState(account_name="test_account_2"),
        }
        
        # Run selection multiple times and check distribution
        selections = {"test_account": 0, "test_account_2": 0}
        for _ in range(1000):
            name = manager._select_weighted_random(["test_account", "test_account_2"])
            selections[name] += 1
        
        # test_account_2 has weight 2.0, test_account has weight 1.0
        # So test_account_2 should be selected about 2/3 of the time
        ratio = selections["test_account_2"] / selections["test_account"]
        assert 1.5 < ratio < 2.5  # Allow some variance
    
    @pytest.mark.asyncio
    async def test_execute_with_failover_success(self, account_registry):
        """Test successful execution with failover."""
        manager = AccountManager(account_registry)
        
        # Mock client
        mock_client = AsyncMock()
        mock_client.get_markets = AsyncMock(return_value=[])
        
        manager._states = {
            "test_account": AccountState(
                account_name="test_account",
                client=mock_client
            ),
        }
        
        async def operation(client):
            return await client.get_markets()
        
        result, account_name = await manager.execute_with_failover(operation)
        
        assert result == []
        assert account_name == "test_account"
        assert manager._states["test_account"].consecutive_errors == 0
    
    @pytest.mark.asyncio
    async def test_execute_with_failover_error(self, account_registry):
        """Test execution with error and failover."""
        manager = AccountManager(account_registry)
        manager.error_cooldown_seconds = 0.01  # Speed up test
        
        # Mock clients - first fails, second succeeds
        mock_client_1 = AsyncMock()
        mock_client_1.get_markets = AsyncMock(side_effect=Exception("API Error"))
        
        mock_client_2 = AsyncMock()
        mock_client_2.get_markets = AsyncMock(return_value=[])
        
        manager._states = {
            "test_account": AccountState(
                account_name="test_account",
                client=mock_client_1
            ),
            "test_account_2": AccountState(
                account_name="test_account_2",
                client=mock_client_2
            ),
        }
        
        async def operation(client):
            return await client.get_markets()
        
        result, account_name = await manager.execute_with_failover(operation, max_attempts=3)
        
        assert result == []
        assert account_name == "test_account_2"
        assert manager._states["test_account"].consecutive_errors == 1
    
    @pytest.mark.asyncio
    async def test_execute_with_failover_all_fail(self, account_registry):
        """Test execution when all accounts fail."""
        manager = AccountManager(account_registry)
        manager.error_cooldown_seconds = 0.01  # Speed up test
        
        # Mock clients - all fail
        mock_client = AsyncMock()
        mock_client.get_markets = AsyncMock(side_effect=Exception("API Error"))
        
        manager._states = {
            "test_account": AccountState(
                account_name="test_account",
                client=mock_client
            ),
            "test_account_2": AccountState(
                account_name="test_account_2",
                client=mock_client
            ),
        }
        
        async def operation(client):
            return await client.get_markets()
        
        with pytest.raises(Exception, match="All accounts failed"):
            await manager.execute_with_failover(operation, max_attempts=3)
    
    @pytest.mark.asyncio
    async def test_get_aggregate_stats(self, account_registry):
        """Test getting aggregate statistics."""
        manager = AccountManager(account_registry)
        
        manager._states = {
            "test_account": AccountState(
                account_name="test_account",
                balance=100.0,
                total_trades=10,
                total_volume=1000.0
            ),
            "test_account_2": AccountState(
                account_name="test_account_2",
                balance=200.0,
                total_trades=20,
                total_volume=2000.0
            ),
        }
        
        stats = manager.get_aggregate_stats()
        
        assert stats["total_accounts"] == 2
        assert stats["total_balance"] == 300.0
        assert stats["total_trades"] == 30
        assert stats["total_volume"] == 3000.0
    
    @pytest.mark.asyncio
    async def test_get_account_status_report(self, account_registry):
        """Test getting account status report."""
        manager = AccountManager(account_registry)
        
        manager._states = {
            "test_account": AccountState(
                account_name="test_account",
                balance=100.0,
                consecutive_errors=1
            ),
        }
        
        report = manager.get_account_status_report()
        
        assert len(report) == 1
        assert report[0]["name"] == "test_account"
        assert report[0]["balance"] == 100.0
        assert report[0]["consecutive_errors"] == 1
    
    @pytest.mark.asyncio
    async def test_add_account(self, account_registry):
        """Test adding a new account."""
        manager = AccountManager(account_registry)
        
        new_account = AccountConfig(
            name="new_account",
            api_key="new_key",
            api_secret="new_secret",
            wallet_address="0x4444444444444444444444444444444444444444",
            private_key="0x4444444444444444444444444444444444444444444444444444444444444444",
        )
        
        with patch.object(manager, '_initialize_account', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = True
            result = await manager.add_account(new_account)
            
            assert result is True
            assert "new_account" in manager.registry
    
    @pytest.mark.asyncio
    async def test_remove_account(self, account_registry):
        """Test removing an account."""
        manager = AccountManager(account_registry)
        
        # Add state
        manager._states["test_account"] = AccountState(
            account_name="test_account",
            client=AsyncMock()
        )
        
        result = await manager.remove_account("test_account")
        
        assert result is True
        assert "test_account" not in manager._states
        assert "test_account" not in manager.registry
    
    @pytest.mark.asyncio
    async def test_close(self, account_registry):
        """Test closing the manager."""
        manager = AccountManager(account_registry)
        
        # Add mock clients
        mock_client_1 = AsyncMock()
        mock_client_1.close = AsyncMock()
        mock_client_2 = AsyncMock()
        mock_client_2.close = AsyncMock()
        
        manager._states = {
            "test_account": AccountState(
                account_name="test_account",
                client=mock_client_1
            ),
            "test_account_2": AccountState(
                account_name="test_account_2",
                client=mock_client_2
            ),
        }
        
        await manager.close()
        
        mock_client_1.close.assert_called_once()
        mock_client_2.close.assert_called_once()


# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests for multi-account support."""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test the full multi-account workflow."""
        # Create registry
        registry = AccountRegistry()
        
        # Add accounts
        account1 = AccountConfig(
            name="integration_account_1",
            api_key="key1",
            api_secret="secret1",
            wallet_address="0x1111111111111111111111111111111111111111",
            private_key="0x1111111111111111111111111111111111111111111111111111111111111111",
            priority=1,
            weight=1.0,
        )
        account2 = AccountConfig(
            name="integration_account_2",
            api_key="key2",
            api_secret="secret2",
            wallet_address="0x2222222222222222222222222222222222222222",
            private_key="0x2222222222222222222222222222222222222222222222222222222222222222",
            priority=2,
            weight=2.0,
        )
        
        registry.add_account(account1)
        registry.add_account(account2)
        
        # Create manager
        manager = AccountManager(
            registry,
            rotation_strategy=RotationStrategy.PRIORITY
        )
        
        # Verify setup
        assert len(manager.registry) == 2
        accounts = manager.registry.get_accounts_by_priority()
        assert accounts[0].name == "integration_account_2"  # Higher priority


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
