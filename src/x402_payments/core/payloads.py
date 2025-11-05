"""
Helpers for constructing the JSON payloads sent to the x402 facilitator.
"""

from __future__ import annotations

import secrets
import time
from typing import Any, Dict, Optional

from eth_account import Account
from eth_account.messages import encode_typed_data
from hexbytes import HexBytes

from .config import PaymentConfig

__all__ = [
    "build_authorization_payload",
    "build_payment_payload",
    "build_payment_request",
]


def build_authorization_payload(
    config: PaymentConfig,
    *,
    now: Optional[int] = None,
    nonce: Optional[bytes] = None,
) -> Dict[str, Any]:
    """
    Construct and sign the ERC-3009 TransferWithAuthorization payload.
    """
    now = int(time.time()) if now is None else now
    nonce_bytes = nonce if nonce is not None else secrets.token_bytes(32)
    valid_after = now - config.backdate_seconds
    valid_before = now + config.max_timeout_seconds

    message = {
        "from": config.payer_address,
        "to": config.receiver_address,
        "value": config.amount_base_units,
        "validAfter": valid_after,
        "validBefore": valid_before,
        "nonce": HexBytes(nonce_bytes),
    }
    domain = {
        "name": config.token_name,
        "version": config.token_version,
        "chainId": config.chain_id,
        "verifyingContract": config.asset_address,
    }
    typed_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "primaryType": "TransferWithAuthorization",
        "domain": domain,
        "message": message,
    }

    account = Account.from_key(config.payer_private_key)
    signable = encode_typed_data(full_message=typed_data)
    signature = account.sign_message(signable).signature

    return {
        "signature": "0x" + signature.hex(),
        "authorization": {
            "from": config.payer_address,
            "to": config.receiver_address,
            "value": config.amount_base_units_str,
            "validAfter": str(valid_after),
            "validBefore": str(valid_before),
            "nonce": "0x" + nonce_bytes.hex(),
        },
    }


def build_payment_payload(
    config: PaymentConfig,
    *,
    now: Optional[int] = None,
    nonce: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Build the payload submitted to ``/verify`` and ``/settle``."""
    return {
        "x402Version": 1,
        "scheme": "exact",
        "network": config.network,
        "payload": build_authorization_payload(config, now=now, nonce=nonce),
    }


def build_payment_request(
    config: PaymentConfig,
    *,
    now: Optional[int] = None,
    nonce: Optional[bytes] = None,
) -> Dict[str, Any]:
    """
    Build the full facilitator request body containing the payment payload and requirements.
    """
    return {
        "x402Version": 1,
        "paymentPayload": build_payment_payload(config, now=now, nonce=nonce),
        "paymentRequirements": config.payment_requirements(),
    }

