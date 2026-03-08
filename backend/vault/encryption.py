"""
AES-256-GCM Encryption Module

Implements secure encryption/decryption using AES-256 in Galois/Counter Mode.
Provides authenticated encryption with associated data (AEAD).
"""

import os
import base64
from typing import Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend


# Constants
NONCE_SIZE = 12  # 96 bits for GCM
KEY_SIZE = 32    # 256 bits for AES-256


def encrypt_data(plaintext: bytes, key: bytes) -> Tuple[bytes, bytes]:
    """
    Encrypt data using AES-256-GCM.
    
    Args:
        plaintext: Data to encrypt
        key: 32-byte encryption key
        
    Returns:
        Tuple of (nonce, ciphertext) where nonce is 12 bytes
        
    Raises:
        ValueError: If key is not 32 bytes
    """
    if len(key) != KEY_SIZE:
        raise ValueError(f"Key must be {KEY_SIZE} bytes, got {len(key)}")
    
    # Generate random nonce
    nonce = os.urandom(NONCE_SIZE)
    
    # Create AES-GCM cipher
    aesgcm = AESGCM(key)
    
    # Encrypt (returns ciphertext with authentication tag)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    return nonce, ciphertext


def decrypt_data(nonce: bytes, ciphertext: bytes, key: bytes) -> bytes:
    """
    Decrypt data using AES-256-GCM.
    
    Args:
        nonce: 12-byte nonce used during encryption
        ciphertext: Encrypted data with authentication tag
        key: 32-byte encryption key
        
    Returns:
        Decrypted plaintext
        
    Raises:
        ValueError: If nonce or key size is incorrect
        cryptography.exceptions.InvalidTag: If authentication fails
    """
    if len(nonce) != NONCE_SIZE:
        raise ValueError(f"Nonce must be {NONCE_SIZE} bytes, got {len(nonce)}")
    
    if len(key) != KEY_SIZE:
        raise ValueError(f"Key must be {KEY_SIZE} bytes, got {len(key)}")
    
    # Create AES-GCM cipher
    aesgcm = AESGCM(key)
    
    # Decrypt (verifies authentication tag automatically)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    
    return plaintext


def encode_vault_data(nonce: bytes, ciphertext: bytes) -> str:
    """
    Encode encrypted data to base64 string for storage.
    
    Args:
        nonce: 12-byte nonce
        ciphertext: Encrypted data
        
    Returns:
        Base64 encoded string
    """
    return base64.b64encode(nonce + ciphertext).decode('utf-8')


def decode_vault_data(encoded: str) -> Tuple[bytes, bytes]:
    """
    Decode base64 string to nonce and ciphertext.
    
    Args:
        encoded: Base64 encoded string
        
    Returns:
        Tuple of (nonce, ciphertext)
        
    Raises:
        ValueError: If encoded data is too short
    """
    data = base64.b64decode(encoded)
    
    if len(data) < NONCE_SIZE:
        raise ValueError(f"Encoded data too short: {len(data)} bytes")
    
    nonce = data[:NONCE_SIZE]
    ciphertext = data[NONCE_SIZE:]
    
    return nonce, ciphertext
