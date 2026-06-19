from __future__ import annotations

from pathlib import Path

from telegram_message_exporter.crypto import (
    AES,
    DEFAULT_PASSCODE,
    _decrypt_key_cbc,
    _tempkey_kdf,
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


def _build_tempkey_encrypted(key_material: bytes, passcode: bytes) -> bytes:
    db_hash = murmur_hash(key_material, seed=TEMPKEY_MURMUR_SEED)
    payload = key_material + db_hash.to_bytes(4, byteorder="little", signed=True)
    payload += b"\x00" * (16 - len(payload) % 16)
    aes_key, aes_iv = _tempkey_kdf(passcode)
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_iv)
    return cipher.encrypt(payload)
