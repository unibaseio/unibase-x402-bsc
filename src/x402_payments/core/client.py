"""
HTTP client helpers for the x402 facilitator.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from .config import PaymentConfig
from .payloads import (
    build_authorization_payload,
    build_payment_payload,
    build_payment_request,
)

__all__ = [
    "PaymentClient",
    "SettlementResult",
    "verify_payment",
    "settle_payment",
    "send_payment",
]


def _post_json(session: requests.Session, url: str, body: Dict[str, Any]) -> Dict[str, Any]:
    response = session.post(url, json=body, timeout=30)
    if response.status_code >= 400:
        raise RuntimeError(
            f"Facilitator responded with {response.status_code}: {response.text}"
        )
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Failed to parse JSON from facilitator at {url}: {response.text}"
        ) from exc


def verify_payment(
    session: requests.Session,
    config: PaymentConfig,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    verify_url = f"{config.facilitator_url}/verify"
    logging.info("Submitting payment for verification to %s", verify_url)
    return _post_json(session, verify_url, body)


@dataclass(frozen=True)
class SettlementResult:
    success: bool
    network: Optional[str]
    transaction: Optional[str]
    raw: Dict[str, Any]

    @classmethod
    def from_response(cls, payload: Dict[str, Any]) -> "SettlementResult":
        return cls(
            success=bool(payload.get("success")),
            network=payload.get("network"),
            transaction=payload.get("transaction"),
            raw=payload,
        )


def settle_payment(
    session: requests.Session,
    config: PaymentConfig,
    body: Dict[str, Any],
) -> SettlementResult:
    settle_url = f"{config.facilitator_url}/settle"
    logging.info("Submitting payment for settlement to %s", settle_url)
    payload = _post_json(session, settle_url, body)
    return SettlementResult.from_response(payload)


class PaymentClient:
    """
    Thin convenience wrapper around the facilitator endpoints.
    """

    def __init__(
        self,
        config: PaymentConfig,
        *,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.config = config
        self.session = session or requests.Session()

    def payment_requirements(self) -> Dict[str, Any]:
        """
        Return the payment requirements derived from the configuration.
        """
        return self.config.payment_requirements()

    def build_authorization_payload(
        self,
        *,
        now: Optional[int] = None,
        nonce: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        return build_authorization_payload(self.config, now=now, nonce=nonce)

    def build_payment_payload(
        self,
        *,
        now: Optional[int] = None,
        nonce: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        return build_payment_payload(self.config, now=now, nonce=nonce)

    def build_payment_request(
        self,
        *,
        now: Optional[int] = None,
        nonce: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        return build_payment_request(self.config, now=now, nonce=nonce)

    def build_request(
        self,
        *,
        now: Optional[int] = None,
        nonce: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """
        Backwards-compatible alias for :meth:`build_payment_request`.
        """
        return self.build_payment_request(now=now, nonce=nonce)

    def verify(self, body: Dict[str, Any]) -> Dict[str, Any]:
        return verify_payment(self.session, self.config, body)

    def settle(self, body: Dict[str, Any]) -> SettlementResult:
        return settle_payment(self.session, self.config, body)

    def send(self, *, verify_only: bool = False) -> SettlementResult:
        request_body = self.build_payment_request()
        verify_response = self.verify(request_body)
        if not verify_response.get("isValid"):
            raise RuntimeError(f"Payment rejected: {verify_response}")

        if verify_only:
            return SettlementResult(
                success=True,
                network=self.config.network,
                transaction=None,
                raw={"verifyOnly": True, "response": verify_response},
            )

        return self.settle(request_body)


def send_payment(
    config: PaymentConfig,
    *,
    session: Optional[requests.Session] = None,
    verify_only: bool = False,
) -> SettlementResult:
    """
    High-level helper that performs verify then settle for the given configuration.
    """
    client = PaymentClient(config, session=session)
    return client.send(verify_only=verify_only)
