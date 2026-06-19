"""Cryptographic helpers for Telegram Desktop database decryption."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Protocol

import hashlib
import importlib
import os
import struct

from .hashing import TEMPKEY_MURMUR_SEED, murmur_hash, murmur_hash_bytes

try:
    AES = importlib.import_module("Cryptodome.Cipher.AES")
except ImportError as exc:  # pragma: no cover - missing optional dependency
    raise SystemExit(
        "Missing dependency: pycryptodomex. Install with `pip install pycryptodomex`."
    ) from exc

try:
    SQLCIPHER = importlib.import_module("sqlcipher3")
except ImportError:  # pragma: no cover - optional fallback
    try:
        SQLCIPHER = importlib.import_module("pysqlcipher3.dbapi2")
    except ImportError:
        SQLCIPHER = None

DEFAULT_PASSCODE = b"no-matter-key"


@dataclass(frozen=True)
class KeyCandidate:
    """Candidate SQLCipher key material."""

    name: str
    hex_value: str


@dataclass(frozen=True)
class KeyDerivationInfo:
    """Metadata for derived keys."""

    candidates: tuple[KeyCandidate, ...]
    tempkey_ok: bool
    local_key: Optional[bytes]


@dataclass(frozen=True)
class SqlCipherProfile:
    """SQLCipher profile parameters."""

    name: str
    compat: Optional[int]
    pragmas: dict[str, str | int]
    compat_before_key: bool = False


@dataclass(frozen=True)
class SqlCipherMatch:
    """Match details for a successful SQLCipher open."""

    connection: "SqlCipherConnection"
    candidate: KeyCandidate
    profile: SqlCipherProfile


@dataclass(frozen=True)
class DecryptResult:
    """Result of decrypting a Telegram database."""

    key_info: KeyDerivationInfo
    match: SqlCipherMatch


class SqlCipherConnection(Protocol):
    """Protocol for SQLCipher connection objects."""

    def execute(self, sql: str) -> object:  # pragma: no cover - protocol definition
        """Execute a SQL statement."""

    def close(self) -> None:  # pragma: no cover - protocol definition
        """Close the connection."""


def read_passcodes(value: Optional[str]) -> list[bytes]:
    """Resolve passcodes from CLI or environment."""
    if value is not None:
        return [value.encode("utf-8")]
    env_val = os.environ.get("TG_LOCAL_PASSCODE")
    if env_val is not None:
        return [env_val.encode("utf-8")]
    return [DEFAULT_PASSCODE, b""]


def _tempkey_kdf(passcode: bytes) -> tuple[bytes, bytes]:
    digest = hashlib.sha512(passcode).digest()
    return digest[:32], digest[-16:]


def _parse_tempkey(encrypted: bytes, passcode: bytes) -> Optional[bytes]:
    """Parse Telegram Desktop .tempkeyEncrypted -> dbKey + dbSalt."""
    if len(encrypted) % 16 != 0:
        return None

    aes_key, aes_iv = _tempkey_kdf(passcode)
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_iv)
    data = cipher.decrypt(encrypted)
    if len(data) < 52:
        return None

    db_key = data[:32]
    db_salt = data[32:48]
    db_hash = int.from_bytes(data[48:52], byteorder="little", signed=True)
    db_pad = data[52:]

    calc_hash = murmur_hash(db_key + db_salt, seed=TEMPKEY_MURMUR_SEED)
    if db_hash != calc_hash:
        return None

    if db_pad and any(db_pad):
        # Non-zero padding is unexpected but not necessarily fatal.
        pass

    return db_key + db_salt


def _valid_local_key(candidate: bytes) -> bool:
    if not candidate:
        return False
    if all(b == 0 for b in candidate):
        return False
    return 16 <= len(candidate) <= 64


def _decrypt_key_cbc(encrypted: bytes, passcode: bytes) -> Optional[bytes]:
    if len(encrypted) < 32:
        return None
    key = hashlib.sha512(passcode).digest()[:32]
    iv = encrypted[:16]
    payload = encrypted[16:]
    if len(payload) % 16 != 0:
        return None
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(payload)

    padding_length = decrypted[-1]
    if padding_length <= 0 or padding_length > 16:
        return None
    if decrypted[-padding_length:] != bytes([padding_length]) * padding_length:
        return None

    local_key = decrypted[:-padding_length]
    return local_key if _valid_local_key(local_key) else None


def _decrypt_key_ige(encrypted: bytes, passcode: bytes) -> Optional[bytes]:
    if len(encrypted) < 64:
        return None
    key = hashlib.sha512(passcode).digest()[:32]
    iv = encrypted[:32]
    payload = encrypted[32:]
    if len(payload) % 16 != 0:
        return None

    if hasattr(AES, "MODE_IGE"):
        cipher = AES.new(key, AES.MODE_IGE, iv)
        decrypted = cipher.decrypt(payload)
        return decrypted if _valid_local_key(decrypted) else None

    decrypted = _decrypt_ige_fallback(key, iv, payload)
    return decrypted if _valid_local_key(decrypted) else None


def _decrypt_ige_fallback(key: bytes, iv: bytes, payload: bytes) -> bytes:
    ecb = AES.new(key, AES.MODE_ECB)
    c_prev = iv[:16]
    p_prev = iv[16:]
    out = bytearray()
    for offset in range(0, len(payload), 16):
        c_block = payload[offset : offset + 16]
        xored = bytes(a ^ b for a, b in zip(c_block, p_prev))
        y = ecb.decrypt(xored)
        p_block = bytes(a ^ b for a, b in zip(y, c_prev))
        out.extend(p_block)
        c_prev = c_block
        p_prev = p_block
    return bytes(out)


def decrypt_local_key(key_path: Path, passcodes: Iterable[bytes]) -> Optional[bytes]:
    """Attempt legacy CBC/IGE decryption for .tempkeyEncrypted."""
    encrypted = key_path.read_bytes()
    for passcode in passcodes:
        local_key = _decrypt_key_cbc(encrypted, passcode)
        if local_key:
            return local_key
        local_key = _decrypt_key_ige(encrypted, passcode)
        if local_key:
            return local_key
    return None


def _derive_sqlcipher_keys(local_key: bytes) -> list[KeyCandidate]:
    key_hash = hashlib.sha1(local_key).digest() + b"\x00" * 12
    seeds = _seed_variants(local_key)

    candidates: list[KeyCandidate] = []
    for seed_name, seed in seeds:
        bytes_key = _murmur_bytes_key(key_hash, seed)
        candidates.append(KeyCandidate(f"mmh3-bytes-{seed_name}", bytes_key.hex()))

        hash_key = _murmur_hash_key(key_hash, seed)
        candidates.append(KeyCandidate(f"mmh3-hash-{seed_name}", hash_key.hex()))

    candidates.append(KeyCandidate("sha1-raw", key_hash.hex()))
    candidates.append(KeyCandidate("local-key-hex", local_key.hex()))
    return candidates


def _seed_variants(local_key: bytes) -> list[tuple[str, int]]:
    return [
        ("le-signed", int.from_bytes(local_key[:4], "little", signed=True)),
        ("le-unsigned", int.from_bytes(local_key[:4], "little", signed=False)),
        ("be-signed", int.from_bytes(local_key[:4], "big", signed=True)),
        ("be-unsigned", int.from_bytes(local_key[:4], "big", signed=False)),
    ]


def _murmur_bytes_key(key_hash: bytes, seed: int) -> bytes:
    encrypted_key = bytearray()
    for offset in range(0, len(key_hash), 4):
        chunk = key_hash[offset : offset + 4]
        hashed = murmur_hash_bytes(chunk, seed=seed)[:4]
        encrypted_key.extend(hashed)
    return bytes(encrypted_key)


def _murmur_hash_key(key_hash: bytes, seed: int) -> bytes:
    encrypted_key = bytearray()
    for offset in range(0, len(key_hash), 4):
        chunk = key_hash[offset : offset + 4]
        hashed = murmur_hash(chunk, seed=seed)
        encrypted_key.extend(struct.pack("<i", hashed))
    return bytes(encrypted_key)


def derive_key_candidates(
    key_path: Path, passcodes: Iterable[bytes]
) -> KeyDerivationInfo:
    """Derive SQLCipher key candidates from a tempkey file."""
    encrypted = key_path.read_bytes()
    candidates: list[KeyCandidate] = []
    tempkey_ok = False

    if len(encrypted) == 48:
        tempkey_ok = True
        candidates.append(KeyCandidate("raw-48-tempkey", encrypted.hex()))

    for passcode in passcodes:
        parsed = _parse_tempkey(encrypted, passcode)
        if parsed:
            tempkey_ok = True
            candidates.append(KeyCandidate("tempkey", parsed.hex()))

    local_key = decrypt_local_key(key_path, passcodes)
    if local_key:
        candidates.extend(_derive_sqlcipher_keys(local_key))

    return KeyDerivationInfo(tuple(candidates), tempkey_ok, local_key)


def build_profiles() -> list[SqlCipherProfile]:
    """Return a list of SQLCipher profiles to try."""
    return [
        SqlCipherProfile("sqlcipher3-default", 3, {}, False),
        SqlCipherProfile(
            "sqlcipher3-legacy",
            3,
            {
                "cipher_page_size": 4096,
                "kdf_iter": 4000,
                "cipher_hmac_algorithm": "HMAC_SHA1",
                "cipher_kdf_algorithm": "PBKDF2_HMAC_SHA1",
            },
            True,
        ),
        SqlCipherProfile("sqlcipher4-default", 4, {}, False),
        SqlCipherProfile(
            "sqlcipher4-legacy",
            4,
            {"cipher_page_size": 4096},
            True,
        ),
        SqlCipherProfile(
            "sqlcipher4-rawkey-hmac",
            4,
            {
                "kdf_iter": 1,
                "cipher_hmac_algorithm": "HMAC_SHA512",
                "cipher_kdf_algorithm": "PBKDF2_HMAC_SHA512",
            },
            False,
        ),
        SqlCipherProfile(
            "sqlcipher4-rawkey-hmac-plainhdr",
            4,
            {
                "kdf_iter": 1,
                "cipher_hmac_algorithm": "HMAC_SHA512",
                "cipher_kdf_algorithm": "PBKDF2_HMAC_SHA512",
                "cipher_plaintext_header_size": 32,
                "cipher_default_plaintext_header_size": 32,
            },
            False,
        ),
        SqlCipherProfile(
            "sqlcipher4-rawkey-nohmac",
            4,
            {"kdf_iter": 1, "cipher_use_hmac": "OFF"},
            False,
        ),
        SqlCipherProfile(
            "sqlcipher3-rawkey-nohmac",
            3,
            {
                "kdf_iter": 1,
                "cipher_use_hmac": "OFF",
                "cipher_hmac_algorithm": "HMAC_SHA1",
                "cipher_kdf_algorithm": "PBKDF2_HMAC_SHA1",
            },
            False,
        ),
    ]


def _apply_pragmas(conn, pragmas: dict[str, str | int]) -> None:
    for name, value in pragmas.items():
        conn.execute(f"PRAGMA {name} = {value}")


def _open_with_profile(
    db_path: Path, candidate: KeyCandidate, profile: SqlCipherProfile
):
    if SQLCIPHER is None:
        raise SystemExit(
            "Missing dependency: sqlcipher3 (or pysqlcipher3). Install it to decrypt."
        )
    conn = SQLCIPHER.connect(str(db_path))
    if profile.compat is not None and profile.compat_before_key:
        conn.execute(f"PRAGMA cipher_compatibility = {profile.compat}")
    if profile.pragmas:
        _apply_pragmas(conn, profile.pragmas)
    conn.execute(f"PRAGMA key=\"x'{candidate.hex_value}'\"")
    if profile.compat is not None and not profile.compat_before_key:
        conn.execute(f"PRAGMA cipher_compatibility = {profile.compat}")
    db_error = getattr(SQLCIPHER, "DatabaseError", RuntimeError)
    try:
        conn.execute("SELECT count(*) FROM sqlite_master")
        return conn
    except db_error:
        conn.close()
        return None


def open_sqlcipher_connection(
    db_path: Path,
    candidates: Iterable[KeyCandidate],
    profiles: Iterable[SqlCipherProfile],
) -> Optional[SqlCipherMatch]:
    """Attempt to open the encrypted database with candidate keys."""
    for candidate in candidates:
        for profile in profiles:
            conn = _open_with_profile(db_path, candidate, profile)
            if conn is not None:
                return SqlCipherMatch(conn, candidate, profile)
    return None


def export_plaintext_db(conn, out_path: Path) -> None:
    """Export an encrypted SQLCipher DB to a plaintext SQLite file."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()
    out_path_sql = str(out_path).replace("'", "''")
    conn.execute("PRAGMA cipher_plaintext_header_size = 0")
    conn.execute("PRAGMA cipher_default_plaintext_header_size = 0")
    conn.execute(f"ATTACH DATABASE '{out_path_sql}' AS plaintext KEY ''")
    conn.execute("SELECT sqlcipher_export('plaintext')")
    conn.execute("DETACH DATABASE plaintext")


def decrypt_database(
    key_path: Path,
    db_path: Path,
    out_path: Path,
    passcodes: Iterable[bytes],
) -> DecryptResult:
    """Decrypt an encrypted Telegram database into a plaintext SQLite DB."""
    key_info = derive_key_candidates(key_path, passcodes)
    if not key_info.candidates:
        raise SystemExit("Unable to derive any key material from .tempkeyEncrypted.")

    match = open_sqlcipher_connection(db_path, key_info.candidates, build_profiles())
    if match is None:
        raise SystemExit("Failed to decrypt database. Check passcode and key file.")

    export_plaintext_db(match.connection, out_path)
    match.connection.close()
    return DecryptResult(key_info, match)
