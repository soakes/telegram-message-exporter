"""Data models for exports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Attachment:  # pylint: disable=too-many-instance-attributes
    """Normalized media attachment associated with a message."""

    kind: str
    filename: str | None = None
    mime_type: str | None = None
    cache_key: str | None = None
    alternate_cache_keys: tuple[str, ...] = ()
    source_path: str | None = None
    exported_path: str | None = None
    width: int | None = None
    height: int | None = None
    url: str | None = None


@dataclass(frozen=True)
class ForwardInfo:  # pylint: disable=too-many-instance-attributes
    """Original-message metadata attached to a forwarded message."""

    author_id: int | None
    source_id: int | None
    source_message_peer_id: int | None
    source_message_namespace: int | None
    source_message_id: int | None
    date: datetime | None
    author_signature: str | None
    psa_type: str | None
    is_imported: bool = False


@dataclass(frozen=True)
class Message:
    """Normalized message representation used by exporters."""

    timestamp: datetime | None
    text: str
    outgoing: bool | None
    peer_id: int | None
    author_id: int | None
    attachments: tuple[Attachment, ...] = ()
    forward_info: ForwardInfo | None = None

    def speaker_hint(self) -> str:
        """Return a concise label for direction when no names are available."""
        if self.outgoing is True:
            return "out"
        if self.outgoing is False:
            return "in"
        return "unknown"
