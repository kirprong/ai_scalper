"""
EIP-712 Signing Module for Polymarket CLOB API

This module provides local EIP-712 signing functionality for Polymarket orders
without transmitting private keys over the network.
"""

from .eip712 import (
    EIP712Domain,
    Order,
    build_domain,
    sign_typed_data,
    verify_signature,
    build_order_message,
    get_order_types,
)

from .polymarket_signer import (
    PolymarketSigner,
    SignatureType,
    OrderSide,
)

__all__ = [
    "EIP712Domain",
    "Order",
    "build_domain",
    "sign_typed_data",
    "verify_signature",
    "build_order_message",
    "get_order_types",
    "PolymarketSigner",
    "SignatureType",
    "OrderSide",
]
