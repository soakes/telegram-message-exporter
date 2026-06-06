"""Hash helpers used by Telegram local database parsing."""

from __future__ import annotations

from typing import Final

import importlib

try:
    mmh3 = importlib.import_module("mmh3")
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: mmh3==4.1.0. Install with `pip install mmh3==4.1.0`."
    ) from exc

TEMPKEY_MURMUR_SEED: Final[int] = 0xF7CA7FD2


def murmur_hash(data: bytes, seed: int = TEMPKEY_MURMUR_SEED) -> int:
    """Return the signed 32-bit Murmur3 hash for the given data."""
    return mmh3.hash(data, seed=seed, signed=True)


def murmur_hash_bytes(data: bytes, seed: int) -> bytes:
    """Return Murmur3 hash bytes for the given data."""
    return mmh3.hash_bytes(data, seed=seed)


def persistent_hash32(value: str) -> int:
    """Return Telegram/Postbox persistentHash32-compatible output."""
    return mmh3.hash(value, seed=0, signed=True)
