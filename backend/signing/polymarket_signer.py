"""
Polymarket CLOB Order Signer

This module provides Polymarket-specific order signing functionality with
secure private key management through the vault system.
"""

import random
import time
from typing import Dict, Any, Optional
from enum import IntEnum
from dataclasses import dataclass

from .eip712 import (
    build_domain,
    build_order_message,
    sign_typed_data,
    verify_signature,
)


class SignatureType(IntEnum):
    """Polymarket signature types"""
    EOA = 0  # ECDSA EIP712 signatures signed by EOAs
    POLY_PROXY = 1  # EIP712 signatures signed by EOAs that own Polymarket Proxy wallets
    POLY_GNOSIS_SAFE = 2  # EIP712 signatures signed by EOAs that own Polymarket Gnosis safes


class OrderSide(IntEnum):
    """Order side enum"""
    BUY = 0
    SELL = 1


# Polymarket contract addresses by chain
POLYGON_CONTRACTS = {
    137: {  # Polygon Mainnet
        "exchange": "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
        "negRiskAdapter": "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",
        "negRiskExchange": "0xC5d563A36AE78145C45a50134d48A1215220f80a",
        "collateral": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "conditionalTokens": "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
    },
    80002: {  # Amoy Testnet
        "exchange": "0xdFE02Eb6733538f8Ea35D585af8DE5958AD99E40",
        "negRiskAdapter": "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",
        "negRiskExchange": "0xC5d563A36AE78145C45a50134d48A1215220f80a",
        "collateral": "0x9c4e1703476e875070ee25b56a58b008cfb8fa78",
        "conditionalTokens": "0x69308FB512518e39F9b16112fA8d994F4e2Bf8bB",
    }
}

# Zero address for taker (open order)
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


@dataclass
class SignedOrder:
    """Signed Polymarket order"""
    salt: int
    maker: str
    signer: str
    taker: str
    tokenId: str
    makerAmount: str
    takerAmount: str
    expiration: int
    nonce: int
    feeRateBps: str
    side: str  # "BUY" or "SELL"
    signatureType: int
    signature: str


class PolymarketSigner:
    """
    Polymarket CLOB order signer with secure key management
    
    This class handles EIP-712 signing of Polymarket orders using private keys
    loaded from the vault. Keys are never transmitted over the network.
    
    Security:
    - Private keys loaded from vault only
    - Keys stored in memory only during signing
    - No key transmission over network
    - No key leakage to logs
    """
    
    def __init__(
        self,
        private_key: str,
        chain_id: int = 137,
        neg_risk: bool = False
    ):
        """
        Initialize Polymarket signer
        
        Args:
            private_key: Ethereum private key (hex string) from vault
            chain_id: Chain ID (default: 137 for Polygon Mainnet)
            neg_risk: Whether to use negative risk exchange (default: False)
        """
        self._private_key = private_key
        self.chain_id = chain_id
        self.neg_risk = neg_risk
        
        # Get contract address
        contracts = POLYGON_CONTRACTS.get(chain_id)
        if not contracts:
            raise ValueError(f"Unsupported chain ID: {chain_id}")
        
        contract_key = "negRiskExchange" if neg_risk else "exchange"
        self.verifying_contract = contracts[contract_key]
        
        # Build domain separator
        self.domain = build_domain(
            chain_id=chain_id,
            verifying_contract=self.verifying_contract
        )
        
        # Derive address from private key (in memory only)
        from eth_account import Account
        self.address = Account.from_key(private_key).address
    
    def sign_order(
        self,
        token_id: str,
        maker_amount: str,
        taker_amount: str,
        side: OrderSide,
        nonce: int,
        fee_rate_bps: str = "100",
        expiration: int = 0,
        taker: str = ZERO_ADDRESS,
        signature_type: SignatureType = SignatureType.EOA
    ) -> SignedOrder:
        """
        Sign a Polymarket order
        
        Args:
            token_id: ERC1155 token ID of conditional token being traded
            maker_amount: Maximum amount maker is willing to spend
            taker_amount: Minimum amount taker must pay the maker in return
            side: Order side (BUY or SELL)
            nonce: Maker's Exchange nonce
            fee_rate_bps: Fee rate in basis points (default: "100")
            expiration: Unix expiration timestamp (default: 0 = no expiration)
            taker: Taker address (default: zero address for open order)
            signature_type: Signature type (default: EOA)
            
        Returns:
            SignedOrder object with signature
            
        Security:
            - Private key used in memory only
            - Never transmitted over network
        """
        # Generate random salt for unique order
        salt = int(random.random() * time.time() * 1000)
        
        # Build order message
        message = build_order_message(
            salt=salt,
            maker=self.address,
            signer=self.address,
            taker=taker,
            token_id=token_id,
            maker_amount=maker_amount,
            taker_amount=taker_amount,
            expiration=expiration,
            nonce=nonce,
            fee_rate_bps=fee_rate_bps,
            side=int(side),
            signature_type=int(signature_type)
        )
        
        # Sign the order
        signature = sign_typed_data(
            private_key=self._private_key,
            domain=self.domain,
            message=message
        )
        
        # Build signed order
        return SignedOrder(
            salt=salt,
            maker=self.address,
            signer=self.address,
            taker=taker,
            tokenId=token_id,
            makerAmount=maker_amount,
            takerAmount=taker_amount,
            expiration=expiration,
            nonce=nonce,
            feeRateBps=fee_rate_bps,
            side="BUY" if side == OrderSide.BUY else "SELL",
            signatureType=int(signature_type),
            signature=signature
        )
    
    def verify_order(self, signed_order: SignedOrder) -> bool:
        """
        Verify a signed order
        
        Args:
            signed_order: SignedOrder to verify
            
        Returns:
            True if signature is valid
        """
        # Build message from signed order
        message = build_order_message(
            salt=signed_order.salt,
            maker=signed_order.maker,
            signer=signed_order.signer,
            taker=signed_order.taker,
            token_id=signed_order.tokenId,
            maker_amount=signed_order.makerAmount,
            taker_amount=signed_order.takerAmount,
            expiration=signed_order.expiration,
            nonce=signed_order.nonce,
            fee_rate_bps=signed_order.feeRateBps,
            side=0 if signed_order.side == "BUY" else 1,
            signature_type=signed_order.signatureType
        )
        
        # Verify signature
        return verify_signature(
            signature=signed_order.signature,
            domain=self.domain,
            message=message,
            expected_address=self.address
        )
    
    def to_dict(self, signed_order: SignedOrder) -> Dict[str, Any]:
        """
        Convert signed order to dictionary for API submission
        
        Args:
            signed_order: SignedOrder to convert
            
        Returns:
            Dictionary representation for Polymarket API
        """
        return {
            "salt": signed_order.salt,
            "maker": signed_order.maker,
            "signer": signed_order.signer,
            "taker": signed_order.taker,
            "tokenId": signed_order.tokenId,
            "makerAmount": signed_order.makerAmount,
            "takerAmount": signed_order.takerAmount,
            "expiration": signed_order.expiration,
            "nonce": signed_order.nonce,
            "feeRateBps": signed_order.feeRateBps,
            "side": signed_order.side,
            "signatureType": signed_order.signatureType,
            "signature": signed_order.signature
        }