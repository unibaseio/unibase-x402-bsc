"""
Utilities for building the environment used by the x402 payment helpers.

The helpers are intentionally lightweight: they understand .env files, allow
callers to layer overrides, and ultimately return a plain ``dict`` that can be
fed into :class:`x402_payments.core.config.PaymentConfig`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, MutableMapping, Optional


def _parse_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    try:
        data = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return values

    for raw_line in data.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def load_env_file(
    path: str = ".env",
    *,
    environ: Optional[MutableMapping[str, str]] = None,
) -> Dict[str, str]:
    """
    Load environment variables from ``path`` into ``environ``.

    Existing keys are preserved. The merged mapping is returned so callers can
    inspect the resulting values.
    """
    target: MutableMapping[str, str] = environ if environ is not None else os.environ
    values = _parse_env_file(Path(path))
    for key, value in values.items():
        target.setdefault(key, value)
    return dict(target)


@dataclass(frozen=True)
class PaymentEnvironment:
    """
    A resolved set of environment variables used to configure payments.
    """

    variables: Mapping[str, str]

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.variables.get(key, default)


def build_environment(
    *,
    env_file: Optional[str] = ".env",
    base: Optional[Mapping[str, str]] = None,
    overrides: Optional[Mapping[str, str]] = None,
) -> PaymentEnvironment:
    """
    Assemble a :class:`PaymentEnvironment` from multiple sources.

    ``base`` defaults to :data:`os.environ`. ``env_file`` is optional; set it to
    ``None`` to skip file loading entirely. ``overrides`` always win.
    """
    merged: Dict[str, str] = dict(base or os.environ)

    if env_file is not None:
        for key, value in _parse_env_file(Path(env_file)).items():
            merged.setdefault(key, value)

    if overrides:
        merged.update(overrides)

    return PaymentEnvironment(variables=merged)
