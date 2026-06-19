"""Path discovery helpers for native Telegram for macOS storage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

TELEGRAM_CONTAINER = "6N38VWS5BX.ru.keepcoder.Telegram"


@dataclass(frozen=True)
class DiscoveredAccount:
    """Useful paths below one Telegram account directory."""

    account_dir: Path
    db_path: Optional[Path]
    media_dir: Optional[Path]


@dataclass(frozen=True)
class TelegramPathDiscovery:
    """Useful paths below a Telegram storage root."""

    root: Path
    encrypted_key_path: Optional[Path]
    raw_key_path: Optional[Path]
    accounts: tuple[DiscoveredAccount, ...]


def default_telegram_root() -> Path:
    """Return the normal native Telegram for macOS stable storage root."""
    return Path.home() / "Library" / "Group Containers" / TELEGRAM_CONTAINER / "stable"


def discover_telegram_paths(root: Optional[Path] = None) -> TelegramPathDiscovery:
    """Discover bounded Telegram key, database, and media paths."""
    root_path = (root or default_telegram_root()).expanduser()
    encrypted_key = _existing_file(root_path / ".tempkeyEncrypted")
    raw_key = _existing_file(root_path / ".tempkey")
    accounts = []

    for account_dir in sorted(root_path.glob("account-*")):
        if not account_dir.is_dir():
            continue
        postbox_dir = account_dir / "postbox"
        accounts.append(
            DiscoveredAccount(
                account_dir=account_dir,
                db_path=_existing_file(postbox_dir / "db" / "db_sqlite"),
                media_dir=_existing_dir(postbox_dir / "media"),
            )
        )

    return TelegramPathDiscovery(
        root=root_path,
        encrypted_key_path=encrypted_key,
        raw_key_path=raw_key,
        accounts=tuple(accounts),
    )


def _existing_file(path: Path) -> Optional[Path]:
    return path if path.is_file() else None


def _existing_dir(path: Path) -> Optional[Path]:
    return path if path.is_dir() else None
