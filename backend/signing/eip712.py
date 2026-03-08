"""
EIP-712 Typed Data Signing Implementation

This module implements EIP-712 typed data signing for Polymarket CLOB API orders.
Based on the EIP-712 standard: https://eips.ethereum.org/EIPS/eip-712
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from eth_account import Account
from eth_account.messages import encode_typed_data
from web3 import Web3


@dataclass
class EIP712Domain:
    """EIP-712 Domain Separator"""
    name: str
    version: str
    chainId: int
    verifyingContract: str


@dataclass
class Order:
    """
    Polymarket CLOB Order Structure
    
    Based on: https://github.com/Polymarket/clob-order-utils/blob/v2.1.0/src/exchange.order.const.ts#L22-L35
    """
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
    side: int  # 0 = BUY, 1 = SELL
    signatureType: int  # 0 = EOA, 1 = POLY_PROXY, 2 = POLY_GNOSIS_SAFE


def build_domain(
    name: str = "Polymarket CTF Exchange",
    version: str = "1",
    chain_id: int = 137,  # Polygon Mainnet
    verifying_contract: str = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
) -> Dict[str, Any]:
    """
    Build EIP-712 domain separator for Polymarket
    
    Args:
        name: Protocol name (default: "Polymarket CTF Exchange")
        version: Protocol version (default: "1")
        chain_id: Chain ID (default: 137 for Polygon Mainnet)
        verifying_contract: Exchange contract address
        
    Returns:
        Domain separator dictionary
    """
    return {
        "name": name,
        "version": version,
        "chainId": chain_id,
        "verifyingContract": verifying_contract
    }


def get_order_types() -> Dict[str, List[Dict[str, str]]]:
    """
    Get EIP-712 type definitions for Order struct
    
    Returns:
        Type definitions dictionary
    """
    return {
        "EIP712Domain": [
            {"name": "name", "type": "string"},
            {"name": "version", "type": "string"},
            {"name": "chainId", "type": "uint256"},
            {"name": "verifyingContract", "type": "address"}
        ],
        "Order": [
            {"name": "salt", "type": "uint256"},
            {"name": "maker", "type": "address"},
            {"name": "signer", "type": "address"},
            {"name": "taker", "type": "address"},
            {"name": "tokenId", "type": "uint256"},
            {"name": "makerAmount", "type": "uint256"},
            {"name": "takerAmount", "type": "uint256"},
            {"name": "expiration", "type": "uint256"},
            {"name": "nonce", "type": "uint256"},
            {"name": "feeRateBps", "type": "uint256"},
            {"name": "side", "type": "uint8"},
            {"name": "signatureType", "type": "uint8"}
        ]
    }


def sign_typed_data(
    private_key: str,
    domain: Dict[str, Any],
    message: Dict[str, Any],
    types: Optional[Dict[str, List[Dict[str, str]]]] = None
) -> str:
    """
    Sign EIP-712 typed data with private key
    
    Args:
        private_key: Ethereum private key (hex string)
        domain: EIP-712 domain separator
        message: Message to sign
        types: Type definitions (default: Order types)
        
    Returns:
        Hex-encoded signature
        
    Security:
        - Private key is used in memory only
        - Never transmitted over network
        - Never logged or printed
    """
    if types is None:
        types = get_order_types()
    
    # Build typed data structure
    typed_data = {
        "types": types,
        "domain": domain,
        "primaryType": "Order",
        "message": message
    }
    
    # Sign with eth-account
    # This uses the private key in memory only
    account = Account.from_key(private_key)
    
    # Encode and sign typed data
    signable_message = encode_typed_data(full_message=typed_data)
    signed_message = account.sign_message(signable_message)
    
    # Return hex signature with 0x prefix
    return "0x" + signed_message.signature.hex()


def build_order_message(
    salt: int,
    maker: str,
    signer: str,
    taker: str,
    token_id: str,
    maker_amount: str,
    taker_amount: str,
    expiration: int,
    nonce: int,
    fee_rate_bps: str,
    side: int,
    signature_type: int = 0
) -> Dict[str, Any]:
    """
    Build Order message dictionary for signing
    
    Args:
        salt: Random salt for unique order
        maker: Maker address (funder)
        signer: Signing address
        taker: Taker address (operator, usually zero address)
        token_id: ERC1155 token ID
        maker_amount: Maximum amount maker is willing to spend
        taker_amount: Minimum amount taker must pay
        expiration: Unix expiration timestamp (0 = no expiration)
        nonce: Maker's Exchange nonce
        fee_rate_bps: Fee rate in basis points
        side: 0 = BUY, 1 = SELL
        signature_type: 0 = EOA, 1 = POLY_PROXY, 2 = POLY_GNOSIS_SAFE
        
    Returns:
        Order message dictionary
    """
    return {
        "salt": salt,
        "maker": maker,
        "signer": signer,
        "taker": taker,
        "tokenId": token_id,
        "makerAmount": maker_amount,
        "takerAmount": taker_amount,
        "expiration": expiration,
        "nonce": nonce,
        "feeRateBps": fee_rate_bps,
        "side": side,
        "signatureType": signature_type
    }


def verify_signature(
    signature: str,
    domain: Dict[str, Any],
    message: Dict[str, Any],
    expected_address: str,
    types: Optional[Dict[str, List[Dict[str, str]]]] = None
) -> bool:
    """
    Verify EIP-712 signature
    
    Args:
        signature: Hex-encoded signature
        domain: EIP-712 domain separator
        message: Message that was signed
        expected_address: Expected signer address
        types: Type definitions (default: Order types)
        
    Returns:
        True if signature is valid
    """
    if types is None:
        types = get_order_types()
    
    # Build typed data
    typed_data = {
        "types": types,
        "domain": domain,
        "primaryType": "Order",
        "message": message
    }
    
    # Encode typed data
    signable_message = encode_typed_data(full_message=typed_data)
    
    # Recover address from signature
    recovered_address = Account.recover_message(signable_message, signature=signature)
    
    # Compare addresses (case-insensitive)
    return recovered_address.lower() == expected_address.lower()
