from __future__ import annotations

import os

import pytest

from telegram_message_exporter.paths import discover_telegram_paths


def test_discover_telegram_paths_finds_account_storage(tmp_path) -> None:
    root = tmp_path / "stable"
    account_dir = root / "account-123" / "postbox"
    db_dir = account_dir / "db"
    media_dir = account_dir / "media"
    db_dir.mkdir(parents=True)
    media_dir.mkdir()
    encrypted_key = root / ".tempkeyEncrypted"
    raw_key = root / ".tempkey"
    db_path = db_dir / "db_sqlite"
    encrypted_key.write_bytes(b"encrypted")
    raw_key.write_bytes(b"raw")
    db_path.write_bytes(b"db")

    discovery = discover_telegram_paths(root)

    assert discovery.root == root
    assert discovery.encrypted_key_path == encrypted_key
    assert discovery.raw_key_path == raw_key
    assert len(discovery.accounts) == 1
    assert discovery.accounts[0].account_dir == root / "account-123"
    assert discovery.accounts[0].db_path == db_path
    assert discovery.accounts[0].media_dir == media_dir


def test_discover_telegram_paths_reports_missing_optional_paths(tmp_path) -> None:
    account_dir = tmp_path / "account-1"
    account_dir.mkdir()

    discovery = discover_telegram_paths(tmp_path)

    assert discovery.encrypted_key_path is None
    assert discovery.raw_key_path is None
    assert len(discovery.accounts) == 1
    assert discovery.accounts[0].db_path is None
    assert discovery.accounts[0].media_dir is None


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_discover_telegram_paths_raises_when_root_cannot_be_listed(tmp_path) -> None:
    root = tmp_path / "stable"
    (root / "account-123").mkdir(parents=True)
    (root / ".tempkeyEncrypted").write_bytes(b"encrypted")
    # Like the macOS privacy block: entries can be stat'd but not listed.
    root.chmod(0o300)
    try:
        with pytest.raises(PermissionError):
            discover_telegram_paths(root)
    finally:
        root.chmod(0o700)


def test_discover_telegram_paths_tolerates_missing_root(tmp_path) -> None:
    discovery = discover_telegram_paths(tmp_path / "missing")

    assert discovery.encrypted_key_path is None
    assert discovery.accounts == ()
