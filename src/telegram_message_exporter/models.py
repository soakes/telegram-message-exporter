"""Data models for exports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Attachment:  # pylint: disable=too-many-instance-attributes
    """Normalized media attachment associated with a message."""

    kind: str
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    cache_key: Optional[str] = None
    alternate_cache_keys: tuple[str, ...] = ()
    source_path: Optional[str] = None
    exported_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    url: Optional[str] = None


@dataclass(frozen=True)
class ForwardInfo:  # pylint: disable=too-many-instance-attributes
    """Original-message metadata attached to a forwarded message."""

    author_id: Optional[int]
    source_id: Optional[int]
    source_message_peer_id: Optional[int]
    source_message_namespace: Optional[int]
    source_message_id: Optional[int]
    date: Optional[datetime]
    author_signature: Optional[str]
    psa_type: Optional[str]
    is_imported: bool = False


@dataclass(frozen=True)
class Message:
    """Normalized message representation used by exporters."""

    timestamp: Optional[datetime]
    text: str
    outgoing: Optional[bool]
    peer_id: Optional[int]
    author_id: Optional[int]
    attachments: tuple[Attachment, ...] = ()
    forward_info: Optional[ForwardInfo] = None

    def speaker_hint(self) -> str:
        """Return a concise label for direction when no names are available."""
        if self.outgoing is True:
            return "out"
        if self.outgoing is False:
            return "in"
        return "unknown"
