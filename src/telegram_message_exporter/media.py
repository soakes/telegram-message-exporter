"""Local media export helpers."""

from __future__ import annotations

import mimetypes
import os
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Optional

from .models import Attachment, Message


@dataclass(frozen=True)
class MediaExportReport:
    """Summary of local media copy results."""

    copied: int
    missing: int
    media_dir: Optional[Path]


class MediaIndex:
    """Filename index for a Telegram cache/media directory."""

    def __init__(self, roots: Iterable[Path]) -> None:
        self.by_name: dict[str, list[Path]] = {}
        for root in roots:
            self._add_root(root)

    def _add_root(self, root: Path) -> None:
        if not root.exists():
            return
        for dirpath, _, filenames in os.walk(root, onerror=lambda _: None):
            current = Path(dirpath)
            for filename in filenames:
                path = current / filename
                self.by_name.setdefault(filename, []).append(path)

    def match(self, names: Iterable[str], size: Optional[int]) -> Optional[Path]:
        """Return the best local file match for the given candidate names."""
        for name in names:
            for path in self.by_name.get(name, []):
                if _size_matches(path, size):
                    return path
        for name in names:
            matches = self.by_name.get(name, [])
            if matches:
                return matches[0]
        return None


def copy_message_media(
    messages: list[Message],
    out_path: Path,
    media_root: Optional[Path] = None,
    media_dir: Optional[Path] = None,
) -> tuple[list[Message], MediaExportReport]:
    """Copy locally available media attachments next to the export file."""
    roots = [media_root.expanduser()] if media_root else []
    index = MediaIndex(roots)
    target_dir = media_dir.expanduser() if media_dir else _default_media_dir(out_path)

    copied = 0
    missing = 0
    copied_by_source: dict[Path, str] = {}
    updated_messages: list[Message] = []

    for message_index, message in enumerate(messages, start=1):
        updated_attachments: list[Attachment] = []
        for attachment_index, attachment in enumerate(message.attachments, start=1):
            source = _resolve_attachment_source(attachment, roots, index)
            if source is None:
                missing += 1
                updated_attachments.append(attachment)
                continue

            source_key = source.resolve()
            copied_path = copied_by_source.get(source_key)
            if copied_path is None:
                target_dir.mkdir(parents=True, exist_ok=True)
                file_name = _export_file_name(
                    attachment,
                    source,
                    message_index,
                    attachment_index,
                )
                target = _unique_target_path(
                    target_dir,
                    file_name,
                )
                shutil.copy2(source, target)
                copied_path = _relative_path(target, out_path.parent)
                copied_by_source[source_key] = copied_path
                copied += 1

            updated_attachments.append(
                replace(
                    attachment,
                    copied_path=copied_path,
                    source_path=attachment.source_path or str(source),
                )
            )
        updated_messages.append(
            replace(message, attachments=tuple(updated_attachments))
        )

    report_dir = target_dir if copied else None
    return updated_messages, MediaExportReport(copied, missing, report_dir)


def _default_media_dir(out_path: Path) -> Path:
    return out_path.with_name(f"{out_path.stem}_media")


def _resolve_attachment_source(
    attachment: Attachment, roots: list[Path], index: MediaIndex
) -> Optional[Path]:
    source_path = _path_from_attachment(attachment)
    if source_path and source_path.is_file():
        return source_path

    if source_path and not source_path.is_absolute():
        for root in roots:
            candidate = root / source_path
            if candidate.is_file():
                return candidate

    return index.match(_candidate_names(attachment), attachment.size)


def _path_from_attachment(attachment: Attachment) -> Optional[Path]:
    if not attachment.source_path:
        return None
    return Path(attachment.source_path).expanduser()


def _candidate_names(attachment: Attachment) -> tuple[str, ...]:
    names: list[str] = []
    if attachment.file_name:
        names.append(Path(attachment.file_name).name)
    if attachment.source_path:
        names.append(Path(attachment.source_path).name)
    names.extend(key for key in attachment.resource_keys if key)
    return tuple(dict.fromkeys(names))


def _size_matches(path: Path, size: Optional[int]) -> bool:
    if size is None:
        return True
    try:
        return path.stat().st_size == size
    except OSError:
        return False


def _export_file_name(
    attachment: Attachment,
    source: Path,
    message_index: int,
    attachment_index: int,
) -> str:
    preferred = attachment.file_name or source.name
    if not preferred or preferred == ".":
        preferred = f"attachment_{message_index}_{attachment_index}"
    safe_name = _safe_file_name(preferred)
    if "." not in safe_name:
        safe_name += _extension_for_attachment(attachment, source)
    return safe_name


def _safe_file_name(value: str) -> str:
    cleaned = "".join(
        "_" if char in '/\\:\0' or ord(char) < 32 else char for char in value.strip()
    )
    cleaned = cleaned.strip(". ")
    return cleaned or "attachment"


def _extension_for_attachment(attachment: Attachment, source: Path) -> str:
    if source.suffix:
        return source.suffix
    if attachment.mime_type:
        return mimetypes.guess_extension(attachment.mime_type) or ""
    return ""


def _unique_target_path(target_dir: Path, file_name: str) -> Path:
    candidate = target_dir / file_name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while True:
        candidate = target_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _relative_path(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return str(path)
