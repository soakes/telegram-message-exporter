from __future__ import annotations

import hashlib
import shutil
import sqlite3
from pathlib import Path

import pytest

from telegram_message_exporter.crypto import (
    AES,
    DEFAULT_PASSCODE,
    SQLCIPHER,
    _decrypt_key_cbc,
    _tempkey_kdf,
    decrypt_database,
    derive_key_candidates,
)
from telegram_message_exporter.hashing import TEMPKEY_MURMUR_SEED, murmur_hash


def test_derive_key_candidates_accepts_raw_48_byte_tempkey(tmp_path: Path) -> None:
    raw_key = bytes(range(48))
    key_path = tmp_path / ".tempkey"
    key_path.write_bytes(raw_key)

    info = derive_key_candidates(key_path, [DEFAULT_PASSCODE])

    assert info.tempkey_ok is True
    assert info.candidates[0].name == "raw-48-tempkey"
    assert info.candidates[0].hex_value == raw_key.hex()


def test_decrypt_key_cbc_rejects_non_block_payload() -> None:
    encrypted = b"0" * 33

    assert _decrypt_key_cbc(encrypted, DEFAULT_PASSCODE) is None


def test_derive_key_candidates_preserves_encrypted_tempkey_parse(
    tmp_path: Path,
) -> None:
    db_key = bytes(range(32))
    db_salt = bytes(range(32, 48))
    encrypted = _build_tempkey_encrypted(db_key + db_salt, DEFAULT_PASSCODE)
    key_path = tmp_path / ".tempkeyEncrypted"
    key_path.write_bytes(encrypted)

    info = derive_key_candidates(key_path, [DEFAULT_PASSCODE])

    assert info.tempkey_ok is True
    assert ("tempkey", (db_key + db_salt).hex()) in {
        (candidate.name, candidate.hex_value) for candidate in info.candidates
    }


@pytest.mark.parametrize("keep_wal", [True, False])
def test_decrypt_database_leaves_source_untouched(
    tmp_path: Path, keep_wal: bool
) -> None:
    raw_key = bytes(range(48))
    key_path = tmp_path / ".tempkey"
    key_path.write_bytes(raw_key)
    source_dir = tmp_path / "db"
    _build_encrypted_database(tmp_path / "live", source_dir, raw_key, keep_wal)
    before = _file_hashes(source_dir)
    out_path = tmp_path / "plaintext.db"

    decrypt_database(key_path, source_dir / "db_sqlite", out_path, [DEFAULT_PASSCODE])

    assert _file_hashes(source_dir) == before
    with sqlite3.connect(out_path) as conn:
        assert conn.execute("SELECT value FROM t").fetchall() == [("newest",)]


def _build_encrypted_database(
    live_dir: Path, source_dir: Path, raw_key: bytes, keep_wal: bool
) -> None:
    """Write a WAL-mode database whose newest row is only in -wal if keep_wal."""
    live_dir.mkdir()
    source_dir.mkdir()
    conn = SQLCIPHER.connect(str(live_dir / "db_sqlite"))
    conn.execute(f"PRAGMA key=\"x'{raw_key.hex()}'\"")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("CREATE TABLE t(value)")
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("INSERT INTO t VALUES ('newest')")
    conn.commit()
    if keep_wal:
        # Copy while the connection is open, as a running Telegram leaves it.
        for name in ("db_sqlite", "db_sqlite-wal"):
            shutil.copyfile(live_dir / name, source_dir / name)
        conn.close()
    else:
        conn.close()
        shutil.copyfile(live_dir / "db_sqlite", source_dir / "db_sqlite")


def _file_hashes(directory: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.iterdir())
    }


def _build_tempkey_encrypted(key_material: bytes, passcode: bytes) -> bytes:
    db_hash = murmur_hash(key_material, seed=TEMPKEY_MURMUR_SEED)
    payload = key_material + db_hash.to_bytes(4, byteorder="little", signed=True)
    payload += b"\x00" * (16 - len(payload) % 16)
    aes_key, aes_iv = _tempkey_kdf(passcode)
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_iv)
    return cipher.encrypt(payload)
