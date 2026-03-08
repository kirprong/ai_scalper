"""
System Key Manager

Derives encryption keys from machine-specific identifiers using PBKDF2.
Ensures keys are unique per machine and never stored on disk.
"""

import os
import hashlib
import platform
import uuid
from typing import Optional
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend


# Constants
KEY_SIZE = 32        # 256 bits
SALT_SIZE = 32       # 256 bits
ITERATIONS = 100000  # PBKDF2 iterations


class KeyManager:
    """
    Manages system-specific encryption key derivation.
    
    Keys are derived from machine identifiers and never stored on disk.
    All sensitive data is kept in memory only.
    """
    
    def __init__(self, custom_salt: Optional[bytes] = None):
        """
        Initialize KeyManager.
        
        Args:
            custom_salt: Optional custom salt (for testing)
        """
        self._salt = custom_salt or self._generate_system_salt()
        self._key: Optional[bytes] = None
        
    def _generate_system_salt(self) -> bytes:
        """
        Generate salt from machine-specific identifiers.
        
        Uses platform and hardware info to create unique salt per machine.
        
        Returns:
            32-byte salt
        """
        # Collect machine identifiers
        identifiers = [
            platform.node(),           # Machine hostname
            platform.system(),         # OS name
            platform.machine(),        # Machine type
            str(uuid.getnode()),       # MAC address
        ]
        
        # Combine identifiers
        combined = '|'.join(identifiers).encode('utf-8')
        
        # Generate salt using SHA-256
        salt = hashlib.sha256(combined).digest()
        
        return salt
    
    def derive_key(self, password: str) -> bytes:
        """
        Derive encryption key from password using PBKDF2.
        
        Args:
            password: Password string
            
        Returns:
            32-byte encryption key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=self._salt,
            iterations=ITERATIONS,
            backend=default_backend()
        )
        
        key = kdf.derive(password.encode('utf-8'))
        
        # Store in memory only (never write to disk)
        self._key = key
        
        return key
    
    def get_key(self) -> Optional[bytes]:
        """
        Get current key from memory.
        
        Returns:
            Key bytes or None if not derived
        """
        return self._key
    
    def clear_key(self) -> None:
        """
        Clear key from memory for security.
        """
        if self._key:
            # Overwrite memory before clearing
            self._key = bytes(len(self._key))
            self._key = None
    
    @property
    def salt(self) -> bytes:
        """
        Get salt (safe to store, not secret).
        
        Returns:
            32-byte salt
        """
        return self._salt
    
    @staticmethod
    def generate_random_salt() -> bytes:
        """
        Generate cryptographically random salt.
        
        Returns:
            32-byte random salt
        """
        return os.urandom(SALT_SIZE)
