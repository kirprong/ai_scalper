"""
Vault - Secure .env Encryption

Provides secure storage and retrieval of environment variables
with AES-256-GCM encryption and memory-only key loading.
"""

import os
import base64
from typing import Dict, Optional
from pathlib import Path
import logging

from .encryption import encrypt_data, decrypt_data
from .key_manager import KeyManager


# Vault file format
VAULT_HEADER = "VAULT_V1"
VAULT_MAGIC = f"{VAULT_HEADER}\n"


class Vault:
    """
    Secure vault for environment variables.
    
    Features:
    - AES-256-GCM encryption
    - Memory-only key storage
    - Log sanitization (no key leakage)
    - .env.vault file format
    """
    
    def __init__(self, vault_path: Optional[str] = None):
        """
        Initialize Vault.
        
        Args:
            vault_path: Path to .env.vault file (default: .env.vault in cwd)
        """
        self.vault_path = Path(vault_path or ".env.vault")
        self.key_manager = KeyManager()
        self._env_vars: Dict[str, str] = {}
        self._loaded = False
        
        # Configure logging with sanitization
        self._setup_logging()
        
    def _setup_logging(self):
        """Setup logging with sanitization to prevent key leakage."""
        self.logger = logging.getLogger('vault')
        
        # Custom filter to sanitize sensitive data
        class SanitizeFilter(logging.Filter):
            def filter(self, record):
                # Remove any potential key patterns from logs
                msg = record.getMessage()
                # Don't log anything that looks like a key
                if any(x in msg.lower() for x in ['key=', 'password=', 'secret=', 'token=']):
                    record.msg = "[SANITIZED]"
                    record.args = ()
                return True
        
        self.logger.addFilter(SanitizeFilter())
    
    def encrypt_env_file(self, env_path: str, password: str) -> None:
        """
        Encrypt .env file to .env.vault format.
        
        Args:
            env_path: Path to .env file
            password: Password for encryption
            
        Raises:
            FileNotFoundError: If .env file doesn't exist
        """
        env_path = Path(env_path)
        
        if not env_path.exists():
            raise FileNotFoundError(f"Environment file not found: {env_path}")
        
        # Read .env file
        with open(env_path, 'r') as f:
            env_content = f.read()
        
        # Derive key from password
        key = self.key_manager.derive_key(password)
        
        # Encrypt content
        nonce, ciphertext = encrypt_data(env_content.encode('utf-8'), key)
        
        # Write vault file
        with open(self.vault_path, 'w') as f:
            f.write(VAULT_MAGIC)
            f.write(base64.b64encode(self.key_manager.salt).decode('utf-8') + '\n')
            f.write(base64.b64encode(nonce).decode('utf-8') + '\n')
            f.write(base64.b64encode(ciphertext).decode('utf-8') + '\n')
        
        self.logger.info(f"Encrypted {env_path} to {self.vault_path}")
        
        # Clear key from memory
        self.key_manager.clear_key()
    
    def load(self, password: str) -> Dict[str, str]:
        """
        Load and decrypt .env.vault to memory.
        
        Args:
            password: Password for decryption
            
        Returns:
            Dictionary of environment variables
            
        Raises:
            FileNotFoundError: If vault file doesn't exist
            ValueError: If vault format is invalid
            cryptography.exceptions.InvalidTag: If password is wrong
        """
        if not self.vault_path.exists():
            raise FileNotFoundError(f"Vault file not found: {self.vault_path}")
        
        # Read vault file
        with open(self.vault_path, 'r') as f:
            lines = f.read().strip().split('\n')
        
        # Validate format
        if len(lines) < 4:
            raise ValueError("Invalid vault file format")
        
        if lines[0] != VAULT_HEADER:
            raise ValueError(f"Invalid vault header: {lines[0]}")
        
        # Parse vault data
        salt = base64.b64decode(lines[1])
        nonce = base64.b64decode(lines[2])
        ciphertext = base64.b64decode(lines[3])
        
        # Derive key from password and salt
        self.key_manager = KeyManager(custom_salt=salt)
        key = self.key_manager.derive_key(password)
        
        # Decrypt content
        plaintext = decrypt_data(nonce, ciphertext, key)
        
        # Parse environment variables
        env_content = plaintext.decode('utf-8')
        self._env_vars = self._parse_env_content(env_content)
        
        # Mark as loaded
        self._loaded = True
        
        # Clear key from memory after loading
        self.key_manager.clear_key()
        
        self.logger.info(f"Loaded {len(self._env_vars)} environment variables from vault")
        
        return self._env_vars
    
    def _parse_env_content(self, content: str) -> Dict[str, str]:
        """
        Parse .env file content to dictionary.
        
        Args:
            content: .env file content
            
        Returns:
            Dictionary of environment variables
        """
        env_vars = {}
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                env_vars[key] = value
        
        return env_vars
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get environment variable from memory.
        
        Args:
            key: Variable name
            default: Default value if not found
            
        Returns:
            Variable value or default
        """
        return self._env_vars.get(key, default)
    
    def get_all(self) -> Dict[str, str]:
        """
        Get all environment variables from memory.
        
        Returns:
            Dictionary of all variables
        """
        return self._env_vars.copy()
    
    def set_env(self) -> None:
        """
        Set loaded variables to os.environ.
        
        Raises:
            RuntimeError: If vault not loaded
        """
        if not self._loaded:
            raise RuntimeError("Vault not loaded. Call load() first.")
        
        for key, value in self._env_vars.items():
            os.environ[key] = value
        
        self.logger.info(f"Set {len(self._env_vars)} environment variables")
    
    def is_loaded(self) -> bool:
        """Check if vault is loaded."""
        return self._loaded
    
    def clear(self) -> None:
        """Clear all variables from memory."""
        self._env_vars.clear()
        self._loaded = False
        self.key_manager.clear_key()
        self.logger.info("Cleared vault from memory")
