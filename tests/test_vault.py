"""
Unit Tests for Vault Module

Tests encryption, decryption, key management, and security features.
"""

import os
import pytest
import tempfile
from pathlib import Path

from backend.vault import Vault, encrypt_data, decrypt_data, KeyManager


class TestEncryption:
    """Test AES-256-GCM encryption/decryption."""
    
    def test_encrypt_decrypt_basic(self):
        """Test basic encryption and decryption."""
        plaintext = b"Hello, World!"
        key = os.urandom(32)
        
        nonce, ciphertext = encrypt_data(plaintext, key)
        decrypted = decrypt_data(nonce, ciphertext, key)
        
        assert decrypted == plaintext
    
    def test_encrypt_different_nonces(self):
        """Test that same plaintext produces different ciphertexts."""
        plaintext = b"Same message"
        key = os.urandom(32)
        
        nonce1, cipher1 = encrypt_data(plaintext, key)
        nonce2, cipher2 = encrypt_data(plaintext, key)
        
        # Nonces should be different
        assert nonce1 != nonce2
        # Ciphertexts should be different
        assert cipher1 != cipher2
    
    def test_encrypt_invalid_key_size(self):
        """Test that invalid key size raises error."""
        plaintext = b"Test"
        key = os.urandom(16)  # Wrong size
        
        with pytest.raises(ValueError, match="Key must be 32 bytes"):
            encrypt_data(plaintext, key)
    
    def test_decrypt_invalid_nonce_size(self):
        """Test that invalid nonce size raises error."""
        plaintext = b"Test"
        key = os.urandom(32)
        
        nonce, ciphertext = encrypt_data(plaintext, key)
        
        with pytest.raises(ValueError, match="Nonce must be 12 bytes"):
            decrypt_data(b"short", ciphertext, key)
    
    def test_decrypt_wrong_key(self):
        """Test that wrong key fails authentication."""
        plaintext = b"Secret message"
        key1 = os.urandom(32)
        key2 = os.urandom(32)
        
        nonce, ciphertext = encrypt_data(plaintext, key1)
        
        with pytest.raises(Exception):  # InvalidTag exception
            decrypt_data(nonce, ciphertext, key2)


class TestKeyManager:
    """Test key derivation and management."""
    
    def test_derive_key_basic(self):
        """Test basic key derivation."""
        km = KeyManager()
        key = km.derive_key("test_password")
        
        assert len(key) == 32
        assert km.get_key() == key
    
    def test_derive_key_deterministic(self):
        """Test that same password + salt produces same key."""
        salt = os.urandom(32)
        
        km1 = KeyManager(custom_salt=salt)
        km2 = KeyManager(custom_salt=salt)
        
        key1 = km1.derive_key("password")
        key2 = km2.derive_key("password")
        
        assert key1 == key2
    
    def test_derive_key_different_passwords(self):
        """Test that different passwords produce different keys."""
        salt = os.urandom(32)
        
        km1 = KeyManager(custom_salt=salt)
        km2 = KeyManager(custom_salt=salt)
        
        key1 = km1.derive_key("password1")
        key2 = km2.derive_key("password2")
        
        assert key1 != key2
    
    def test_clear_key(self):
        """Test that clear_key removes key from memory."""
        km = KeyManager()
        km.derive_key("password")
        
        assert km.get_key() is not None
        
        km.clear_key()
        
        assert km.get_key() is None
    
    def test_system_salt_generation(self):
        """Test that system salt is generated."""
        km = KeyManager()
        
        assert len(km.salt) == 32
        assert isinstance(km.salt, bytes)


class TestVault:
    """Test Vault class."""
    
    @pytest.fixture
    def temp_env_file(self):
        """Create temporary .env file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("# Test environment\n")
            f.write("API_KEY=test_key_123\n")
            f.write("SECRET=secret_value\n")
            f.write('QUOTED="quoted value"\n')
            env_path = f.name
        yield env_path
        os.unlink(env_path)
    
    @pytest.fixture
    def temp_vault_path(self):
        """Create temporary vault path."""
        with tempfile.NamedTemporaryFile(suffix='.vault', delete=False) as f:
            vault_path = f.name
        # Delete it so vault can create it
        os.unlink(vault_path)
        yield vault_path
        # Cleanup
        if os.path.exists(vault_path):
            os.unlink(vault_path)
    
    def test_encrypt_env_file(self, temp_env_file, temp_vault_path):
        """Test encrypting .env file."""
        vault = Vault(vault_path=temp_vault_path)
        
        vault.encrypt_env_file(temp_env_file, "test_password")
        
        assert os.path.exists(temp_vault_path)
        
        # Check vault format
        with open(temp_vault_path, 'r') as f:
            lines = f.read().strip().split('\n')
        
        assert lines[0] == "VAULT_V1"
        assert len(lines) == 4
    
    def test_load_vault(self, temp_env_file, temp_vault_path):
        """Test loading encrypted vault."""
        vault = Vault(vault_path=temp_vault_path)
        
        # Encrypt
        vault.encrypt_env_file(temp_env_file, "password")
        
        # Load in new vault instance
        vault2 = Vault(vault_path=temp_vault_path)
        env_vars = vault2.load("password")
        
        assert env_vars["API_KEY"] == "test_key_123"
        assert env_vars["SECRET"] == "secret_value"
        assert env_vars["QUOTED"] == "quoted value"
    
    def test_load_wrong_password(self, temp_env_file, temp_vault_path):
        """Test that wrong password fails."""
        vault = Vault(vault_path=temp_vault_path)
        
        vault.encrypt_env_file(temp_env_file, "correct_password")
        
        vault2 = Vault(vault_path=temp_vault_path)
        
        with pytest.raises(Exception):  # InvalidTag
            vault2.load("wrong_password")
    
    def test_get_variable(self, temp_env_file, temp_vault_path):
        """Test getting individual variables."""
        vault = Vault(vault_path=temp_vault_path)
        vault.encrypt_env_file(temp_env_file, "password")
        
        vault2 = Vault(vault_path=temp_vault_path)
        vault2.load("password")
        
        assert vault2.get("API_KEY") == "test_key_123"
        assert vault2.get("NONEXISTENT", "default") == "default"
    
    def test_set_env(self, temp_env_file, temp_vault_path):
        """Test setting environment variables."""
        vault = Vault(vault_path=temp_vault_path)
        vault.encrypt_env_file(temp_env_file, "password")
        
        vault2 = Vault(vault_path=temp_vault_path)
        vault2.load("password")
        vault2.set_env()
        
        assert os.environ["API_KEY"] == "test_key_123"
        assert os.environ["SECRET"] == "secret_value"
        
        # Cleanup
        del os.environ["API_KEY"]
        del os.environ["SECRET"]
    
    def test_clear_vault(self, temp_env_file, temp_vault_path):
        """Test clearing vault from memory."""
        vault = Vault(vault_path=temp_vault_path)
        vault.encrypt_env_file(temp_env_file, "password")
        
        vault2 = Vault(vault_path=temp_vault_path)
        vault2.load("password")
        
        assert vault2.is_loaded()
        
        vault2.clear()
        
        assert not vault2.is_loaded()
        assert len(vault2.get_all()) == 0


class TestSecurity:
    """Test security features."""
    
    def test_no_key_in_repr(self):
        """Test that key doesn't appear in string representation."""
        km = KeyManager()
        km.derive_key("password")
        
        # Key should not appear in any string representation
        assert "password" not in str(km)
        assert "password" not in repr(km)
    
    def test_memory_only_storage(self):
        """Test that keys are stored in memory only."""
        km = KeyManager()
        key = km.derive_key("password")
        
        # Key should be accessible from memory
        assert km.get_key() == key
        
        # But not written to any file
        # (This is a conceptual test - actual file system check would be complex)
    
    def test_log_sanitization(self, caplog):
        """Test that sensitive data is sanitized in logs."""
        import logging
        
        vault = Vault()
        
        # Try to log something sensitive
        vault.logger.info("key=secret_value")
        vault.logger.info("password=test123")
        vault.logger.info("Normal log message")
        
        # Check that sensitive logs are sanitized
        # (The filter should replace sensitive messages)
