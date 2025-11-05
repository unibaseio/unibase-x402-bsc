"""
Public facade for the x402 payment helper package.

The module intentionally re-exports the most useful pieces for integrators so
they can ``from x402_payments import ...`` without navigating the package.
"""

from .api import create_payment_client, send_payment
from .core import (
    ConfigError,
    PaymentClient,
    PaymentConfig,
    PaymentParameters,
    PaymentEnvironment,
    SettlementResult,
    build_authorization_payload,
    build_environment,
    build_payment_payload,
    build_payment_request,
    load_env_file,
    load_payment_config,
    settle_payment,
    verify_payment,
)

__all__ = (
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
    "load_env_file",
    "load_payment_config",
    "create_payment_client",
    "settle_payment",
    "verify_payment",
    "send_payment",
)
