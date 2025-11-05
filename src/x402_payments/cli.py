"""
Command-line interface for exercising the x402 payment APIs.
"""

from __future__ import annotations

import argparse
import logging
from typing import Iterable, Sequence, Tuple

import requests

from .api import ConfigError, SettlementResult, create_payment_client, load_payment_config


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )


def _env_override(value: str) -> Tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Overrides must look like KEY=VALUE")
    key, val = value.split("=", 1)
    key = key.strip()
    if not key:
        raise argparse.ArgumentTypeError("Override key must not be empty")
    return key, val


def _collect_overrides(pairs: Iterable[Tuple[str, str]]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for key, value in pairs:
        overrides[key] = value
    return overrides


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="x402-payments",
        description="Execute a single x402 payment flow on BSC",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to the .env file containing X402_* settings (default: .env)",
    )
    parser.add_argument(
        "--set",
        action="append",
        type=_env_override,
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
        help="Submit the payload to /verify but skip settlement",
    )
    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    _configure_logging(args.log_level)
    overrides = _collect_overrides(args.set or ())

    try:
        config = load_payment_config(env_file=args.env_file, overrides=overrides)
    except (KeyError, ConfigError, ValueError) as exc:
        logging.error("Invalid configuration: %s", exc)
        return 1

    client = create_payment_client(config=config, session=requests.Session())
    request_body = client.build_request()

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
        logging.info("Skipping settlement because --verify-only was requested")
        return 0

    try:
        settlement = client.settle(request_body)
    except Exception as exc:  # noqa: BLE001
        logging.error("Settlement request failed: %s", exc)
        return 1

    return _handle_settlement(settlement)


def _handle_settlement(settlement: SettlementResult) -> int:
    if not settlement.success:
        logging.error("Settlement failed: %s", settlement.raw)
        return 1

    logging.info(
        "Payment settled on %s. Transaction hash: %s",
        settlement.network,
        settlement.transaction,
    )
    return 0
