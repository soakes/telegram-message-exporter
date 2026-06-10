"""Data models for exports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Attachment:
    """Normalized media/file attachment representation."""

    kind: str
    title: str
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    size: Optional[int] = None
    source_path: Optional[str] = None
    copied_path: Optional[str] = None
    reference: Optional[str] = None
    resource_keys: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PeerInfo:
    """Display metadata for a Telegram peer."""

    peer_id: int
    title: str
    kind: str = "unknown"


@dataclass(frozen=True)
class Message:
    """Normalized message representation used by exporters."""

    timestamp: Optional[datetime]
    text: str
    outgoing: Optional[bool]
    peer_id: Optional[int]
    author_id: Optional[int]
    attachments: tuple[Attachment, ...] = field(default_factory=tuple)

    def speaker_hint(self) -> str:
        """Return a concise label for direction when no names are available."""
        if self.outgoing is True:
            return "out"
        if self.outgoing is False:
            return "in"
        return "unknown"
