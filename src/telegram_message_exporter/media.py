"""Local media export helpers."""

from __future__ import annotations

import mimetypes
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Iterable, Optional

from .models import Attachment, Message, PeerInfo

ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class MediaExportReport:
    """Summary of local media copy results."""

    copied: int
    missing: int
    media_dir: Optional[Path]
    avatars_copied: int = 0
    avatars_missing: int = 0


@dataclass(frozen=True)
class CopyTask:
    """One physical file copy planned for export."""

    source_key: Path
    source: Path
    target: Path


ResolvedAttachment = tuple[Attachment, Optional[Path], Optional[Path]]


class MediaIndex:
    """Filename index for a Telegram cache/media directory."""

    def __init__(
        self,
        roots: Iterable[Path],
        progress: Optional[ProgressCallback] = None,
    ) -> None:
        self.by_name: dict[str, list[Path]] = {}
        self.by_token: dict[str, list[Path]] = {}
        self.best_by_name: dict[str, list[Path]] = {}
        self.best_by_token: dict[str, list[Path]] = {}
        self.indexed_files = 0
        for root in roots:
            self._add_root(root, progress)

    def _add_root(
        self,
        root: Path,
        progress: Optional[ProgressCallback],
    ) -> None:
        if not root.exists():
            return
        if progress:
            progress(f"Indexing media root: {root}")
        for dirpath, _, filenames in os.walk(root, onerror=lambda _: None):
            current = Path(dirpath)
            for filename in filenames:
                path = current / filename
                if not _is_indexable_media_file(path) or not _is_copyable_file(path):
                    continue
                self.by_name.setdefault(filename, []).append(path)
                if _looks_like_telegram_media_name(filename):
                    for token in _resource_tokens(filename):
                        self.by_token.setdefault(token, []).append(path)
                self.indexed_files += 1
                if progress and self.indexed_files % 25000 == 0:
                    progress(f"Indexed {self.indexed_files} media files")

    def match(self, names: Iterable[str], size: Optional[int]) -> Optional[Path]:
        """Return the best local file match for the given candidate names."""
        candidate_names = tuple(dict.fromkeys(name for name in names if name))
        for name in names:
            for path in self._best_name_paths(name):
                if _size_matches(path, size):
                    return path
        for name in candidate_names:
            matches = self._best_name_paths(name)
            if matches:
                return matches[0]
        token_match = self._match_tokens(candidate_names, size)
        if token_match:
            return token_match
        return None

    def _match_tokens(
        self, names: Iterable[str], size: Optional[int]
    ) -> Optional[Path]:
        tokens = _strong_tokens(names)
        if not tokens:
            return None
        first_token = tokens[0]
        candidates = self._best_token_paths(first_token)
        for path in candidates:
            filename_tokens = _resource_tokens(path.name)
            if not all(token in filename_tokens for token in tokens[1:]):
                continue
            if _size_matches(path, size):
                return path
        for path in candidates:
            filename_tokens = _resource_tokens(path.name)
            if all(token in filename_tokens for token in tokens[1:]):
                return path
        return None

    def _best_name_paths(self, name: str) -> list[Path]:
        cached = self.best_by_name.get(name)
        if cached is None:
            cached = _best_paths(self.by_name.get(name, []))
            self.best_by_name[name] = cached
        return cached

    def _best_token_paths(self, token: str) -> list[Path]:
        cached = self.best_by_token.get(token)
        if cached is None:
            cached = _best_paths(self.by_token.get(token, []))
            self.best_by_token[token] = cached
        return cached


def copy_message_media(
    messages: list[Message],
    out_path: Path,
    media_root: Optional[Path] = None,
    media_roots: Optional[Iterable[Path]] = None,
    media_dir: Optional[Path] = None,
    progress: Optional[ProgressCallback] = None,
    media_workers: Optional[int] = None,
) -> tuple[list[Message], MediaExportReport]:
    """Copy locally available media attachments next to the export file."""
    updated_messages, _, report = copy_export_media(
        messages,
        out_path,
        media_root=media_root,
        media_roots=media_roots,
        media_dir=media_dir,
        progress=progress,
        media_workers=media_workers,
    )
    return updated_messages, report


def copy_export_media(
    messages: list[Message],
    out_path: Path,
    media_root: Optional[Path] = None,
    media_roots: Optional[Iterable[Path]] = None,
    media_dir: Optional[Path] = None,
    peer_info: Optional[dict[int, PeerInfo]] = None,
    progress: Optional[ProgressCallback] = None,
    media_workers: Optional[int] = None,
) -> tuple[list[Message], Optional[dict[int, PeerInfo]], MediaExportReport]:
    """Copy message media and peer avatars next to the export file."""
    roots = []
    if media_root:
        roots.append(media_root.expanduser())
    if media_roots:
        roots.extend(root.expanduser() for root in media_roots)
    roots = list(dict.fromkeys(roots))
    target_dir = media_dir.expanduser() if media_dir else _default_media_dir(out_path)
    exported_peer_ids = {msg.peer_id for msg in messages if msg.peer_id is not None}
    needs_index = _needs_media_index(messages, peer_info, exported_peer_ids)
    index = MediaIndex(roots if needs_index else (), progress=progress)
    if progress and roots:
        progress(f"Indexed {index.indexed_files} media files total")

    updated_messages, copied, missing, copied_by_source = _copy_message_attachments(
        messages,
        out_path,
        roots,
        index,
        target_dir,
        progress=progress,
        media_workers=media_workers,
    )
    updated_peer_info, avatars_copied, avatars_missing = _copy_peer_avatars(
        peer_info,
        out_path,
        index,
        target_dir,
        copied_by_source,
        exported_peer_ids,
        progress=progress,
    )

    report_dir = target_dir if copied or avatars_copied else None
    return (
        updated_messages,
        updated_peer_info,
        MediaExportReport(
            copied=copied,
            missing=missing,
            media_dir=report_dir,
            avatars_copied=avatars_copied,
            avatars_missing=avatars_missing,
        ),
    )


def _needs_media_index(
    messages: list[Message],
    peer_info: Optional[dict[int, PeerInfo]],
    exported_peer_ids: set[int],
) -> bool:
    for message in messages:
        for attachment in message.attachments:
            if _candidate_names(attachment):
                return True
    if peer_info:
        for peer_id in exported_peer_ids:
            info = peer_info.get(peer_id)
            if info and info.avatar_resource_keys:
                return True
    return False


def _copy_message_attachments(
    messages: list[Message],
    out_path: Path,
    roots: list[Path],
    index: MediaIndex,
    target_dir: Path,
    progress: Optional[ProgressCallback] = None,
    media_workers: Optional[int] = None,
) -> tuple[list[Message], int, int, dict[Path, str]]:
    """Copy message attachments using a prepared media index."""

    copied_by_source: dict[Path, str] = {}
    copy_tasks: list[CopyTask] = []
    resolved_messages: list[tuple[int, list[ResolvedAttachment]]] = []
    total_messages = len(messages)

    for message_index, message in enumerate(messages, start=1):
        if progress and message_index % 10000 == 0:
            progress(f"Resolved media for {message_index}/{total_messages} messages")
        if not message.attachments:
            continue
        resolved_attachments = []
        for attachment_index, attachment in enumerate(message.attachments, start=1):
            source = _resolve_attachment_source(attachment, roots, index)
            if source is None:
                resolved_attachments.append((attachment, None, None))
                continue

            if not _is_copyable_file(source):
                resolved_attachments.append((attachment, None, None))
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
                copied_path = _relative_path(target, out_path.parent)
                copied_by_source[source_key] = copied_path
                copy_tasks.append(CopyTask(source_key, source, target))

            resolved_attachments.append((attachment, source, source_key))
        resolved_messages.append((message_index - 1, resolved_attachments))

    if not resolved_messages:
        return messages, 0, 0, copied_by_source

    failed_sources = _copy_tasks(copy_tasks, media_workers, progress)
    copied_by_source = {
        key: value
        for key, value in copied_by_source.items()
        if key not in failed_sources
    }

    copied = len(copy_tasks) - len(failed_sources)
    missing = 0
    updated_messages = list(messages)
    for message_offset, resolved_attachments in resolved_messages:
        message = messages[message_offset]
        updated_attachments: list[Attachment] = []
        changed = False
        for attachment, source, source_key in resolved_attachments:
            if source is None or source_key is None or source_key in failed_sources:
                missing += 1
                updated_attachments.append(attachment)
                continue
            copied_path = copied_by_source[source_key]
            updated_attachments.append(
                _enrich_attachment_from_source(
                    attachment,
                    source,
                    copied_path,
                )
            )
            changed = True
        if changed:
            updated_messages[message_offset] = replace(
                message,
                attachments=tuple(updated_attachments),
            )

    return updated_messages, copied, missing, copied_by_source


def _copy_peer_avatars(
    peer_info: Optional[dict[int, PeerInfo]],
    out_path: Path,
    index: MediaIndex,
    target_dir: Path,
    copied_by_source: dict[Path, str],
    exported_peer_ids: set[int],
    progress: Optional[ProgressCallback] = None,
) -> tuple[Optional[dict[int, PeerInfo]], int, int]:
    if not peer_info:
        return peer_info, 0, 0

    copied = 0
    missing = 0
    updated: dict[int, PeerInfo] = {}
    checked = 0
    for peer_id, info in peer_info.items():
        if peer_id not in exported_peer_ids:
            updated[peer_id] = info
            continue
        checked += 1
        if progress and checked % 10000 == 0:
            progress(f"Resolved avatars for {checked} exported peers")
        if not info.avatar_resource_keys:
            updated[peer_id] = info
            continue

        source = index.match(info.avatar_resource_keys, None)
        if source is None or not _is_copyable_file(source):
            missing += 1
            updated[peer_id] = info
            continue

        source_key = source.resolve()
        copied_path = copied_by_source.get(source_key)
        if copied_path is None:
            target_dir.mkdir(parents=True, exist_ok=True)
            file_name = _avatar_file_name(info, source)
            target = _unique_target_path(target_dir / "avatars", file_name)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not _copy_file(source, target):
                missing += 1
                updated[peer_id] = info
                continue
            copied_path = _relative_path(target, out_path.parent)
            copied_by_source[source_key] = copied_path
            copied += 1

        updated[peer_id] = replace(info, avatar_path=copied_path)

    return updated, copied, missing


def _default_media_dir(out_path: Path) -> Path:
    return out_path.with_name(f"{out_path.stem}_media")


def _resolve_attachment_source(
    attachment: Attachment, roots: list[Path], index: MediaIndex
) -> Optional[Path]:
    source_path = _path_from_attachment(attachment)

    if source_path and roots:
        for root in roots:
            candidate = source_path if source_path.is_absolute() else root / source_path
            if candidate.is_file() and _is_allowed_source(candidate, root):
                return candidate

    if source_path and not roots and source_path.is_file():
        if _is_indexable_media_file(source_path):
            return source_path

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


def _enrich_attachment_from_source(
    attachment: Attachment,
    source: Path,
    copied_path: str,
) -> Attachment:
    mime_type = attachment.mime_type or _mime_type_for_source(source)
    size = attachment.size or _file_size(source)
    file_name = attachment.file_name or source.name
    kind = _kind_for_source(attachment.kind, source, mime_type, file_name)
    return replace(
        attachment,
        kind=kind,
        file_name=file_name,
        mime_type=mime_type,
        size=size,
        copied_path=copied_path,
        source_path=attachment.source_path or str(source),
    )


def _mime_type_for_source(source: Path) -> Optional[str]:
    guessed = mimetypes.guess_type(source.name)[0]
    if guessed:
        return guessed
    return _guess_mime_type_from_header(source)


def _file_size(source: Path) -> Optional[int]:
    try:
        return source.stat().st_size
    except OSError:
        return None


def _kind_for_source(
    current_kind: str,
    source: Path,
    mime_type: Optional[str],
    file_name: Optional[str],
) -> str:
    if current_kind not in {"media", "file"}:
        return current_kind
    lower_name = (file_name or source.name).lower()
    mime = mime_type or ""
    if "sticker" in lower_name or mime in {
        "application/x-tgsticker",
        "application/x-tgs",
    }:
        return "sticker"
    if source.name.startswith("telegram-cloud-photo-size"):
        return "photo"
    if mime.startswith("image/"):
        return "photo"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    return current_kind


def _size_matches(path: Path, size: Optional[int]) -> bool:
    if size is None:
        return True
    try:
        return path.stat().st_size == size
    except OSError:
        return False


MEDIA_CACHE_PREFIXES = (
    "map-",
    "telegram-cloud-document",
    "telegram-cloud-document-size",
    "telegram-cloud-photo-size",
    "telegram-peer-photo-size",
    "telegram-stickerpackthumbnail",
    "telegram-wallpaper",
)
KNOWN_MEDIA_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".mp4",
    ".webm",
    ".mov",
    ".m4v",
    ".mp3",
    ".m4a",
    ".ogg",
    ".oga",
    ".opus",
    ".wav",
    ".pdf",
    ".zip",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
}


def _is_allowed_source(path: Path, root: Path) -> bool:
    if not _is_indexable_media_file(path):
        return False
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _is_indexable_media_file(path: Path) -> bool:
    name = path.name
    if name.startswith(".") or name.endswith(".meta"):
        return False
    if _looks_like_telegram_media_name(name):
        return True
    return path.suffix.lower() in KNOWN_MEDIA_SUFFIXES


def _is_copyable_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _copy_file(source: Path, target: Path) -> bool:
    try:
        shutil.copy2(source, target)
    except OSError:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True


def _copy_tasks(
    tasks: list[CopyTask],
    workers: Optional[int],
    progress: Optional[ProgressCallback],
) -> set[Path]:
    if not tasks:
        return set()
    worker_count = _effective_worker_count(workers, len(tasks))
    if progress:
        progress(f"Copying {len(tasks)} media files with {worker_count} workers")
    if worker_count <= 1:
        return _copy_tasks_sequential(tasks, progress)
    return _copy_tasks_parallel(tasks, worker_count, progress)


def _copy_tasks_sequential(
    tasks: list[CopyTask],
    progress: Optional[ProgressCallback],
) -> set[Path]:
    failed: set[Path] = set()
    for index, task in enumerate(tasks, start=1):
        if not _copy_file(task.source, task.target):
            failed.add(task.source_key)
        if progress and index % 1000 == 0:
            progress(f"Copied media files: {index}/{len(tasks)}")
    return failed


def _copy_tasks_parallel(
    tasks: list[CopyTask],
    worker_count: int,
    progress: Optional[ProgressCallback],
) -> set[Path]:
    failed: set[Path] = set()
    completed = 0
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(_copy_file, task.source, task.target): task
            for task in tasks
        }
        for future in as_completed(futures):
            task = futures[future]
            completed += 1
            try:
                ok = future.result()
            except OSError:
                ok = False
            if not ok:
                failed.add(task.source_key)
            if progress and completed % 1000 == 0:
                progress(f"Copied media files: {completed}/{len(tasks)}")
    return failed


def _effective_worker_count(workers: Optional[int], task_count: int) -> int:
    if workers is not None:
        return max(1, min(workers, task_count))
    default = min(8, os.cpu_count() or 4)
    return max(1, min(default, task_count))


def _looks_like_telegram_media_name(name: str) -> bool:
    return any(name.startswith(prefix) for prefix in MEDIA_CACHE_PREFIXES)


def _resource_tokens(value: str) -> set[str]:
    return {
        token.lower()
        for token in re.split(r"[^A-Za-z0-9]+", value)
        if token and token.lower() not in {"partial", "meta"}
    }


def _strong_tokens(values: Iterable[str]) -> tuple[str, ...]:
    tokens: list[str] = []
    for value in values:
        for token in _resource_tokens(value):
            if len(token) >= 6 or token.isdigit() and len(token) >= 3:
                tokens.append(token)
    tokens = sorted(set(tokens), key=lambda item: (-len(item), item))
    return tuple(tokens[:4])


def _best_paths(paths: Iterable[Path]) -> list[Path]:
    return sorted(
        (path for path in paths if _is_copyable_file(path)),
        key=_path_quality,
    )


def _path_quality(path: Path) -> tuple[int, int, str]:
    name = path.name
    partial_penalty = 1 if "_partial" in name else 0
    meta_penalty = 1 if name.endswith(".meta") else 0
    try:
        size = -path.stat().st_size
    except OSError:
        size = 0
    return (meta_penalty, partial_penalty, size, name)


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
    extension = _extension_for_attachment(attachment, source)
    if extension and (
        "." not in safe_name
        or _looks_like_telegram_media_name(source.name)
        and not safe_name.lower().endswith(extension.lower())
    ):
        safe_name += extension
    return safe_name


def _avatar_file_name(info: PeerInfo, source: Path) -> str:
    suffix = source.suffix or _guess_extension_from_header(source) or ".jpg"
    return _safe_file_name(f"avatar_{info.peer_id}{suffix}")


def _safe_file_name(value: str) -> str:
    cleaned = "".join(
        "_" if char in '/\\:\0' or ord(char) < 32 else char for char in value.strip()
    )
    cleaned = cleaned.strip(". ")
    return cleaned or "attachment"


def _extension_for_attachment(attachment: Attachment, source: Path) -> str:
    if source.suffix and source.suffix.lower() in KNOWN_MEDIA_SUFFIXES:
        return source.suffix
    if attachment.mime_type:
        if attachment.mime_type == "application/x-tgsticker":
            return ".tgs"
        return mimetypes.guess_extension(attachment.mime_type) or ""
    return _guess_extension_from_header(source)


def _guess_extension_from_header(source: Path) -> str:
    try:
        with source.open("rb") as handle:
            header = handle.read(16)
    except OSError:
        return ""
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
        return ".gif"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return ".webp"
    if header.startswith(b"%PDF"):
        return ".pdf"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return ".mp4"
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        return ".webm"
    if header.startswith(b"PK\x03\x04"):
        return ".zip"
    return ""


def _guess_mime_type_from_header(source: Path) -> Optional[str]:
    extension = _guess_extension_from_header(source)
    if extension == ".jpg":
        return "image/jpeg"
    if extension == ".webm":
        return "video/webm"
    if extension:
        return mimetypes.types_map.get(extension)
    return None


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
