"""
Multi-Account Manager

This module provides management of multiple Polymarket accounts with:
- Account rotation for load balancing
- Per-account state tracking (balances, positions)
- Graceful failover when accounts fail
- Thread-safe operations
"""

import asyncio
import logging
import random
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict

from backend.config.accounts import AccountConfig, AccountRegistry, AccountStatus
from backend.api.polymarket_client import PolymarketClient
from backend.signing import PolymarketSigner


logger = logging.getLogger(__name__)


class RotationStrategy(Enum):
    """Account rotation strategies"""
    ROUND_ROBIN = "round_robin"
    WEIGHTED_RANDOM = "weighted_random"
    PRIORITY = "priority"
    LEAST_USED = "least_used"


@dataclass
class AccountState:
    """
    Runtime state for a single account.
    
    Tracks balances, positions, and usage statistics.
    """
    account_name: str
    balance: float = 0.0
    available_balance: float = 0.0
    positions: Dict[str, float] = field(default_factory=dict)  # token_id -> amount
    open_orders: int = 0
    total_trades: int = 0
    total_volume: float = 0.0
    daily_volume: float = 0.0
    daily_trades: int = 0
    last_used: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0
    consecutive_errors: int = 0
    client: Optional[PolymarketClient] = None
    signer: Optional[PolymarketSigner] = None
    
    def is_healthy(self, max_consecutive_errors: int = 3) -> bool:
        """Check if account is healthy and usable."""
        return self.consecutive_errors < max_consecutive_errors
    
    def record_success(self, volume: float = 0.0):
        """Record a successful operation."""
        self.consecutive_errors = 0
        self.error_count = 0
        self.last_used = datetime.utcnow()
        self.total_trades += 1
        self.daily_trades += 1
        self.total_volume += volume
        self.daily_volume += volume
    
    def record_error(self, error: str):
        """Record a failed operation."""
        self.error_count += 1
        self.consecutive_errors += 1
        self.last_error = error
        self.last_used = datetime.utcnow()
        logger.warning(
            f"Account '{self.account_name}' error ({self.consecutive_errors} consecutive): {error}"
        )
    
    def reset_daily_stats(self):
        """Reset daily statistics."""
        self.daily_volume = 0.0
        self.daily_trades = 0


@dataclass
class FailoverResult:
    """Result of a failover operation."""
    success: bool
    original_account: str
    failover_account: Optional[str]
    error: Optional[str] = None


class AccountManager:
    """
    Manager for multiple Polymarket accounts.
    
    Features:
    - Manage multiple account connections
    - Rotate between accounts for API calls
    - Track per-account balances and positions
    - Handle account failures gracefully with automatic failover
    - Thread-safe operations with async locks
    
    Usage:
        manager = AccountManager(registry)
        await manager.initialize()
        
        # Get next account for trading
        account = await manager.get_next_account()
        
        # Execute with automatic failover
        result = await manager.execute_with_failover(
            lambda client: client.get_markets()
        )
    """
    
    def __init__(
        self,
        registry: AccountRegistry,
        rotation_strategy: RotationStrategy = RotationStrategy.WEIGHTED_RANDOM,
        max_consecutive_errors: int = 3,
        error_cooldown_seconds: float = 60.0,
        balance_refresh_interval: float = 300.0,
    ):
        """
        Initialize the account manager.
        
        Args:
            registry: AccountRegistry with account configurations
            rotation_strategy: Strategy for account rotation
            max_consecutive_errors: Max errors before disabling account
            error_cooldown_seconds: Cooldown period after errors
            balance_refresh_interval: Interval for balance refresh in seconds
        """
        self.registry = registry
        self.rotation_strategy = rotation_strategy
        self.max_consecutive_errors = max_consecutive_errors
        self.error_cooldown_seconds = error_cooldown_seconds
        self.balance_refresh_interval = balance_refresh_interval
        
        # Account states
        self._states: Dict[str, AccountState] = {}
        
        # Rotation state
        self._round_robin_index = 0
        self._lock = asyncio.Lock()
        
        # Background tasks
        self._balance_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def initialize(self) -> None:
        """
        Initialize all account connections.
        
        Creates signers and clients for each account with private keys.
        """
        async with self._lock:
            for account in self.registry.get_all_accounts():
                await self._initialize_account(account)
            
            logger.info(f"Initialized {len(self._states)} accounts")
    
    async def _initialize_account(self, account: AccountConfig) -> bool:
        """
        Initialize a single account.
        
        Args:
            account: Account configuration
            
        Returns:
            True if initialized successfully
        """
        if account.name in self._states:
            return True
        
        if not account.private_key:
            logger.warning(f"Account '{account.name}' has no private key, skipping")
            self.registry.update_status(account.name, AccountStatus.INACTIVE)
            return False
        
        try:
            # Create signer
            signer = PolymarketSigner(
                private_key=account.private_key,
                chain_id=account.chain_id
            )
            
            # Create client
            client = PolymarketClient(
                signer=signer,
                chain_id=account.chain_id
            )
            
            # Create state
            state = AccountState(
                account_name=account.name,
                client=client,
                signer=signer
            )
            
            self._states[account.name] = state
            self.registry.update_status(account.name, AccountStatus.ACTIVE)
            
            logger.info(f"Initialized account '{account.name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize account '{account.name}': {e}")
            self.registry.update_status(account.name, AccountStatus.ERROR)
            return False
    
    async def close(self) -> None:
        """Close all account connections."""
        self._running = False
        
        if self._balance_task:
            self._balance_task.cancel()
            try:
                await self._balance_task
            except asyncio.CancelledError:
                pass
        
        for state in self._states.values():
            if state.client:
                await state.client.close()
        
        logger.info("Closed all account connections")
    
    def get_account_names(self) -> List[str]:
        """Get list of all account names."""
        return list(self._states.keys())
    
    def get_state(self, account_name: str) -> Optional[AccountState]:
        """Get state for a specific account."""
        return self._states.get(account_name)
    
    def get_active_accounts(self) -> List[str]:
        """Get list of active account names."""
        return [
            name for name, state in self._states.items()
            if state.is_healthy(self.max_consecutive_errors)
            and self.registry.get_account(name).status == AccountStatus.ACTIVE
        ]
    
    async def get_next_account(
        self,
        exclude: Optional[List[str]] = None
    ) -> Optional[AccountConfig]:
        """
        Get the next account based on rotation strategy.
        
        Args:
            exclude: List of account names to exclude
            
        Returns:
            Next AccountConfig or None if no accounts available
        """
        exclude = exclude or []
        
        async with self._lock:
            active = [
                name for name in self.get_active_accounts()
                if name not in exclude
            ]
            
            if not active:
                logger.warning("No active accounts available")
                return None
            
            # Select account based on strategy
            if self.rotation_strategy == RotationStrategy.ROUND_ROBIN:
                name = self._select_round_robin(active)
            elif self.rotation_strategy == RotationStrategy.WEIGHTED_RANDOM:
                name = self._select_weighted_random(active)
            elif self.rotation_strategy == RotationStrategy.PRIORITY:
                name = self._select_priority(active)
            elif self.rotation_strategy == RotationStrategy.LEAST_USED:
                name = self._select_least_used(active)
            else:
                name = active[0]
            
            return self.registry.get_account(name)
    
    def _select_round_robin(self, accounts: List[str]) -> str:
        """Select account using round-robin."""
        if self._round_robin_index >= len(accounts):
            self._round_robin_index = 0
        
        name = accounts[self._round_robin_index]
        self._round_robin_index = (self._round_robin_index + 1) % len(accounts)
        return name
    
    def _select_weighted_random(self, accounts: List[str]) -> str:
        """Select account using weighted random selection."""
        weights = []
        for name in accounts:
            account = self.registry.get_account(name)
            weights.append(account.weight if account else 1.0)
        
        total = sum(weights)
        r = random.random() * total
        
        cumulative = 0.0
        for name, weight in zip(accounts, weights):
            cumulative += weight
            if r <= cumulative:
                return name
        
        return accounts[-1]
    
    def _select_priority(self, accounts: List[str]) -> str:
        """Select account with highest priority."""
        best_name = accounts[0]
        best_priority = 0
        
        for name in accounts:
            account = self.registry.get_account(name)
            if account and account.priority > best_priority:
                best_priority = account.priority
                best_name = name
        
        return best_name
    
    def _select_least_used(self, accounts: List[str]) -> str:
        """Select least recently used account."""
        best_name = accounts[0]
        best_time = datetime.utcnow()
        
        for name in accounts:
            state = self._states.get(name)
            if state:
                if state.last_used is None:
                    return name
                if state.last_used < best_time:
                    best_time = state.last_used
                    best_name = name
        
        return best_name
    
    def get_client(self, account_name: str) -> Optional[PolymarketClient]:
        """Get the client for a specific account."""
        state = self._states.get(account_name)
        return state.client if state else None
    
    def get_signer(self, account_name: str) -> Optional[PolymarketSigner]:
        """Get the signer for a specific account."""
        state = self._states.get(account_name)
        return state.signer if state else None
    
    async def execute_with_failover(
        self,
        operation: Callable[[PolymarketClient], Any],
        max_attempts: int = 3,
        account_name: Optional[str] = None,
    ) -> tuple:
        """
        Execute an operation with automatic failover.
        
        Args:
            operation: Async function taking PolymarketClient
            max_attempts: Maximum attempts across all accounts
            account_name: Specific account to use (optional)
            
        Returns:
            Tuple of (result, account_name_used)
            
        Raises:
            Exception: If all attempts fail
        """
        tried_accounts = []
        last_error = None
        
        for attempt in range(max_attempts):
            # Get account
            if account_name and account_name not in tried_accounts:
                account = self.registry.get_account(account_name)
            else:
                account = await self.get_next_account(exclude=tried_accounts)
            
            if not account:
                raise Exception("No available accounts for operation")
            
            tried_accounts.append(account.name)
            state = self._states.get(account.name)
            
            if not state or not state.client:
                continue
            
            try:
                # Execute operation
                result = await operation(state.client)
                state.record_success()
                return result, account.name
                
            except Exception as e:
                error_msg = str(e)
                state.record_error(error_msg)
                last_error = e
                
                # Check if account should be disabled
                if not state.is_healthy(self.max_consecutive_errors):
                    self.registry.update_status(account.name, AccountStatus.ERROR)
                    logger.error(
                        f"Disabled account '{account.name}' due to consecutive errors"
                    )
                
                # Wait before retry
                if attempt < max_attempts - 1:
                    await asyncio.sleep(self.error_cooldown_seconds)
        
        raise Exception(
            f"All accounts failed after {max_attempts} attempts. "
            f"Tried: {tried_accounts}. Last error: {last_error}"
        )
    
    async def update_balance(self, account_name: str) -> bool:
        """
        Update balance for a specific account.
        
        Args:
            account_name: Account to update
            
        Returns:
            True if successful
        """
        state = self._states.get(account_name)
        if not state or not state.client:
            return False
        
        try:
            # Get balance from API (simplified - actual implementation
            # would query the blockchain or API)
            # For now, we'll just mark it as updated
            state.last_used = datetime.utcnow()
            return True
            
        except Exception as e:
            state.record_error(str(e))
            return False
    
    async def update_all_balances(self) -> None:
        """Update balances for all accounts."""
        tasks = [
            self.update_balance(name)
            for name in self._states.keys()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _balance_refresh_loop(self) -> None:
        """Background task to periodically refresh balances."""
        while self._running:
            try:
                await asyncio.sleep(self.balance_refresh_interval)
                await self.update_all_balances()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Balance refresh error: {e}")
    
    def start_balance_refresh(self) -> None:
        """Start the background balance refresh task."""
        if not self._running:
            self._running = True
            self._balance_task = asyncio.create_task(self._balance_refresh_loop())
            logger.info("Started balance refresh task")
    
    def get_aggregate_stats(self) -> Dict[str, Any]:
        """
        Get aggregate statistics across all accounts.
        
        Returns:
            Dictionary with aggregate stats
        """
        total_balance = 0.0
        total_available = 0.0
        total_positions = 0
        total_trades = 0
        total_volume = 0.0
        active_accounts = 0
        error_accounts = 0
        
        for name, state in self._states.items():
            account = self.registry.get_account(name)
            if account:
                if account.status == AccountStatus.ACTIVE:
                    active_accounts += 1
                elif account.status == AccountStatus.ERROR:
                    error_accounts += 1
            
            total_balance += state.balance
            total_available += state.available_balance
            total_positions += len(state.positions)
            total_trades += state.total_trades
            total_volume += state.total_volume
        
        return {
            "total_accounts": len(self._states),
            "active_accounts": active_accounts,
            "error_accounts": error_accounts,
            "total_balance": total_balance,
            "total_available_balance": total_available,
            "total_positions": total_positions,
            "total_trades": total_trades,
            "total_volume": total_volume,
        }
    
    def reset_daily_stats(self) -> None:
        """Reset daily statistics for all accounts."""
        for state in self._states.values():
            state.reset_daily_stats()
        logger.info("Reset daily statistics for all accounts")
    
    async def add_account(self, account: AccountConfig) -> bool:
        """
        Add a new account to the manager.
        
        Args:
            account: Account configuration
            
        Returns:
            True if added successfully
        """
        try:
            self.registry.add_account(account)
            await self._initialize_account(account)
            return True
        except Exception as e:
            logger.error(f"Failed to add account '{account.name}': {e}")
            return False
    
    async def remove_account(self, account_name: str) -> bool:
        """
        Remove an account from the manager.
        
        Args:
            account_name: Name of account to remove
            
        Returns:
            True if removed successfully
        """
        async with self._lock:
            state = self._states.pop(account_name, None)
            
            if state and state.client:
                await state.client.close()
            
            self.registry.remove_account(account_name)
            logger.info(f"Removed account '{account_name}'")
            return True
    
    def get_account_status_report(self) -> List[Dict[str, Any]]:
        """
        Get a detailed status report for all accounts.
        
        Returns:
            List of account status dictionaries
        """
        report = []
        
        for name, state in self._states.items():
            account = self.registry.get_account(name)
            
            report.append({
                "name": name,
                "status": account.status.value if account else "unknown",
                "balance": state.balance,
                "available_balance": state.available_balance,
                "positions": len(state.positions),
                "open_orders": state.open_orders,
                "total_trades": state.total_trades,
                "daily_trades": state.daily_trades,
                "total_volume": state.total_volume,
                "daily_volume": state.daily_volume,
                "consecutive_errors": state.consecutive_errors,
                "last_error": state.last_error,
                "last_used": state.last_used.isoformat() if state.last_used else None,
                "is_healthy": state.is_healthy(self.max_consecutive_errors),
            })
        
        return report
