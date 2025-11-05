"""
Configuration objects and helpers for x402 payments.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Mapping, Optional

from eth_account import Account
from eth_utils import is_hex_address, to_checksum_address

from .environment import PaymentEnvironment, build_environment

__all__ = [
    "ConfigError",
    "PaymentConfig",
    "PaymentParameters",
    "load_payment_config",
]

_PARAMETER_TO_ENV_KEY = {
    "payer_private_key": "X402_PAYER_PRIVATE_KEY",
    "payer_address": "X402_PAYER_ADDRESS",
    "receiver_address": "X402_RECEIVER_ADDRESS",
    "facilitator_url": "X402_FACILITATOR_URL",
    "amount": "X402_PAYMENT_AMOUNT",
    "timeout_seconds": "X402_PAYMENT_TIMEOUT_SECONDS",
    "backdate_seconds": "X402_PAYMENT_BACKDATE_SECONDS",
    "resource": "X402_PAYMENT_RESOURCE",
    "description": "X402_PAYMENT_DESCRIPTION",
    "mime_type": "X402_PAYMENT_MIME_TYPE",
    "token_decimals": "X402_PAYMENT_TOKEN_DECIMALS",
    "asset_address": "X402_PAYMENT_ASSET_ADDRESS",
    "token_name": "X402_PAYMENT_TOKEN_NAME",
    "token_version": "X402_PAYMENT_TOKEN_VERSION",
    "chain_id": "X402_PAYMENT_CHAIN_ID",
    "network": "X402_PAYMENT_NETWORK",
}


def _stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


@dataclass(frozen=True)
class PaymentParameters:
    """
    Explicit parameter bundle for constructing :class:`PaymentConfig`.

    Callers can either instantiate this helper or pass the individual keyword
    arguments directly to :func:`load_payment_config`.
    """

    payer_private_key: Optional[str] = None
    payer_address: Optional[str] = None
    receiver_address: Optional[str] = None
    facilitator_url: Optional[str] = None
    amount: Optional[Decimal | str | float | int] = None
    timeout_seconds: Optional[int | str] = None
    backdate_seconds: Optional[int | str] = None
    resource: Optional[str] = None
    description: Optional[str] = None
    mime_type: Optional[str] = None
    token_decimals: Optional[int | str] = None
    asset_address: Optional[str] = None
    token_name: Optional[str] = None
    token_version: Optional[str] = None
    chain_id: Optional[int | str] = None
    network: Optional[str] = None

    def as_overrides(self) -> Dict[str, str]:
        overrides: Dict[str, str] = {}
        for field_name, env_key in _PARAMETER_TO_ENV_KEY.items():
            value = getattr(self, field_name)
            if value is None:
                continue
            overrides[env_key] = _stringify(value)
        return overrides


def _collect_parameter_overrides(
    parameters: Optional[PaymentParameters],
    explicit: Mapping[str, Any],
) -> Dict[str, str]:
    overrides: Dict[str, str] = {}
    if parameters is not None:
        overrides.update(parameters.as_overrides())

    for key, value in explicit.items():
        if value is None:
            continue
        try:
            env_key = _PARAMETER_TO_ENV_KEY[key]
        except KeyError as exc:  # pragma: no cover - defensive, should not trigger
            raise TypeError(f"Unknown payment parameter '{key}'") from exc
        overrides[env_key] = _stringify(value)
    return overrides


class ConfigError(Exception):
    """Raised when the supplied configuration is invalid."""


def _normalize_private_key(raw_key: str) -> str:
    key = raw_key.strip()
    if not key:
        raise ConfigError("X402_PAYER_PRIVATE_KEY must not be empty")
    if not key.startswith("0x"):
        key = "0x" + key
    if len(key) != 66:
        raise ConfigError("X402_PAYER_PRIVATE_KEY must be 32 bytes (64 hex chars)")
    return key


def _normalize_address(raw_address: str, field_name: str) -> str:
    value = raw_address.strip()
    if not value:
        raise ConfigError(f"{field_name} must not be empty")
    if not value.startswith("0x"):
        value = "0x" + value
    if not is_hex_address(value):
        raise ConfigError(f"{field_name} is not a valid EVM address")

    return to_checksum_address(value)


def _to_base_units(amount: Decimal, decimals: int) -> int:
    scaled = amount * (Decimal(10) ** decimals)
    try:
        integral = scaled.to_integral_exact()
    except InvalidOperation as exc:
        raise ConfigError(
            f"Amount {amount} cannot be represented with {decimals} decimals"
        ) from exc

    if integral != scaled:
        raise ConfigError(
            f"Amount {amount} cannot be represented with {decimals} decimals"
        )
    as_int = int(integral)
    if as_int <= 0:
        raise ConfigError("Payment amount must be greater than zero")

    return as_int


@dataclass(frozen=True)
class PaymentConfig:
    facilitator_url: str
    payer_private_key: str
    payer_address: str
    receiver_address: str
    asset_address: str
    amount_decimal: Decimal
    amount_base_units: int
    resource: str
    description: str
    mime_type: str
    max_timeout_seconds: int
    backdate_seconds: int
    chain_id: int = 56
    network: str = "bsc"
    token_name: str = "Wrapped USDC"
    token_version: str = "2"

    @property
    def amount_base_units_str(self) -> str:
        return str(self.amount_base_units)

    def payment_requirements(self) -> Dict[str, Any]:
        return {
            "scheme": "exact",
            "network": self.network,
            "maxAmountRequired": self.amount_base_units_str,
            "resource": self.resource,
            "description": self.description,
            "mimeType": self.mime_type,
            "outputSchema": None,
            "payTo": self.receiver_address,
            "maxTimeoutSeconds": self.max_timeout_seconds,
            "asset": self.asset_address,
            "extra": {
                "name": self.token_name,
                "version": self.token_version,
            },
        }

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> "PaymentConfig":
        facilitator_url = values.get(
            "X402_FACILITATOR_URL", "https://api.x402.unibase.com"
        ).rstrip("/")

        private_key = _normalize_private_key(values["X402_PAYER_PRIVATE_KEY"])
        payer_account = Account.from_key(private_key)

        payer_address = values.get("X402_PAYER_ADDRESS", payer_account.address)
        payer_address = _normalize_address(payer_address, "X402_PAYER_ADDRESS")

        receiver_raw = values.get("X402_RECEIVER_ADDRESS")
        if receiver_raw is None:
            raise ConfigError("X402_RECEIVER_ADDRESS must be provided")
        receiver_address = _normalize_address(
            receiver_raw, "X402_RECEIVER_ADDRESS"
        )

        amount_raw = values.get("X402_PAYMENT_AMOUNT", "0.1")
        try:
            amount_decimal = Decimal(amount_raw)
        except InvalidOperation as exc:
            raise ConfigError(
                f"X402_PAYMENT_AMOUNT must be a valid decimal number, got '{amount_raw}'"
            ) from exc

        max_timeout_seconds = int(values.get("X402_PAYMENT_TIMEOUT_SECONDS", "600"))
        backdate_seconds = int(values.get("X402_PAYMENT_BACKDATE_SECONDS", "600"))

        asset_address = _normalize_address(
            values.get(
                "X402_PAYMENT_ASSET_ADDRESS",
                "0xf3A3E4D9c163251124229Da6DC9C98D889647804",
            ),
            "X402_PAYMENT_ASSET_ADDRESS",
        )

        decimals = int(values.get("X402_PAYMENT_TOKEN_DECIMALS", "18"))
        amount_base_units = _to_base_units(amount_decimal, decimals)

        resource = values.get(
            "X402_PAYMENT_RESOURCE", "https://example.com/protected-resource"
        )
        description = values.get(
            "X402_PAYMENT_DESCRIPTION",
            "Example payment for x402-protected resource",
        )
        mime_type = values.get("X402_PAYMENT_MIME_TYPE", "application/json")

        token_name = values.get("X402_PAYMENT_TOKEN_NAME", "Wrapped USDC")
        token_version = values.get("X402_PAYMENT_TOKEN_VERSION", "2")
        chain_id = int(values.get("X402_PAYMENT_CHAIN_ID", "56"))
        network = values.get("X402_PAYMENT_NETWORK", "bsc")

        return cls(
            facilitator_url=facilitator_url,
            payer_private_key=private_key,
            payer_address=payer_address,
            receiver_address=receiver_address,
            asset_address=asset_address,
            amount_decimal=amount_decimal,
            amount_base_units=amount_base_units,
            resource=resource,
            description=description,
            mime_type=mime_type,
            max_timeout_seconds=max_timeout_seconds,
            backdate_seconds=backdate_seconds,
            chain_id=chain_id,
            network=network,
            token_name=token_name,
            token_version=token_version,
        )

    @classmethod
    def from_env(
        cls,
        *,
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
    ) -> "PaymentConfig":
        parameter_overrides = _collect_parameter_overrides(
            parameters,
            {
                "payer_private_key": payer_private_key,
                "payer_address": payer_address,
                "receiver_address": receiver_address,
                "facilitator_url": facilitator_url,
                "amount": amount,
                "timeout_seconds": timeout_seconds,
                "backdate_seconds": backdate_seconds,
                "resource": resource,
                "description": description,
                "mime_type": mime_type,
                "token_decimals": token_decimals,
                "asset_address": asset_address,
                "token_name": token_name,
                "token_version": token_version,
                "chain_id": chain_id,
                "network": network,
            },
        )
        merged_overrides = dict(overrides or {})
        merged_overrides.update(parameter_overrides)

        environment = build_environment(
            env_file=env_file,
            base=base,
            overrides=merged_overrides,
        )
        return cls.from_mapping(environment.variables)


def load_payment_config(
    *,
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
) -> PaymentConfig:
    """
    Convenience wrapper that mirrors :meth:`PaymentConfig.from_env`.

    The configuration can be provided entirely through environment variables,
    a ``.env`` file, direct keyword arguments, or any combination of the three.
    """
    return PaymentConfig.from_env(
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
