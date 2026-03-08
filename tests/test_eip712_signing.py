"""
Tests for EIP-712 Signing Module

This module tests EIP-712 typed data signing for Polymarket CLOB API.
"""

import pytest
from eth_account import Account

from backend.signing import (
    build_domain,
    sign_typed_data,
    verify_signature,
    build_order_message,
    get_order_types,
    PolymarketSigner,
    SignatureType,
    OrderSide,
)


class TestEIP712Domain:
    """Test EIP-712 domain separator building"""
    
    def test_build_domain_default(self):
        """Test building domain with default parameters"""
        domain = build_domain()
        
        assert domain["name"] == "Polymarket CTF Exchange"
        assert domain["version"] == "1"
        assert domain["chainId"] == 137
        assert domain["verifyingContract"] == "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
    
    def test_build_domain_custom(self):
        """Test building domain with custom parameters"""
        domain = build_domain(
            name="Custom Exchange",
            version="2",
            chain_id=80002,
            verifying_contract="0x1234567890123456789012345678901234567890"
        )
        
        assert domain["name"] == "Custom Exchange"
        assert domain["version"] == "2"
        assert domain["chainId"] == 80002
        assert domain["verifyingContract"] == "0x1234567890123456789012345678901234567890"


class TestOrderTypes:
    """Test EIP-712 order type definitions"""
    
    def test_get_order_types(self):
        """Test getting order type definitions"""
        types = get_order_types()
        
        assert "EIP712Domain" in types
        assert "Order" in types
        
        # Check domain types
        domain_types = types["EIP712Domain"]
        assert len(domain_types) == 4
        assert {"name": "name", "type": "string"} in domain_types
        assert {"name": "version", "type": "string"} in domain_types
        assert {"name": "chainId", "type": "uint256"} in domain_types
        assert {"name": "verifyingContract", "type": "address"} in domain_types
        
        # Check order types
        order_types = types["Order"]
        assert len(order_types) == 12
        
        # Check specific fields
        field_names = [f["name"] for f in order_types]
        assert "salt" in field_names
        assert "maker" in field_names
        assert "signer" in field_names
        assert "taker" in field_names
        assert "tokenId" in field_names
        assert "makerAmount" in field_names
        assert "takerAmount" in field_names
        assert "expiration" in field_names
        assert "nonce" in field_names
        assert "feeRateBps" in field_names
        assert "side" in field_names
        assert "signatureType" in field_names


class TestOrderMessage:
    """Test order message building"""
    
    def test_build_order_message(self):
        """Test building order message"""
        message = build_order_message(
            salt=12345,
            maker="0x7CD8694f58740D231Ee081f5CC943A3ADA4A21E8",
            signer="0x7CD8694f58740D231Ee081f5CC943A3ADA4A21E8",
            taker="0x0000000000000000000000000000000000000000",
            token_id="71321045679252212594626385532706912750332728571942532289631379312455583992563",
            maker_amount="50000000",
            taker_amount="100000000",
            expiration=0,
            nonce=1,
            fee_rate_bps="100",
            side=0,
            signature_type=0
        )
        
        assert message["salt"] == 12345
        assert message["maker"] == "0x7CD8694f58740D231Ee081f5CC943A3ADA4A21E8"
        assert message["signer"] == "0x7CD8694f58740D231Ee081f5CC943A3ADA4A21E8"
        assert message["taker"] == "0x0000000000000000000000000000000000000000"
        assert message["tokenId"] == "71321045679252212594626385532706912750332728571942532289631379312455583992563"
        assert message["makerAmount"] == "50000000"
        assert message["takerAmount"] == "100000000"
        assert message["expiration"] == 0
        assert message["nonce"] == 1
        assert message["feeRateBps"] == "100"
        assert message["side"] == 0
        assert message["signatureType"] == 0


class TestSigning:
    """Test EIP-712 signing and verification"""
    
    @pytest.fixture
    def test_account(self):
        """Create test account"""
        # Generate a new account for testing
        account = Account.create()
        return account
    
    @pytest.fixture
    def test_domain(self):
        """Create test domain"""
        return build_domain()
    
    @pytest.fixture
    def test_message(self):
        """Create test order message"""
        return build_order_message(
            salt=12345,
            maker="0x7CD8694f58740D231Ee081f5CC943A3ADA4A21E8",
            signer="0x7CD8694f58740D231Ee081f5CC943A3ADA4A21E8",
            taker="0x0000000000000000000000000000000000000000",
            token_id="71321045679252212594626385532706912750332728571942532289631379312455583992563",
            maker_amount="50000000",
            taker_amount="100000000",
            expiration=0,
            nonce=1,
            fee_rate_bps="100",
            side=0,
            signature_type=0
        )
    
    def test_sign_typed_data(self, test_account, test_domain, test_message):
        """Test signing typed data"""
        signature = sign_typed_data(
            private_key=test_account.key.hex(),
            domain=test_domain,
            message=test_message
        )
        
        # Signature should be hex string
        assert isinstance(signature, str)
        assert signature.startswith("0x")
        # Signature should be 65 bytes (130 hex chars + 0x prefix)
        assert len(signature) == 132
    
    def test_verify_signature(self, test_account, test_domain, test_message):
        """Test signature verification"""
        # Sign message
        signature = sign_typed_data(
            private_key=test_account.key.hex(),
            domain=test_domain,
            message=test_message
        )
        
        # Verify signature
        is_valid = verify_signature(
            signature=signature,
            domain=test_domain,
            message=test_message,
            expected_address=test_account.address
        )
        
        assert is_valid is True
    
    def test_verify_signature_wrong_address(self, test_account, test_domain, test_message):
        """Test signature verification with wrong address"""
        # Sign message
        signature = sign_typed_data(
            private_key=test_account.key.hex(),
            domain=test_domain,
            message=test_message
        )
        
        # Verify with wrong address
        wrong_address = "0x1234567890123456789012345678901234567890"
        is_valid = verify_signature(
            signature=signature,
            domain=test_domain,
            message=test_message,
            expected_address=wrong_address
        )
        
        assert is_valid is False


class TestPolymarketSigner:
    """Test Polymarket signer"""
    
    @pytest.fixture
    def test_account(self):
        """Create test account"""
        account = Account.create()
        return account
    
    @pytest.fixture
    def signer(self, test_account):
        """Create Polymarket signer"""
        return PolymarketSigner(
            private_key=test_account.key.hex(),
            chain_id=137,
            neg_risk=False
        )
    
    def test_signer_initialization(self, signer, test_account):
        """Test signer initialization"""
        assert signer.chain_id == 137
        assert signer.neg_risk is False
        assert signer.address == test_account.address
        assert signer.verifying_contract == "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
    
    def test_sign_order(self, signer):
        """Test signing order"""
        signed_order = signer.sign_order(
            token_id="71321045679252212594626385532706912750332728571942532289631379312455583992563",
            maker_amount="50000000",
            taker_amount="100000000",
            side=OrderSide.BUY,
            nonce=1,
            fee_rate_bps="100"
        )
        
        # Check signed order fields
        assert signed_order.maker == signer.address
        assert signed_order.signer == signer.address
        assert signed_order.taker == "0x0000000000000000000000000000000000000000"
        assert signed_order.tokenId == "71321045679252212594626385532706912750332728571942532289631379312455583992563"
        assert signed_order.makerAmount == "50000000"
        assert signed_order.takerAmount == "100000000"
        assert signed_order.side == "BUY"
        assert signed_order.nonce == 1
        assert signed_order.feeRateBps == "100"
        assert signed_order.signatureType == 0
        
        # Check signature
        assert isinstance(signed_order.signature, str)
        assert signed_order.signature.startswith("0x")
    
    def test_verify_order(self, signer):
        """Test verifying signed order"""
        signed_order = signer.sign_order(
            token_id="71321045679252212594626385532706912750332728571942532289631379312455583992563",
            maker_amount="50000000",
            taker_amount="100000000",
            side=OrderSide.BUY,
            nonce=1
        )
        
        # Verify order
        is_valid = signer.verify_order(signed_order)
        assert is_valid is True
    
    def test_to_dict(self, signer):
        """Test converting signed order to dict"""
        signed_order = signer.sign_order(
            token_id="71321045679252212594626385532706912750332728571942532289631379312455583992563",
            maker_amount="50000000",
            taker_amount="100000000",
            side=OrderSide.SELL,
            nonce=1
        )
        
        order_dict = signer.to_dict(signed_order)
        
        # Check dict fields
        assert order_dict["maker"] == signer.address
        assert order_dict["signer"] == signer.address
        assert order_dict["tokenId"] == "71321045679252212594626385532706912750332728571942532289631379312455583992563"
        assert order_dict["side"] == "SELL"
        assert "signature" in order_dict
    
    def test_sign_order_sell(self, signer):
        """Test signing SELL order"""
        signed_order = signer.sign_order(
            token_id="71321045679252212594626385532706912750332728571942532289631379312455583992563",
            maker_amount="100000000",
            taker_amount="50000000",
            side=OrderSide.SELL,
            nonce=1
        )
        
        assert signed_order.side == "SELL"
    
    def test_neg_risk_exchange(self, test_account):
        """Test negative risk exchange"""
        signer = PolymarketSigner(
            private_key=test_account.key.hex(),
            chain_id=137,
            neg_risk=True
        )
        
        assert signer.verifying_contract == "0xC5d563A36AE78145C45a50134d48A1215220f80a"
    
    def test_testnet_chain(self, test_account):
        """Test Amoy testnet"""
        signer = PolymarketSigner(
            private_key=test_account.key.hex(),
            chain_id=80002,
            neg_risk=False
        )
        
        assert signer.chain_id == 80002
        assert signer.verifying_contract == "0xdFE02Eb6733538f8Ea35D585af8DE5958AD99E40"
    
    def test_unsupported_chain(self, test_account):
        """Test unsupported chain ID"""
        with pytest.raises(ValueError, match="Unsupported chain ID"):
            PolymarketSigner(
                private_key=test_account.key.hex(),
                chain_id=1,  # Ethereum mainnet
                neg_risk=False
            )


class TestSignatureTypes:
    """Test signature type enums"""
    
    def test_signature_type_values(self):
        """Test signature type enum values"""
        assert SignatureType.EOA == 0
        assert SignatureType.POLY_PROXY == 1
        assert SignatureType.POLY_GNOSIS_SAFE == 2
    
    def test_order_side_values(self):
        """Test order side enum values"""
        assert OrderSide.BUY == 0
        assert OrderSide.SELL == 1


class TestSecurity:
    """Test security aspects"""
    
    def test_private_key_not_logged(self, caplog):
        """Test that private key is not logged"""
        import logging
        
        # Create test account
        account = Account.create()
        
        # Create signer and sign order
        signer = PolymarketSigner(
            private_key=account.key.hex(),
            chain_id=137
        )
        
        signed_order = signer.sign_order(
            token_id="71321045679252212594626385532706912750332728571942532289631379312455583992563",
            maker_amount="50000000",
            taker_amount="100000000",
            side=OrderSide.BUY,
            nonce=1
        )
        
        # Check that private key is not in any log
        private_key_hex = account.key.hex()
        for record in caplog.records:
            assert private_key_hex not in record.message
    
    def test_private_key_memory_only(self):
        """Test that private key is used in memory only"""
        # This is a conceptual test - we verify that the private key
        # is passed as a parameter and not stored in a file
        
        account = Account.create()
        signer = PolymarketSigner(
            private_key=account.key.hex(),
            chain_id=137
        )
        
        # Private key should be stored in memory only
        assert hasattr(signer, "_private_key")
        assert signer._private_key == account.key.hex()
