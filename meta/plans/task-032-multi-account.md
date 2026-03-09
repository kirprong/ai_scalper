# TASK-032: Multi-account Support

## Overview

This task implements multi-account support for the Polymarket AI Lead-Lag Scalper, allowing the system to manage multiple Polymarket accounts simultaneously with automatic rotation and failover capabilities.

## Implementation Date

2026-03-09

## Components

### 1. Account Configuration System (`backend/config/accounts.py`)

**Purpose**: Centralized configuration management for multiple Polymarket accounts.

**Key Classes**:
- `AccountConfig`: Dataclass for individual account configuration
  - Fields: name, api_key, api_secret, wallet_address, private_key, priority, weight, chain_id, status
  - Validation for required fields and wallet address format
  - Methods: `is_active()`, `to_dict()`

- `AccountRegistry`: Registry for managing multiple account configurations
  - Methods: `add_account()`, `remove_account()`, `get_account()`, `get_all_accounts()`
  - Priority and weight-based account selection
  - Status tracking (ACTIVE, INACTIVE, DISABLED, ERROR)

**Loading Functions**:
- `load_accounts_from_env()`: Load from environment variables
- `load_accounts_from_file()`: Load from JSON configuration file
- `load_accounts_from_vault()`: Load from vault-secured variables

**Environment Variable Format**:
```bash
POLYMARKET_ACCOUNT_1_NAME=account1
POLYMARKET_ACCOUNT_1_API_KEY=xxx
POLYMARKET_ACCOUNT_1_API_SECRET=xxx
POLYMARKET_ACCOUNT_1_WALLET_ADDRESS=0x...
POLYMARKET_ACCOUNT_1_PRIVATE_KEY=0x...
POLYMARKET_ACCOUNT_1_PRIORITY=1
POLYMARKET_ACCOUNT_1_WEIGHT=1.0
```

### 2. Account Manager (`backend/trading/account_manager.py`)

**Purpose**: Runtime management of multiple account connections with rotation and failover.

**Key Classes**:
- `AccountState`: Runtime state for each account
  - Tracks: balance, positions, trades, errors, client/signer instances
  - Methods: `is_healthy()`, `record_success()`, `record_error()`

- `AccountManager`: Main manager class
  - Rotation strategies: ROUND_ROBIN, WEIGHTED_RANDOM, PRIORITY, LEAST_USED
  - Methods:
    - `initialize()`: Initialize all account connections
    - `get_next_account()`: Get next account based on rotation strategy
    - `execute_with_failover()`: Execute operation with automatic failover
    - `get_aggregate_stats()`: Get combined statistics
    - `get_account_status_report()`: Detailed status for all accounts

**Rotation Strategies**:
1. **Round Robin**: Cycles through accounts sequentially
2. **Weighted Random**: Random selection based on account weights
3. **Priority**: Always selects highest priority available account
4. **Least Used**: Selects the least recently used account

**Failover Behavior**:
- Tracks consecutive errors per account
- Disables accounts after `max_consecutive_errors` (default: 3)
- Automatically retries with next available account
- Configurable error cooldown period

### 3. Polymarket Client Updates (`backend/api/polymarket_client.py`)

**Changes**:
- Added `account_id` parameter to constructor
- Added `address` property for easy access to wallet address
- Added `get_account_id()` method

## Usage Examples

### Basic Setup

```python
from backend.config.accounts import load_accounts_from_vault
from backend.trading.account_manager import AccountManager, RotationStrategy
from backend.vault import Vault

# Load accounts from vault
vault = Vault()
vault_vars = vault.load(password="your_password")
registry = load_accounts_from_vault(vault_vars)

# Create manager
manager = AccountManager(
    registry,
    rotation_strategy=RotationStrategy.WEIGHTED_RANDOM
)

# Initialize
await manager.initialize()
```

### Execute with Failover

```python
# Execute operation with automatic failover
result, account_name = await manager.execute_with_failover(
    lambda client: client.get_markets()
)
```

### Get Account for Manual Operations

```python
# Get next account
account = await manager.get_next_account()
client = manager.get_client(account.name)

# Use client directly
markets = await client.get_markets()
```

### Status Monitoring

```python
# Get aggregate stats
stats = manager.get_aggregate_stats()
print(f"Total balance: {stats['total_balance']}")
print(f"Active accounts: {stats['active_accounts']}")

# Get detailed report
report = manager.get_account_status_report()
for account in report:
    print(f"{account['name']}: {account['status']}")
```

## Testing

Comprehensive tests are located at `tests/test_account_manager.py`:

- **AccountConfig Tests**: Validation, serialization
- **AccountRegistry Tests**: CRUD operations, priority/weight sorting
- **Load Functions Tests**: Environment, file, vault loading
- **AccountState Tests**: Health tracking, statistics
- **AccountManager Tests**: Rotation strategies, failover, statistics
- **Integration Tests**: Full workflow testing

Run tests:
```bash
pytest tests/test_account_manager.py -v
```

## Configuration

### Manager Options

| Option | Default | Description |
|--------|---------|-------------|
| `rotation_strategy` | WEIGHTED_RANDOM | Strategy for account selection |
| `max_consecutive_errors` | 3 | Errors before disabling account |
| `error_cooldown_seconds` | 60.0 | Cooldown after errors |
| `balance_refresh_interval` | 300.0 | Background balance refresh interval |

### Account Options

| Option | Required | Description |
|--------|----------|-------------|
| `name` | Yes | Unique account identifier |
| `api_key` | Yes | Polymarket API key |
| `api_secret` | Yes | Polymarket API secret |
| `wallet_address` | Yes | Ethereum wallet address |
| `private_key` | No* | Private key for signing |
| `priority` | No (1) | Priority level (higher = more priority) |
| `weight` | No (1.0) | Weight for load balancing |
| `chain_id` | No (137) | Chain ID (137 = Polygon Mainnet) |
| `max_position_size` | No | Maximum position size |
| `daily_limit` | No | Daily trading limit |

*Private key is required for active trading but can be loaded separately.

## Security Considerations

1. **Private Keys**: Never logged or transmitted, loaded from vault only
2. **API Keys**: Masked in `to_dict()` output for safe logging
3. **Memory**: Keys stored in memory only during operation
4. **Validation**: Wallet addresses validated for correct format

## Future Enhancements

1. **Balance Tracking**: Real-time balance updates from blockchain
2. **Position Tracking**: Track open positions per account
3. **Rate Limiting**: Per-account rate limit tracking
4. **Alerting**: Notifications for account errors/disabling
5. **Dynamic Rebalancing**: Adjust weights based on performance

## Files Modified/Created

| File | Action |
|------|--------|
| `backend/config/__init__.py` | Created |
| `backend/config/accounts.py` | Created |
| `backend/trading/account_manager.py` | Created |
| `backend/trading/__init__.py` | Modified |
| `backend/api/polymarket_client.py` | Modified |
| `tests/test_account_manager.py` | Created |
| `meta/plans/task-032-multi-account.md` | Created |

## Acceptance Criteria Status

- [x] System can load and manage multiple Polymarket accounts
- [x] API calls can be distributed across accounts
- [x] Per-account state tracking (balances, positions)
- [x] Graceful failover when an account fails
- [x] Unit tests for account manager
- [x] Test account rotation logic
- [x] Test failover scenarios
