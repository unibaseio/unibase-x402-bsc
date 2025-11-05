# X402 Tools on BSC - Powered by Unibase

Unibase operates the inaugural **x402 facilitator** on BNB Chain, unlocking low-cost, high-throughput payments for AI agents and automated workflows. The facilitator verifies cryptographically signed payment payloads and settles them on-chain so resource servers can monetize protected routes.

This repository packages an end-to-end example for executing an [`x402`](https://docs.unibase.com/x402) payment on Binance Smart Chain (BSC) using Wrapped USDC.  
It promotes the original standalone script into a reusable Python package with a CLI entry point so you can publish and consume it as a tool or integrate it into other agents.

## Protocol Background

### About x402
The x402 payment protocol is HTTP-based. Resource servers declare payment requirements for specific routes, clients sign payment payloads with their private keys, and facilitators (such as this one) verify and settle the transfers on-chain.

### About XUSD
XUSD is an ERC-3009 compatible wrapped stablecoin for x402 payments on BNB Chain. Holders can wrap or unwrap to USDC on a 1:1 basis at any time, making it the canonical settlement asset for this facilitator.

### Supported Assets
- XUSD (`0xf3A3E4D9c163251124229Da6DC9C98D889647804`)
- Other ERC-3009 compliant tokens

> ℹ️ **Reminder:** Wrap your USDC on BSC into XUSD at [x402.unibase.com/xusd](https://www.x402.unibase.com/xusd) before initiating payments so the facilitator can approve and settle the transfer.

### Facilitator Endpoint
- Default `X402_FACILITATOR_URL`: `https://api.x402.unibase.com`

## Features
- Loads payment configuration from environment variables (with optional `.env`).
- Supports runtime overrides so agents can inject config without editing files.
- Works with Wrapped USDC on BSC by settling through XUSD (ERC-3009).
- Signs an ERC-3009 `TransferWithAuthorization` payload locally.
- Verifies and settles the payment through the Unibase x402 facilitator.
- Ships as an installable package exposing both a CLI and importable helpers.

### Package Layout
- `x402_payments.core.config`, `.environment`, `.payloads`, `.client`: immutable building blocks for loading configuration, constructing payloads, and invoking the facilitator.
- `x402_payments.api`: ergonomic façade that layers parameter shorthands and helper constructors on top of the core modules.
- `x402_payments.cli`: command-line utility showcasing how to wire the API together.

## Prerequisites
- Python 3.10 or newer
- [`uv`](https://github.com/astral-sh/uv) for dependency management
- A wallet on BSC (mainnet by default) with XUSD (wrap USDC 1:1 on-chain) and a destination address

## Setup
1. Copy the example environment file and fill in your real values:
   ```bash
   cp .env.example .env
   # Edit .env to add your private key, receiver, and optional overrides
   ```
2. Create and populate a virtual environment with `uv`:
   ```bash
   uv sync
   ```
   This installs the dependencies declared in `pyproject.toml` and produces a `uv.lock`.

## Usage
Run the packaged CLI after the environment is configured:
```bash
uv run x402-payments --env-file .env
```

Useful flags:
- `--env-file`: path to a `.env` file (defaults to `.env` in the project root)
- `--set`: override a single `KEY=VALUE` without touching the filesystem (repeatable)
- `--log-level`: Python logging level (e.g. `DEBUG`, `INFO`, `WARNING`)
- `--verify-only`: stop after `/verify` succeeds without settling on-chain

### API Integration
You can assemble configuration from a `.env` file, from the process environment, entirely in code, or any combination of the three:
```python
from decimal import Decimal
import requests
from x402_payments import (
    ConfigError,
    PaymentClient,
    SettlementResult,
    create_payment_client,
    load_payment_config,
)

try:
    config = load_payment_config(
        env_file=".env",
        payer_private_key="0xabc123...",
        receiver_address="0xreceiverAddressHere",
        amount=Decimal("0.5"),
    )
except (KeyError, ConfigError, ValueError) as exc:
    raise RuntimeError(f"Configuration error: {exc}") from exc

client = create_payment_client(config=config, session=requests.Session())

payment_requirements = client.payment_requirements()
payment_payload = client.build_payment_payload()
request_body = {
    "x402Version": 1,
    "paymentRequirements": payment_requirements,
    "paymentPayload": payment_payload,
}

verify_response = client.verify(request_body)
if not verify_response["isValid"]:
    raise RuntimeError(f"Payment rejected: {verify_response}")

settlement = client.settle(request_body)
if not settlement.success:
    raise RuntimeError(f"Settlement failed: {settlement.raw}")

print(f"Settled on {settlement.network}: {settlement.transaction}")
```

If you prefer to bundle the knobs, build a `PaymentParameters` instance and pass it
to `load_payment_config(parameters=...)`. The dataclass mirrors the keyword arguments shown above.

For a higher-level abstraction, call `send_payment`:
```python
from x402_payments import send_payment

result = send_payment(
    env_file=".env",
    payer_private_key="0xabc123...",
    receiver_address="0xreceiverAddressHere",
    amount="0.5",
    verify_only=False,
)
print(result)
```

Or run the bundled example script:
```bash
uv run python examples/send_payment.py --env-file .env
```

## Publishing
- Update the metadata in `pyproject.toml` (name, version, author, license) before publishing.
- Run `uv sync` and commit the generated `uv.lock`.
- Tag a release and use `uv build` / `uv publish` (or your preferred build backend) to distribute the package.

## Security Notes
- Never commit real private keys. Use `.env.example` for documentation and keep secrets in local `.env` files or a dedicated secret manager.
- Review the facilitator URL and chain configuration before running on mainnet.
