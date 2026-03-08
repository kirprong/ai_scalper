"""
Vault Module - Secure .env encryption with AES-256-GCM

Provides secure storage and retrieval of sensitive environment variables
with memory-only key loading and log sanitization.
"""

from .vault import Vault
from .encryption import encrypt_data, decrypt_data
from .key_manager import KeyManager

__all__ = ['Vault', 'encrypt_data', 'decrypt_data', 'KeyManager']
