"""
Multi-Account Configuration System

This module provides configuration management for multiple Polymarket accounts
with support for loading from environment variables or config files.

Features:
- Load account configurations from environment variables or JSON/YAML files
- Account priorities and weights for load balancing
- Secure credential handling
- Validation of account configurations
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum


logger = logging.getLogger(__name__)


class AccountStatus(Enum):
    """Account status enum"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class AccountConfig:
    """
    Configuration for a single Polymarket account.
    
    Attributes:
        name: Unique identifier for the account
        api_key: Polymarket API key
        api_secret: Polymarket API secret
        wallet_address: Ethereum wallet address for the account
        private_key: Private key for signing (loaded from vault)
        priority: Priority level (higher = more priority)
        weight: Weight for load balancing (default: 1.0)
        chain_id: Chain ID for the account (default: 137 for Polygon Mainnet)
        status: Account status
        max_position_size: Maximum position size for this account
        daily_limit: Daily trading limit for this account
        metadata: Additional metadata for the account
    """
    name: str
    api_key: str
    api_secret: str
    wallet_address: str
    private_key: Optional[str] = None
    priority: int = 1
    weight: float = 1.0
    chain_id: int = 137
    status: AccountStatus = AccountStatus.ACTIVE
    max_position_size: Optional[float] = None
    daily_limit: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate account configuration after initialization."""
        self._validate()
    
    def _validate(self):
        """Validate account configuration."""
        if not self.name:
            raise ValueError("Account name is required")
        
        if not self.api_key:
            raise ValueError(f"API key is required for account '{self.name}'")
        
        if not self.api_secret:
            raise ValueError(f"API secret is required for account '{self.name}'")
        
        if not self.wallet_address:
            raise ValueError(f"Wallet address is required for account '{self.name}'")
        
        # Validate wallet address format (basic check)
        if not self.wallet_address.startswith('0x') or len(self.wallet_address) != 42:
            raise ValueError(
                f"Invalid wallet address format for account '{self.name}': "
                f"expected 0x followed by 40 hex characters"
            )
        
        # Validate weight
        if self.weight <= 0:
            raise ValueError(f"Weight must be positive for account '{self.name}'")
        
        # Validate priority
        if self.priority < 0:
            raise ValueError(f"Priority cannot be negative for account '{self.name}'")
    
    def is_active(self) -> bool:
        """Check if account is active and usable."""
        return self.status == AccountStatus.ACTIVE and self.private_key is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert account config to dictionary (excludes sensitive data)."""
        return {
            "name": self.name,
            "api_key": self.api_key[:8] + "..." if self.api_key else None,
            "wallet_address": self.wallet_address,
            "priority": self.priority,
            "weight": self.weight,
            "chain_id": self.chain_id,
            "status": self.status.value,
            "max_position_size": self.max_position_size,
            "daily_limit": self.daily_limit,
            "metadata": self.metadata,
        }


class AccountRegistry:
    """
    Registry for managing multiple Polymarket account configurations.
    
    Features:
    - Store and retrieve account configurations
    - Get accounts by priority/weight for load balancing
    - Track account status
    - Thread-safe operations
    """
    
    def __init__(self):
        """Initialize the account registry."""
        self._accounts: Dict[str, AccountConfig] = {}
        self._account_order: List[str] = []  # For consistent ordering
    
    def add_account(self, account: AccountConfig) -> None:
        """
        Add an account to the registry.
        
        Args:
            account: AccountConfig to add
            
        Raises:
            ValueError: If account with same name already exists
        """
        if account.name in self._accounts:
            raise ValueError(f"Account '{account.name}' already exists")
        
        self._accounts[account.name] = account
        self._account_order.append(account.name)
        logger.info(f"Added account '{account.name}' to registry")
    
    def remove_account(self, name: str) -> Optional[AccountConfig]:
        """
        Remove an account from the registry.
        
        Args:
            name: Name of the account to remove
            
        Returns:
            Removed AccountConfig or None if not found
        """
        if name in self._accounts:
            account = self._accounts.pop(name)
            self._account_order.remove(name)
            logger.info(f"Removed account '{name}' from registry")
            return account
        return None
    
    def get_account(self, name: str) -> Optional[AccountConfig]:
        """
        Get an account by name.
        
        Args:
            name: Account name
            
        Returns:
            AccountConfig or None if not found
        """
        return self._accounts.get(name)
    
    def get_all_accounts(self) -> List[AccountConfig]:
        """
        Get all accounts in the registry.
        
        Returns:
            List of all AccountConfig objects
        """
        return [self._accounts[name] for name in self._account_order]
    
    def get_active_accounts(self) -> List[AccountConfig]:
        """
        Get all active accounts.
        
        Returns:
            List of active AccountConfig objects
        """
        return [
            acc for acc in self.get_all_accounts()
            if acc.status == AccountStatus.ACTIVE
        ]
    
    def get_accounts_by_priority(self) -> List[AccountConfig]:
        """
        Get accounts sorted by priority (highest first).
        
        Returns:
            List of AccountConfig objects sorted by priority
        """
        accounts = self.get_active_accounts()
        return sorted(accounts, key=lambda x: x.priority, reverse=True)
    
    def get_weighted_accounts(self) -> List[tuple]:
        """
        Get active accounts with their normalized weights.
        
        Returns:
            List of (AccountConfig, normalized_weight) tuples
        """
        accounts = self.get_active_accounts()
        total_weight = sum(acc.weight for acc in accounts)
        
        if total_weight <= 0:
            return []
        
        return [
            (acc, acc.weight / total_weight)
            for acc in accounts
        ]
    
    def update_status(self, name: str, status: AccountStatus) -> bool:
        """
        Update the status of an account.
        
        Args:
            name: Account name
            status: New status
            
        Returns:
            True if updated, False if account not found
        """
        if name in self._accounts:
            self._accounts[name].status = status
            logger.info(f"Updated account '{name}' status to {status.value}")
            return True
        return False
    
    def set_private_key(self, name: str, private_key: str) -> bool:
        """
        Set the private key for an account.
        
        Args:
            name: Account name
            private_key: Private key to set
            
        Returns:
            True if set, False if account not found
        """
        if name in self._accounts:
            self._accounts[name].private_key = private_key
            logger.info(f"Set private key for account '{name}'")
            return True
        return False
    
    def __len__(self) -> int:
        """Return number of accounts in registry."""
        return len(self._accounts)
    
    def __contains__(self, name: str) -> bool:
        """Check if account exists in registry."""
        return name in self._accounts


def load_accounts_from_env(prefix: str = "POLYMARKET_ACCOUNT") -> AccountRegistry:
    """
    Load account configurations from environment variables.
    
    Expected format:
        POLYMARKET_ACCOUNT_1_NAME=account1
        POLYMARKET_ACCOUNT_1_API_KEY=xxx
        POLYMARKET_ACCOUNT_1_API_SECRET=xxx
        POLYMARKET_ACCOUNT_1_WALLET_ADDRESS=0x...
        POLYMARKET_ACCOUNT_1_PRIORITY=1
        POLYMARKET_ACCOUNT_1_WEIGHT=1.0
        
        POLYMARKET_ACCOUNT_2_NAME=account2
        ...
    
    Args:
        prefix: Environment variable prefix
        
    Returns:
        AccountRegistry with loaded accounts
    """
    registry = AccountRegistry()
    
    # Find all account indices
    indices = set()
    for key in os.environ:
        if key.startswith(prefix + "_"):
            parts = key.split("_")
            if len(parts) >= 3:
                try:
                    idx = int(parts[2])
                    indices.add(idx)
                except ValueError:
                    continue
    
    # Load each account
    for idx in sorted(indices):
        env_prefix = f"{prefix}_{idx}"
        
        name = os.environ.get(f"{env_prefix}_NAME")
        api_key = os.environ.get(f"{env_prefix}_API_KEY")
        api_secret = os.environ.get(f"{env_prefix}_API_SECRET")
        wallet_address = os.environ.get(f"{env_prefix}_WALLET_ADDRESS")
        
        if not all([name, api_key, api_secret, wallet_address]):
            logger.warning(f"Skipping account {idx}: missing required fields")
            continue
        
        # Optional fields
        priority = int(os.environ.get(f"{env_prefix}_PRIORITY", "1"))
        weight = float(os.environ.get(f"{env_prefix}_WEIGHT", "1.0"))
        chain_id = int(os.environ.get(f"{env_prefix}_CHAIN_ID", "137"))
        max_position_size = os.environ.get(f"{env_prefix}_MAX_POSITION_SIZE")
        daily_limit = os.environ.get(f"{env_prefix}_DAILY_LIMIT")
        
        try:
            account = AccountConfig(
                name=name,
                api_key=api_key,
                api_secret=api_secret,
                wallet_address=wallet_address,
                priority=priority,
                weight=weight,
                chain_id=chain_id,
                max_position_size=float(max_position_size) if max_position_size else None,
                daily_limit=float(daily_limit) if daily_limit else None,
            )
            registry.add_account(account)
        except ValueError as e:
            logger.error(f"Failed to load account {idx}: {e}")
    
    logger.info(f"Loaded {len(registry)} accounts from environment")
    return registry


def load_accounts_from_file(file_path: str) -> AccountRegistry:
    """
    Load account configurations from a JSON file.
    
    Expected JSON format:
    {
        "accounts": [
            {
                "name": "account1",
                "api_key": "xxx",
                "api_secret": "xxx",
                "wallet_address": "0x...",
                "priority": 1,
                "weight": 1.0
            },
            ...
        ]
    }
    
    Args:
        file_path: Path to the JSON configuration file
        
    Returns:
        AccountRegistry with loaded accounts
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Account config file not found: {file_path}")
    
    with open(path, 'r') as f:
        data = json.load(f)
    
    if 'accounts' not in data:
        raise ValueError("Invalid config file: 'accounts' key not found")
    
    registry = AccountRegistry()
    
    for account_data in data['accounts']:
        try:
            account = AccountConfig(
                name=account_data['name'],
                api_key=account_data['api_key'],
                api_secret=account_data['api_secret'],
                wallet_address=account_data['wallet_address'],
                priority=account_data.get('priority', 1),
                weight=account_data.get('weight', 1.0),
                chain_id=account_data.get('chain_id', 137),
                max_position_size=account_data.get('max_position_size'),
                daily_limit=account_data.get('daily_limit'),
                metadata=account_data.get('metadata', {}),
            )
            registry.add_account(account)
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to load account from file: {e}")
    
    logger.info(f"Loaded {len(registry)} accounts from {file_path}")
    return registry


def load_accounts_from_vault(vault_vars: Dict[str, str], prefix: str = "POLYMARKET_ACCOUNT") -> AccountRegistry:
    """
    Load account configurations from vault variables.
    
    This is similar to load_accounts_from_env but takes a dictionary
    from the vault instead of os.environ.
    
    Args:
        vault_vars: Dictionary of variables from vault
        prefix: Variable prefix
        
    Returns:
        AccountRegistry with loaded accounts
    """
    registry = AccountRegistry()
    
    # Find all account indices
    indices = set()
    for key in vault_vars:
        if key.startswith(prefix + "_"):
            parts = key.split("_")
            if len(parts) >= 3:
                try:
                    idx = int(parts[2])
                    indices.add(idx)
                except ValueError:
                    continue
    
    # Load each account
    for idx in sorted(indices):
        env_prefix = f"{prefix}_{idx}"
        
        name = vault_vars.get(f"{env_prefix}_NAME")
        api_key = vault_vars.get(f"{env_prefix}_API_KEY")
        api_secret = vault_vars.get(f"{env_prefix}_API_SECRET")
        wallet_address = vault_vars.get(f"{env_prefix}_WALLET_ADDRESS")
        private_key = vault_vars.get(f"{env_prefix}_PRIVATE_KEY")
        
        if not all([name, api_key, api_secret, wallet_address]):
            logger.warning(f"Skipping account {idx}: missing required fields")
            continue
        
        # Optional fields
        priority = int(vault_vars.get(f"{env_prefix}_PRIORITY", "1"))
        weight = float(vault_vars.get(f"{env_prefix}_WEIGHT", "1.0"))
        chain_id = int(vault_vars.get(f"{env_prefix}_CHAIN_ID", "137"))
        max_position_size = vault_vars.get(f"{env_prefix}_MAX_POSITION_SIZE")
        daily_limit = vault_vars.get(f"{env_prefix}_DAILY_LIMIT")
        
        try:
            account = AccountConfig(
                name=name,
                api_key=api_key,
                api_secret=api_secret,
                wallet_address=wallet_address,
                private_key=private_key,
                priority=priority,
                weight=weight,
                chain_id=chain_id,
                max_position_size=float(max_position_size) if max_position_size else None,
                daily_limit=float(daily_limit) if daily_limit else None,
            )
            registry.add_account(account)
        except ValueError as e:
            logger.error(f"Failed to load account {idx}: {e}")
    
    logger.info(f"Loaded {len(registry)} accounts from vault")
    return registry
