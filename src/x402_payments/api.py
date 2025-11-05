"""
Public, high-level helpers for interacting with the x402 payment facilitator.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Optional

import requests

from .core.client import (
    PaymentClient,
    SettlementResult,
    send_payment as _send_payment,
    settle_payment,
    verify_payment,
)
from .core.config import (
    ConfigError,
    PaymentConfig,
    PaymentParameters,
    load_payment_config,
)
from .core.environment import PaymentEnvironment, build_environment, load_env_file
from .core.payloads import (
    build_authorization_payload,
    build_payment_payload,
    build_payment_request,
)

__all__ = [
    "ConfigError",
    "PaymentClient",
    "PaymentConfig",
    "PaymentEnvironment",
    "PaymentParameters",
    "SettlementResult",
    "build_authorization_payload",
    "build_environment",
    "build_payment_payload",
    "build_payment_request",
    "create_payment_client",
    "load_env_file",
    "load_payment_config",
    "send_payment",
    "settle_payment",
    "verify_payment",
]


def create_payment_client(
    *,
    config: Optional[PaymentConfig] = None,
    session: Optional[requests.Session] = None,
    env_file: Optional[str] = ".env",
    overrides: Optional[Mapping[str, str]] = None,
    base: Optional[Mapping[str, str]] = None,
    parameters: Optional[PaymentParameters] = None,
    payer_private_key: Optional[str] = None,
    payer_address: Optional[str] = None,
    receiver_address: Optional[str] = None,
    facilitator_url: Optional[str] = None,
    amount: Optional[Decimal | str | float | int] = None,
    timeout_seconds: Optional[int | str] = None,
    backdate_seconds: Optional[int | str] = None,
    resource: Optional[str] = None,
    description: Optional[str] = None,
    mime_type: Optional[str] = None,
    token_decimals: Optional[int | str] = None,
    asset_address: Optional[str] = None,
    token_name: Optional[str] = None,
    token_version: Optional[str] = None,
    chain_id: Optional[int | str] = None,
    network: Optional[str] = None,
) -> PaymentClient:
    """
    Construct a :class:`PaymentClient`.

    Callers can either supply a ready-made :class:`PaymentConfig` or let the
    helper assemble one from environment data.
    """
    if config is not None:
        extras = (
            overrides,
            base,
            parameters,
            payer_private_key,
            payer_address,
            receiver_address,
            facilitator_url,
            amount,
            timeout_seconds,
            backdate_seconds,
            resource,
            description,
            mime_type,
            token_decimals,
            asset_address,
            token_name,
            token_version,
            chain_id,
            network,
        )
        if any(item is not None and item != {} for item in extras):
            raise ValueError(
                "Provide either a pre-built PaymentConfig or individual parameters, not both."
            )
        cfg = config
    else:
        cfg = load_payment_config(
            env_file=env_file,
            overrides=overrides,
            base=base,
            parameters=parameters,
            payer_private_key=payer_private_key,
            payer_address=payer_address,
            receiver_address=receiver_address,
            facilitator_url=facilitator_url,
            amount=amount,
            timeout_seconds=timeout_seconds,
            backdate_seconds=backdate_seconds,
            resource=resource,
            description=description,
            mime_type=mime_type,
            token_decimals=token_decimals,
            asset_address=asset_address,
            token_name=token_name,
            token_version=token_version,
            chain_id=chain_id,
            network=network,
        )
    return PaymentClient(cfg, session=session)


def send_payment(
    *,
    config: Optional[PaymentConfig] = None,
    session: Optional[requests.Session] = None,
    env_file: Optional[str] = ".env",
    overrides: Optional[Mapping[str, str]] = None,
    base: Optional[Mapping[str, str]] = None,
    verify_only: bool = False,
    parameters: Optional[PaymentParameters] = None,
    payer_private_key: Optional[str] = None,
    payer_address: Optional[str] = None,
    receiver_address: Optional[str] = None,
    facilitator_url: Optional[str] = None,
    amount: Optional[Decimal | str | float | int] = None,
    timeout_seconds: Optional[int | str] = None,
    backdate_seconds: Optional[int | str] = None,
    resource: Optional[str] = None,
    description: Optional[str] = None,
    mime_type: Optional[str] = None,
    token_decimals: Optional[int | str] = None,
    asset_address: Optional[str] = None,
    token_name: Optional[str] = None,
    token_version: Optional[str] = None,
    chain_id: Optional[int | str] = None,
    network: Optional[str] = None,
) -> SettlementResult:
    """
    High-level convenience wrapper that handles verify + settle.
    """
    if config is not None:
        extras = (
            overrides,
            base,
            parameters,
            payer_private_key,
            payer_address,
            receiver_address,
            facilitator_url,
            amount,
            timeout_seconds,
            backdate_seconds,
            resource,
            description,
            mime_type,
            token_decimals,
            asset_address,
            token_name,
            token_version,
            chain_id,
            network,
        )
        if any(item is not None and item != {} for item in extras):
            raise ValueError(
                "Provide either a pre-built PaymentConfig or individual parameters, not both."
            )
        cfg = config
    else:
        cfg = load_payment_config(
            env_file=env_file,
            overrides=overrides,
            base=base,
            parameters=parameters,
            payer_private_key=payer_private_key,
            payer_address=payer_address,
            receiver_address=receiver_address,
            facilitator_url=facilitator_url,
            amount=amount,
            timeout_seconds=timeout_seconds,
            backdate_seconds=backdate_seconds,
            resource=resource,
            description=description,
            mime_type=mime_type,
            token_decimals=token_decimals,
            asset_address=asset_address,
            token_name=token_name,
            token_version=token_version,
            chain_id=chain_id,
            network=network,
        )
    return _send_payment(cfg, session=session, verify_only=verify_only)
