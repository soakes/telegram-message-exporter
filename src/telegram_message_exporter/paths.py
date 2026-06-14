"""Path discovery helpers for Telegram local dumps."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


CONTAINER_NAME = "6N38VWS5BX.ru.keepcoder.Telegram"


@dataclass(frozen=True)
class DiscoveredAccount:
    """Detected Telegram account storage paths."""

    account_dir: Path
    message_db: Optional[Path]
    media_root: Optional[Path]
    media_storage_db: Optional[Path]
    media_cache_db: Optional[Path]


@dataclass(frozen=True)
class DumpDiscovery:
    """Detected Telegram dump paths."""

    root: Path
    key_path: Optional[Path]
    accounts: tuple[DiscoveredAccount, ...]


def discover_dump(root: Optional[Path] = None) -> DumpDiscovery:
    """Discover Telegram native macOS storage paths below a dump root."""
    root_path = _resolve_dump_root(root)
    app_root = _find_app_root(root_path)
    key_path = app_root / ".tempkeyEncrypted"
    accounts = []

    for account_dir in sorted(app_root.glob("account-*")):
        if not account_dir.is_dir():
            continue
        media_root = account_dir / "postbox" / "media"
        accounts.append(
            DiscoveredAccount(
                account_dir=account_dir,
                message_db=_existing(account_dir / "postbox" / "db" / "db_sqlite"),
                media_root=_existing(media_root),
                media_storage_db=_existing(media_root / "storage" / "db" / "db_sqlite"),
                media_cache_db=_existing(
                    media_root / "cache-storage" / "db" / "db_sqlite"
                ),
            )
        )

    return DumpDiscovery(
        root=app_root,
        key_path=_existing(key_path),
        accounts=tuple(accounts),
    )


def discover_media_roots(root: Optional[Path] = None) -> tuple[Path, ...]:
    """Return media roots from a detected Telegram dump."""
    discovery = discover_dump(root)
    return tuple(
        account.media_root for account in discovery.accounts if account.media_root
    )


def write_source_context(plaintext_db: Path, source_db: Path) -> None:
    """Write source path metadata next to a decrypted database."""
    account_dir = _account_dir_from_db(source_db)
    media_roots = []
    if account_dir:
        media_root = account_dir / "postbox" / "media"
        if media_root.exists():
            media_roots.append(_portable_path(media_root))
    payload = {
        "source_db": _portable_path(source_db),
        "media_roots": media_roots,
    }
    context_path(plaintext_db).write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def media_roots_from_context(plaintext_db: Path) -> tuple[Path, ...]:
    """Read media roots recorded next to a decrypted database."""
    path = context_path(plaintext_db)
    if not path.exists():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    return tuple(
        Path(value).expanduser()
        for value in payload.get("media_roots", [])
        if isinstance(value, str) and Path(value).expanduser().exists()
    )


def context_path(plaintext_db: Path) -> Path:
    """Return sidecar path for decrypted DB source metadata."""
    return plaintext_db.with_name(f"{plaintext_db.name}.sources.json")


def _account_dir_from_db(source_db: Path) -> Optional[Path]:
    parts = source_db.parts
    if len(parts) < 3:
        return None
    if parts[-3:] != ("postbox", "db", "db_sqlite"):
        return None
    return source_db.parent.parent.parent


def _resolve_dump_root(root: Optional[Path]) -> Path:
    if root:
        return root.expanduser()
    env_root = os.environ.get("TG_EXPORTER_DUMP_ROOT")
    if env_root:
        return Path(env_root).expanduser()

    group_container = Path.home() / "Library" / "Group Containers" / CONTAINER_NAME
    for child in ("stable", "appstore"):
        candidate = group_container / child
        if candidate.exists():
            return candidate
    return group_container / "stable"


def _find_app_root(root: Path) -> Path:
    if (root / ".tempkeyEncrypted").exists() or list(root.glob("account-*")):
        return root
    for child in ("appstore", "stable"):
        candidate = root / child
        if _looks_like_app_root(candidate):
            return candidate
    for child in ("appstore", "stable"):
        candidate = root / CONTAINER_NAME / child
        if _looks_like_app_root(candidate):
            return candidate
    return root


def _looks_like_app_root(path: Path) -> bool:
    return (path / ".tempkeyEncrypted").exists() or bool(list(path.glob("account-*")))


def _existing(path: Path) -> Optional[Path]:
    return path if path.exists() else None


def _portable_path(path: Path) -> str:
    try:
        return f"~/{path.expanduser().resolve().relative_to(Path.home()).as_posix()}"
    except (OSError, ValueError):
        return str(path)
