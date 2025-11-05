"""
Minimal script that uses the public API to perform an x402 payment.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Iterable, Tuple

from x402_payments import ConfigError, create_payment_client, load_payment_config


def _override(value: str) -> Tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Overrides must look like KEY=VALUE")
    key, val = value.split("=", 1)
    key = key.strip()
    if not key:
        raise argparse.ArgumentTypeError("Override key must not be empty")
    return key, val


def _build_overrides(pairs: Iterable[Tuple[str, str]]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for key, value in pairs:
        overrides[key] = value
    return overrides


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send an x402 payment using the SDK API")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to the .env file containing X402_* settings",
    )
    parser.add_argument(
        "--set",
        action="append",
        type=_override,
        metavar="KEY=VALUE",
        default=None,
        help="Override an environment variable without editing the .env file",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level (default: INFO)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Stop after facilitator verification (no on-chain settlement)",
    )
    parser.add_argument(
        "--payer-private-key",
        help="Provide the payer's private key without relying on environment data",
    )
    parser.add_argument(
        "--payer-address",
        help="Override the payer address (derived from the private key by default)",
    )
    parser.add_argument(
        "--receiver-address",
        help="Override the receiver address without editing local files",
    )
    parser.add_argument(
        "--facilitator-url",
        help="Override the facilitator base URL (default: https://api.x402.unibase.com)",
    )
    parser.add_argument(
        "--amount",
        help="Override the payment amount in token units (e.g. 0.5)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        help="Override the payment timeout in seconds",
    )
    parser.add_argument(
        "--backdate-seconds",
        type=int,
        help="Override the payment backdate window in seconds",
    )
    parser.add_argument(
        "--resource",
        help="Override the resource URL protected by the payment",
    )
    parser.add_argument(
        "--description",
        help="Override the payment description shown to the payer",
    )
    parser.add_argument(
        "--mime-type",
        help="Override the MIME type associated with the protected resource",
    )
    parser.add_argument(
        "--token-decimals",
        type=int,
        help="Override the token's decimal precision",
    )
    parser.add_argument(
        "--asset-address",
        help="Override the ERC-20 token contract address",
    )
    parser.add_argument(
        "--token-name",
        help="Override the asset token name used for signing",
    )
    parser.add_argument(
        "--token-version",
        help="Override the asset token version used for signing",
    )
    parser.add_argument(
        "--chain-id",
        type=int,
        help="Override the EVM chain id used in signatures",
    )
    parser.add_argument(
        "--network",
        help="Override the short network identifier (default: bsc)",
    )
    return parser.parse_args()


def _collect_parameter_kwargs(args: argparse.Namespace) -> dict[str, object]:
    possible_values = {
        "payer_private_key": args.payer_private_key,
        "payer_address": args.payer_address,
        "receiver_address": args.receiver_address,
        "facilitator_url": args.facilitator_url,
        "amount": args.amount,
        "timeout_seconds": args.timeout_seconds,
        "backdate_seconds": args.backdate_seconds,
        "resource": args.resource,
        "description": args.description,
        "mime_type": args.mime_type,
        "token_decimals": args.token_decimals,
        "asset_address": args.asset_address,
        "token_name": args.token_name,
        "token_version": args.token_version,
        "chain_id": args.chain_id,
        "network": args.network,
    }
    return {key: value for key, value in possible_values.items() if value is not None}


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    overrides = _build_overrides(args.set or ())
    parameter_kwargs = _collect_parameter_kwargs(args)

    try:
        config = load_payment_config(
            env_file=args.env_file,
            overrides=overrides,
            **parameter_kwargs,
        )
    except (KeyError, ConfigError, ValueError) as exc:
        logging.error("Invalid configuration: %s", exc)
        return 1

    client = create_payment_client(config=config)
    logging.info("Preparing payment requirements for %s", config.facilitator_url)

    requirements = client.payment_requirements()
    payload = client.build_payment_payload()
    request_body = {
        "x402Version": 1,
        "paymentRequirements": requirements,
        "paymentPayload": payload,
    }

    try:
        verify_response = client.verify(request_body)
    except Exception as exc:  # noqa: BLE001
        logging.error("Verification request failed: %s", exc)
        return 1

    if not verify_response.get("isValid"):
        logging.error("Payment rejected: %s", verify_response)
        return 1

    payer = verify_response.get("payer")
    logging.info("Facilitator accepted payment payload for payer %s", payer)

    if args.verify_only:
        logging.info("Verification succeeded; skipping settlement.")
        return 0

    try:
        settlement = client.settle(request_body)
    except Exception as exc:  # noqa: BLE001
        logging.error("Settlement request failed: %s", exc)
        return 1

    if settlement.success:
        logging.info(
            "Payment settled on %s. Transaction hash: %s",
            settlement.network,
            settlement.transaction,
        )
        return 0

    logging.error("Settlement failed: %s", settlement.raw)
    return 1


if __name__ == "__main__":
    sys.exit(main())
