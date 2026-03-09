"""
Configuration module for the AI Lead Scalper.

This module provides configuration management including:
- Multi-account configuration
- Environment-based settings
- Secure credential loading
"""

from .accounts import (
    AccountConfig,
    AccountRegistry,
    AccountStatus,
    load_accounts_from_env,
    load_accounts_from_file,
    load_accounts_from_vault,
)

__all__ = [
    "AccountConfig",
    "AccountRegistry",
    "AccountStatus",
    "load_accounts_from_env",
    "load_accounts_from_file",
    "load_accounts_from_vault",
]
