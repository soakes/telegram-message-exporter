"""Export helpers for Markdown, CSV, and HTML."""

from __future__ import annotations

import csv
import html
import json
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import Attachment, Message, PeerInfo
from .utils import linkify_html, linkify_markdown

HTML_CSS = """
:root {
  --page: #dfe7ee;
  --sidebar: #ffffff;
  --sidebar-border: #d8dee5;
  --chat-bg: #d7e4ee;
  --topbar: #f7f9fb;
  --ink: #17212b;
  --muted: #6f7f8d;
  --muted-soft: #8a99a8;
  --blue: #2aabee;
  --blue-dark: #168acd;
  --accent: #168acd;
  --incoming: #ffffff;
  --outgoing: #d9fdd3;
  --outgoing-meta: #4a8f3a;
  --file-bg: rgba(42, 171, 238, 0.1);
  --shadow: rgba(15, 23, 42, 0.13);
  --radius: 8px;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--page);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  color: var(--ink);
  min-height: 100vh;
  letter-spacing: 0;
}
.export-shell {
  display: grid;
  grid-template-rows: auto 1fr;
  min-height: 100vh;
}
.export-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 10px 16px;
  background: #ffffff;
  border-bottom: 1px solid var(--sidebar-border);
  min-height: 56px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.logo {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--blue);
  color: #ffffff;
  font-weight: 700;
  flex: 0 0 auto;
}
.title-area { min-width: 0; }
.title-area h1 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.subtitle {
  margin: 2px 0 0;
  color: var(--muted);
  font-size: 12px;
}
.stats-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}
.stat-pill {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  padding: 5px 9px;
  border-radius: 999px;
  background: #eef3f7;
  color: var(--muted);
  font-size: 12px;
}
.stat-pill strong {
  color: var(--ink);
  font-weight: 600;
}
.export-layout {
  display: grid;
  grid-template-columns: minmax(260px, 340px) minmax(0, 1fr);
  min-height: calc(100vh - 56px);
}
.export-layout.single {
  grid-template-columns: minmax(0, 980px);
  justify-content: center;
}
.chat-sidebar {
  background: var(--sidebar);
  border-right: 1px solid var(--sidebar-border);
  overflow: auto;
}
.sidebar-title {
  padding: 12px 16px 8px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 600;
}
.sidebar-controls {
  display: grid;
  gap: 8px;
  padding: 8px 12px 12px;
  border-bottom: 1px solid var(--sidebar-border);
}
.search-input {
  width: 100%;
  height: 34px;
  border: 1px solid #d8e1e8;
  border-radius: 8px;
  padding: 0 10px;
  background: #f3f6f8;
  color: var(--ink);
  font: inherit;
  font-size: 13px;
}
.search-input:focus {
  outline: 2px solid rgba(42, 171, 238, 0.25);
  border-color: var(--blue);
  background: #ffffff;
}
.type-filters,
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.filter-button,
.tab-button {
  border: 0;
  border-radius: 999px;
  padding: 5px 9px;
  background: #e9f0f5;
  color: var(--muted);
  cursor: pointer;
  font: inherit;
  font-size: 12px;
}
.filter-button.active,
.tab-button.active {
  background: var(--blue);
  color: #ffffff;
}
.search-results {
  display: none;
  max-height: 260px;
  overflow: auto;
  border-top: 1px solid var(--sidebar-border);
}
.search-results.show { display: block; }
.search-result {
  display: block;
  width: 100%;
  border: 0;
  border-bottom: 1px solid #edf1f5;
  padding: 8px 12px;
  background: #ffffff;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.search-result:hover { background: #f1f5f8; }
.result-title {
  font-size: 12px;
  font-weight: 600;
}
.result-snippet {
  margin-top: 3px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.3;
}
.chat-list {
  display: flex;
  flex-direction: column;
}
.chat-item {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  gap: 10px;
  width: 100%;
  padding: 10px 14px;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  min-height: 64px;
}
.chat-item:hover { background: #f1f5f8; }
.chat-item.active {
  background: var(--blue);
  color: #ffffff;
}
.avatar {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #2aabee, #77c65a);
  color: #ffffff;
  font-weight: 700;
  flex: 0 0 auto;
}
.chat-item.active .avatar { background: rgba(255, 255, 255, 0.22); }
.chat-main { min-width: 0; }
.chat-name {
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chat-preview {
  margin-top: 4px;
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chat-item.active .chat-preview,
.chat-item.active .chat-time {
  color: rgba(255, 255, 255, 0.82);
}
.chat-time {
  font-size: 11px;
  color: var(--muted);
  align-self: start;
}
.kind-badge {
  display: inline-flex;
  width: fit-content;
  margin-top: 4px;
  padding: 2px 6px;
  border-radius: 999px;
  background: #edf3f7;
  color: var(--muted);
  font-size: 10px;
  font-weight: 600;
}
.chat-item.active .kind-badge {
  background: rgba(255, 255, 255, 0.2);
  color: #ffffff;
}
.chat-area {
  min-width: 0;
  background:
    linear-gradient(rgba(215, 228, 238, 0.92), rgba(215, 228, 238, 0.92)),
    repeating-linear-gradient(
      45deg,
      rgba(255, 255, 255, 0.28) 0,
      rgba(255, 255, 255, 0.28) 2px,
      transparent 2px,
      transparent 28px
    );
}
.chat-panel { display: none; min-height: 100%; }
.chat-panel.active { display: block; }
.chat-topbar {
  position: sticky;
  top: 0;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 16px;
  background: var(--topbar);
  border-bottom: 1px solid var(--sidebar-border);
  min-height: 58px;
}
.split-frame {
  display: block;
  width: 100%;
  min-height: calc(100vh - 56px);
  border: 0;
}
.chat-tools {
  margin-left: auto;
  display: grid;
  gap: 6px;
  min-width: min(320px, 42vw);
}
.chat-topbar .chat-meta { min-width: 0; }
.chat-topbar h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chat-topbar p {
  margin: 2px 0 0;
  color: var(--muted);
  font-size: 12px;
}
.messages {
  width: min(100%, 860px);
  margin: 0 auto;
  padding: 16px;
}
.tab-content { display: none; }
.tab-content.active { display: block; }
.library-grid,
.file-list {
  width: min(100%, 860px);
  margin: 0 auto;
  padding: 16px;
}
.library-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
}
.library-item {
  display: block;
  min-height: 118px;
  border-radius: 8px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.78);
  color: inherit;
  text-decoration: none;
  box-shadow: 0 1px 2px var(--shadow);
}
.library-thumb {
  display: grid;
  place-items: center;
  min-height: 92px;
  background: #edf3f7;
  color: var(--muted);
  font-weight: 700;
}
.library-thumb img,
.library-thumb video {
  width: 100%;
  height: 140px;
  object-fit: cover;
}
.library-title {
  display: block;
  padding: 7px 8px;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.empty-state {
  width: min(100%, 860px);
  margin: 0 auto;
  padding: 28px 16px;
  color: var(--muted);
  text-align: center;
}
.msg.hidden,
.chat-item.hidden,
.library-item.hidden,
.attachment.hidden {
  display: none;
}
.msg.highlight .bubble {
  outline: 2px solid rgba(42, 171, 238, 0.45);
}
.day {
  width: fit-content;
  margin: 16px auto 12px;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(104, 125, 144, 0.42);
  color: #ffffff;
  font-size: 12px;
  font-weight: 600;
  box-shadow: 0 1px 2px var(--shadow);
}
.msg { display: flex; margin: 6px 0; gap: 8px; }
.msg.out { justify-content: flex-end; }
.bubble {
  max-width: min(78%, 620px);
  padding: 7px 9px 6px;
  border-radius: var(--radius);
  background: var(--incoming);
  box-shadow: 0 1px 2px var(--shadow);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
  position: relative;
}
.msg.out .bubble { background: var(--outgoing); }
.meta {
  font-size: 12px;
  color: var(--blue-dark);
  margin-bottom: 3px;
  font-weight: 600;
}
.msg.out .meta { color: var(--outgoing-meta); }
.message-text { line-height: 1.34; font-size: 14px; }
.time {
  float: right;
  margin: 4px 0 0 8px;
  color: var(--muted-soft);
  font-size: 11px;
  line-height: 1;
}
.msg.out .time { color: #5b9d4c; }
.attachments {
  display: grid;
  gap: 6px;
  margin-top: 6px;
}
.attachment {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr);
  gap: 9px;
  align-items: center;
  min-width: 230px;
  max-width: 100%;
  padding: 8px;
  border-radius: 7px;
  background: var(--file-bg);
  text-decoration: none;
  color: inherit;
}
.attachment:hover .attachment-title { text-decoration: underline; }
.attachment-icon {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--blue);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
}
.attachment-title {
  font-weight: 600;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.attachment-meta {
  margin-top: 2px;
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.media-preview {
  display: block;
  overflow: hidden;
  border-radius: 8px;
  background: #eef3f7;
  max-width: min(100%, 420px);
}
.media-preview img,
.media-preview video {
  display: block;
  width: 100%;
  max-height: 420px;
  object-fit: contain;
}
.media-preview audio {
  width: min(100%, 360px);
  display: block;
}
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; }
a {
  color: var(--accent);
  text-decoration: none;
  word-break: break-word;
  overflow-wrap: anywhere;
}
a:hover { text-decoration: underline; }
.back-top {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 5;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  font-size: 20px;
  border: 0;
  background: var(--blue);
  color: #ffffff;
  cursor: pointer;
  box-shadow: 0 8px 20px var(--shadow);
  opacity: 0;
  transform: translateY(8px);
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.back-top.show { opacity: 1; transform: translateY(0); }
footer {
  padding: 18px;
  color: var(--muted);
  font-size: 12px;
  text-align: center;
}
@media (max-width: 760px) {
  .export-header { align-items: flex-start; flex-direction: column; }
  .stats-row { justify-content: flex-start; }
  .export-layout,
  .export-layout.single {
    display: block;
  }
  .chat-sidebar {
    max-height: 260px;
    border-right: 0;
    border-bottom: 1px solid var(--sidebar-border);
  }
  .chat-topbar { align-items: flex-start; flex-wrap: wrap; }
  .chat-tools { width: 100%; min-width: 0; margin-left: 0; }
  .bubble { max-width: 92%; }
  .messages { padding: 12px 8px; }
}
"""


@dataclass(frozen=True)
class HtmlStats:
    """Computed stats for HTML output."""

    message_count: int
    attachment_count: int
    chat_count: int
    date_range: str
    exported_at: str


@dataclass(frozen=True)
class ChatGroup:
    """Messages grouped by Telegram peer."""

    key: str
    title: str
    kind: str
    messages: tuple[Message, ...]
    page: Optional[str] = None


@dataclass(frozen=True)
class RenderOptions:
    """Optional rendering preferences."""

    peer_map: Optional[dict[int, str]] = None
    peer_info: Optional[dict[int, PeerInfo]] = None
    me_name: str = "Me"
    show_direction: bool = False


def resolve_speaker(
    msg: Message, peer_map: Optional[dict[int, str]], me_name: str
) -> str:
    """Resolve display name for a message."""
    if msg.outgoing is True:
        return me_name
    if peer_map:
        if msg.author_id and msg.author_id in peer_map:
            return peer_map[msg.author_id]
        if msg.peer_id and msg.peer_id in peer_map:
            return peer_map[msg.peer_id]
    return "Unknown"


def build_html_stats(
    messages: list[Message], _title: str, _me_name: str
) -> HtmlStats:
    """Build summary stats for the HTML export."""
    timestamps = [msg.timestamp for msg in messages if msg.timestamp]
    start = min(timestamps) if timestamps else None
    end = max(timestamps) if timestamps else None
    if start and end:
        date_range = f"{start.strftime('%Y-%m-%d')} → {end.strftime('%Y-%m-%d')}"
    else:
        date_range = "—"

    peer_ids = {msg.peer_id for msg in messages if msg.peer_id is not None}
    attachment_count = sum(len(msg.attachments) for msg in messages)
    exported_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    return HtmlStats(
        message_count=len(messages),
        attachment_count=attachment_count,
        chat_count=max(1, len(peer_ids)),
        date_range=date_range,
        exported_at=exported_at,
    )


def render_markdown(
    messages: list[Message],
    title: str,
    out_path: Path,
    options: Optional[RenderOptions] = None,
) -> None:
    """Export messages to Markdown."""
    options = options or RenderOptions()
    peer_map = options.peer_map
    me_name = options.me_name
    show_direction = options.show_direction
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        handle.write(f"# Telegram Chat History: {title}\n\n")
        handle.write(
            f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        handle.write(f"**Total Messages:** {len(messages)}\n\n")
        attachment_count = sum(len(msg.attachments) for msg in messages)
        if attachment_count:
            handle.write(f"**Attachments:** {attachment_count}\n\n")
        handle.write("---\n")

        current_date = None
        for msg in messages:
            if msg.timestamp:
                msg_date = msg.timestamp.strftime("%Y-%m-%d")
            else:
                msg_date = "Unknown Date"

            if current_date != msg_date:
                current_date = msg_date
                header = (
                    msg.timestamp.strftime("%A, %B %d, %Y")
                    if msg.timestamp
                    else "Unknown"
                )
                handle.write(f"\n## {header}\n\n")

            time_str = (
                msg.timestamp.strftime("%H:%M:%S") if msg.timestamp else "??:??:??"
            )
            speaker = resolve_speaker(msg, peer_map, me_name)

            direction = ""
            if show_direction:
                direction = f" ({msg.speaker_hint()})"

            handle.write(f"**{time_str} — {speaker}{direction}**\n\n")
            if msg.text:
                handle.write(f"{linkify_markdown(msg.text)}\n\n")
            if msg.attachments:
                handle.write("Attachments:\n")
                for attachment in msg.attachments:
                    handle.write(f"- {_markdown_attachment(attachment)}\n")
                handle.write("\n")


def render_csv(
    messages: list[Message],
    out_path: Path,
    peer_map: Optional[dict[int, str]] = None,
    me_name: str = "Me",
) -> None:
    """Export messages to CSV."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "date",
                "time",
                "timestamp",
                "direction",
                "speaker",
                "text",
                "attachments",
                "attachment_paths",
                "peer_id",
                "author_id",
            ]
        )
        for msg in messages:
            ts = msg.timestamp
            date_str = ts.strftime("%Y-%m-%d") if ts else ""
            time_str = ts.strftime("%H:%M:%S") if ts else ""
            timestamp = int(ts.timestamp()) if ts else ""
            speaker = resolve_speaker(msg, peer_map, me_name)
            writer.writerow(
                [
                    date_str,
                    time_str,
                    timestamp,
                    msg.speaker_hint(),
                    speaker,
                    msg.text,
                    "; ".join(_attachment_summary(item) for item in msg.attachments),
                    "; ".join(
                        item.copied_path or "" for item in msg.attachments
                    ).strip("; "),
                    msg.peer_id or "",
                    msg.author_id or "",
                ]
            )


def render_html(
    messages: list[Message],
    title: str,
    out_path: Path,
    peer_map: Optional[dict[int, str]] = None,
    peer_info: Optional[dict[int, PeerInfo]] = None,
    me_name: str = "Me",
    split: bool = False,
) -> None:
    """Export messages to a styled HTML transcript."""
    stats = build_html_stats(messages, title, me_name)
    groups = build_chat_groups(messages, peer_map, peer_info, title)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if split:
        groups = _write_split_chat_pages(groups, out_path, peer_map, me_name)

    with out_path.open("w", encoding="utf-8") as handle:
        handle.write('<!doctype html><html lang="en"><head><meta charset="utf-8">')
        handle.write(
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
        )
        handle.write(f"<title>{html.escape(title)}</title>")
        handle.write(f"<style>{HTML_CSS}</style></head><body>")
        handle.write('<div class="export-shell">')
        _render_header(handle, title, stats)
        _render_chat_layout(handle, groups, peer_map, me_name, split=split)
        _render_search_index(handle, groups, peer_map, me_name)
        _render_footer(handle)
        handle.write("</div></body></html>")


def _write_split_chat_pages(
    groups: tuple[ChatGroup, ...],
    out_path: Path,
    peer_map: Optional[dict[int, str]],
    me_name: str,
) -> tuple[ChatGroup, ...]:
    chat_dir = out_path.with_name(f"{out_path.stem}_chats")
    chat_dir.mkdir(parents=True, exist_ok=True)
    updated_groups: list[ChatGroup] = []
    for index, group in enumerate(groups, start=1):
        page_name = f"chat_{index:04d}_{group.key}.html"
        page_path = chat_dir / page_name
        page_group = replace(group, page=f"{chat_dir.name}/{page_name}")
        _write_chat_page(page_path, page_group, peer_map, me_name)
        updated_groups.append(page_group)
    return tuple(updated_groups)


def _write_chat_page(
    page_path: Path,
    group: ChatGroup,
    peer_map: Optional[dict[int, str]],
    me_name: str,
) -> None:
    page_path.parent.mkdir(parents=True, exist_ok=True)
    with page_path.open("w", encoding="utf-8") as handle:
        handle.write('<!doctype html><html lang="en"><head><meta charset="utf-8">')
        handle.write(
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
        )
        handle.write(f"<title>{html.escape(group.title)}</title>")
        handle.write(f"<style>{HTML_CSS}</style></head><body>")
        handle.write('<div class="chat-area">')
        _render_chat_panel(handle, group, True, peer_map, me_name)
        handle.write("</div>")
        handle.write(_export_script(split=False))
        handle.write("</body></html>")


def build_chat_groups(
    messages: list[Message],
    peer_map: Optional[dict[int, str]],
    peer_info: Optional[dict[int, PeerInfo]],
    title: str,
) -> tuple[ChatGroup, ...]:
    """Group messages by peer for the Telegram-like all-chats view."""
    grouped: dict[str, list[Message]] = {}
    titles: dict[str, str] = {}
    kinds: dict[str, str] = {}
    for msg in messages:
        key = f"peer-{msg.peer_id}" if msg.peer_id is not None else "unknown"
        grouped.setdefault(key, []).append(msg)
        titles.setdefault(key, _chat_title(msg.peer_id, peer_map, peer_info, title))
        kinds.setdefault(key, _chat_kind(msg.peer_id, peer_info))

    groups = [
        ChatGroup(
            key=key,
            title=titles[key],
            kind=kinds[key],
            messages=tuple(items),
        )
        for key, items in grouped.items()
    ]
    groups.sort(key=_latest_group_ts, reverse=True)
    return tuple(groups)


def _chat_title(
    peer_id: Optional[int],
    peer_map: Optional[dict[int, str]],
    peer_info: Optional[dict[int, PeerInfo]],
    fallback: str,
) -> str:
    if peer_id is not None and peer_info and peer_id in peer_info:
        return peer_info[peer_id].title
    if peer_id is not None and peer_map and peer_id in peer_map:
        return peer_map[peer_id]
    if peer_id is not None:
        return f"peer {peer_id}"
    return fallback


def _chat_kind(peer_id: Optional[int], peer_info: Optional[dict[int, PeerInfo]]) -> str:
    if peer_id is not None and peer_info and peer_id in peer_info:
        return peer_info[peer_id].kind
    return "unknown"


def _latest_group_ts(group: ChatGroup) -> float:
    timestamps = [msg.timestamp.timestamp() for msg in group.messages if msg.timestamp]
    return max(timestamps) if timestamps else 0


def _render_header(handle, title: str, stats: HtmlStats) -> None:
    handle.write('<header class="export-header">')
    handle.write('<div class="brand">')
    handle.write('<div class="logo">T</div>')
    handle.write('<div class="title-area">')
    handle.write(f"<h1>{html.escape(title)}</h1>")
    handle.write('<p class="subtitle">Telegram for macOS local export</p>')
    handle.write("</div></div>")
    handle.write('<div class="stats-row">')
    _render_stat_pill(handle, "Messages", str(stats.message_count))
    _render_stat_pill(handle, "Chats", str(stats.chat_count))
    _render_stat_pill(handle, "Files", str(stats.attachment_count))
    _render_stat_pill(handle, "Dates", stats.date_range)
    _render_stat_pill(handle, "Exported", stats.exported_at)
    handle.write("</div>")
    handle.write("</header>")


def _render_stat_pill(handle, label: str, value: str) -> None:
    handle.write(
        f'<span class="stat-pill"><strong>{html.escape(value)}</strong>'
        f" {html.escape(label)}</span>"
    )


def _render_chat_layout(
    handle,
    groups: tuple[ChatGroup, ...],
    peer_map: Optional[dict[int, str]],
    me_name: str,
    split: bool = False,
) -> None:
    layout_class = "export-layout single" if len(groups) <= 1 else "export-layout"
    handle.write(f'<main class="{layout_class}">')
    if len(groups) > 1:
        _render_sidebar(handle, groups, split=split)
    handle.write('<div class="chat-area">')
    if split:
        first_page = groups[0].page if groups else ""
        handle.write(
            '<iframe id="chat-frame" class="split-frame" '
            f'src="{html.escape(first_page or "", quote=True)}"></iframe>'
        )
    else:
        for index, group in enumerate(groups):
            _render_chat_panel(handle, group, index == 0, peer_map, me_name)
    handle.write("</div></main>")
    handle.write('<button id="back-top" class="back-top" type="button">↑</button>')
    handle.write(_export_script(split=split))


def _render_sidebar(
    handle, groups: tuple[ChatGroup, ...], split: bool = False
) -> None:
    handle.write('<aside class="chat-sidebar">')
    handle.write('<div class="sidebar-title">All chats</div>')
    handle.write('<div class="sidebar-controls">')
    handle.write(
        '<input id="global-search" class="search-input" '
        'type="search" placeholder="Search all chats">'
    )
    handle.write('<div class="type-filters" aria-label="Chat type filters">')
    for kind, label in _kind_filters():
        active = " active" if kind == "all" else ""
        handle.write(
            f'<button class="filter-button{active}" type="button" '
            f'data-kind="{kind}">{label}</button>'
        )
    handle.write("</div>")
    handle.write(
        '<input id="chat-search" class="search-input" '
        'type="search" placeholder="Search in selected chat">'
    )
    handle.write("</div>")
    handle.write('<div id="search-results" class="search-results"></div>')
    handle.write('<div class="chat-list">')
    for index, group in enumerate(groups):
        active = " active" if index == 0 else ""
        page = group.page or ""
        search_text = _chat_search_text(group)
        handle.write(
            f'<button type="button" class="chat-item{active}" '
            f'data-chat="{html.escape(group.key, quote=True)}" '
            f'data-kind="{html.escape(group.kind, quote=True)}" '
            f'data-page="{html.escape(page, quote=True)}" '
            f'data-split="{str(split).lower()}" '
            f'data-search="{html.escape(search_text, quote=True)}">'
        )
        _render_avatar(handle, group.title)
        handle.write('<span class="chat-main">')
        handle.write(f'<span class="chat-name">{html.escape(group.title)}</span>')
        handle.write(
            f'<span class="chat-preview">{html.escape(_chat_preview(group))}</span>'
        )
        handle.write(
            f'<span class="kind-badge">{html.escape(_kind_label(group.kind))}</span>'
        )
        handle.write("</span>")
        handle.write(f'<span class="chat-time">{_group_time(group)}</span>')
        handle.write("</button>")
    handle.write("</div></aside>")


def _render_chat_panel(
    handle,
    group: ChatGroup,
    active: bool,
    peer_map: Optional[dict[int, str]],
    me_name: str,
) -> None:
    active_class = " active" if active else ""
    handle.write(
        f'<section id="{html.escape(group.key, quote=True)}" '
        f'class="chat-panel{active_class}">'
    )
    _render_chat_topbar(handle, group)
    _render_tabbed_chat_contents(handle, group, peer_map, me_name)
    handle.write("</section>")


def _render_tabbed_chat_contents(
    handle,
    group: ChatGroup,
    peer_map: Optional[dict[int, str]],
    me_name: str,
) -> None:
    handle.write(
        '<div class="tab-content messages-tab active" data-tab-panel="messages">'
    )
    _render_message_list(handle, group, peer_map, me_name)
    handle.write("</div>")
    handle.write('<div class="tab-content media-tab" data-tab-panel="media">')
    _render_media_library(handle, group)
    handle.write("</div>")
    handle.write('<div class="tab-content files-tab" data-tab-panel="files">')
    _render_file_library(handle, group)
    handle.write("</div>")


def _render_message_list(
    handle,
    group: ChatGroup,
    peer_map: Optional[dict[int, str]],
    me_name: str,
) -> None:
    handle.write('<div class="messages">')
    current_date = None
    for message_index, msg in enumerate(group.messages, start=1):
        msg_date, day_label, time_str = _message_date_parts(msg)
        if current_date != msg_date:
            current_date = msg_date
            handle.write(
                f'<div id="{html.escape(group.key)}-day-{html.escape(msg_date)}" '
                f'class="day">{html.escape(day_label)}</div>'
            )
        speaker = resolve_speaker(msg, peer_map, me_name)
        direction = "out" if msg.outgoing is True else "in"
        search_text = _message_search_text(msg, speaker)
        message_id = _message_dom_id(group, message_index)
        handle.write(
            f'<div id="{message_id}" class="msg {direction}" '
            f'data-search="{html.escape(search_text, quote=True)}">'
        )
        handle.write('<div class="bubble">')
        handle.write(f'<div class="meta">{html.escape(speaker)}</div>')
        if msg.text:
            handle.write(f'<div class="message-text">{linkify_html(msg.text)}</div>')
        _render_attachments(handle, msg.attachments)
        handle.write(f'<span class="time">{html.escape(time_str)}</span>')
        handle.write("</div></div>")
    handle.write("</div>")


def _render_chat_topbar(handle, group: ChatGroup) -> None:
    attachment_count = sum(len(msg.attachments) for msg in group.messages)
    handle.write('<div class="chat-topbar">')
    _render_avatar(handle, group.title)
    handle.write('<div class="chat-meta">')
    handle.write(f"<h2>{html.escape(group.title)}</h2>")
    meta = f"{len(group.messages)} messages"
    if attachment_count:
        meta += f", {attachment_count} files"
    handle.write(f"<p>{html.escape(meta)}</p>")
    handle.write("</div>")
    handle.write('<div class="chat-tools">')
    handle.write(
        '<input class="search-input local-chat-search" type="search" '
        'placeholder="Search this chat">'
    )
    handle.write('<div class="tabs" aria-label="Chat sections">')
    for tab, label in (
        ("messages", "Messages"),
        ("media", "Media"),
        ("files", "Files"),
    ):
        active = " active" if tab == "messages" else ""
        handle.write(
            f'<button class="tab-button{active}" type="button" '
            f'data-tab="{tab}">{label}</button>'
        )
    handle.write("</div></div>")
    handle.write("</div>")


def _render_avatar(handle, title: str) -> None:
    handle.write(f'<span class="avatar">{html.escape(_avatar_initial(title))}</span>')


def _render_media_library(handle, group: ChatGroup) -> None:
    media_items = [
        attachment
        for msg in group.messages
        for attachment in msg.attachments
        if _is_media_attachment(attachment)
    ]
    if not media_items:
        handle.write('<div class="empty-state">No media in this chat</div>')
        return
    handle.write('<div class="library-grid">')
    for attachment in media_items:
        _render_library_item(handle, attachment)
    handle.write("</div>")


def _render_file_library(handle, group: ChatGroup) -> None:
    file_items = [
        attachment
        for msg in group.messages
        for attachment in msg.attachments
        if not _is_media_attachment(attachment)
    ]
    if not file_items:
        handle.write('<div class="empty-state">No files in this chat</div>')
        return
    handle.write('<div class="file-list">')
    for attachment in file_items:
        _render_file_attachment(handle, attachment)
    handle.write("</div>")


def _render_library_item(handle, attachment: Attachment) -> None:
    tag = "a" if attachment.copied_path else "div"
    href = ""
    if attachment.copied_path:
        href = (
            f' href="{html.escape(attachment.copied_path, quote=True)}"'
            ' target="_blank"'
        )
    search_text = _attachment_search_text(attachment)
    handle.write(
        f'<{tag} class="library-item" {href} '
        f'data-search="{html.escape(search_text, quote=True)}">'
    )
    handle.write('<span class="library-thumb">')
    if attachment.copied_path and _is_image_attachment(attachment):
        src = html.escape(attachment.copied_path, quote=True)
        title = html.escape(attachment.title, quote=True)
        handle.write(f'<img src="{src}" alt="{title}">')
    elif attachment.copied_path and _is_video_attachment(attachment):
        src = html.escape(attachment.copied_path, quote=True)
        handle.write(f'<video preload="metadata" src="{src}"></video>')
    else:
        handle.write(html.escape(_attachment_icon(attachment)))
    handle.write("</span>")
    handle.write(
        f'<span class="library-title">{html.escape(attachment.title)}</span>'
    )
    handle.write(f"</{tag}>")


def _render_attachments(handle, attachments: tuple[Attachment, ...]) -> None:
    if not attachments:
        return
    handle.write('<div class="attachments">')
    for attachment in attachments:
        if _render_media_preview(handle, attachment):
            continue
        _render_file_attachment(handle, attachment)
    handle.write("</div>")


def _render_media_preview(handle, attachment: Attachment) -> bool:
    if not attachment.copied_path:
        return False
    src = html.escape(attachment.copied_path, quote=True)
    title = html.escape(attachment.title, quote=True)
    if _is_image_attachment(attachment):
        handle.write(f'<a class="media-preview" href="{src}" target="_blank">')
        handle.write(f'<img src="{src}" alt="{title}">')
        handle.write("</a>")
        return True
    if _is_video_attachment(attachment):
        handle.write('<div class="media-preview">')
        handle.write(f'<video controls preload="metadata" src="{src}"></video>')
        handle.write("</div>")
        return True
    if _is_audio_attachment(attachment):
        handle.write('<div class="media-preview">')
        handle.write(f'<audio controls preload="metadata" src="{src}"></audio>')
        handle.write("</div>")
        return True
    return False


def _render_file_attachment(handle, attachment: Attachment) -> None:
    href = ""
    tag = "div"
    if attachment.copied_path:
        tag = "a"
        href = (
            f' href="{html.escape(attachment.copied_path, quote=True)}"'
            ' target="_blank"'
        )
    search_text = html.escape(_attachment_search_text(attachment), quote=True)
    handle.write(f'<{tag} class="attachment"{href} data-search="{search_text}">')
    handle.write(f'<span class="attachment-icon">{_attachment_icon(attachment)}</span>')
    handle.write("<span>")
    handle.write(
        f'<span class="attachment-title">{html.escape(attachment.title)}</span>'
    )
    meta = html.escape(_attachment_meta(attachment))
    handle.write(f'<span class="attachment-meta">{meta}</span>')
    handle.write("</span>")
    handle.write(f"</{tag}>")


def _message_date_parts(msg: Message) -> tuple[str, str, str]:
    if msg.timestamp:
        msg_date = msg.timestamp.strftime("%Y-%m-%d")
        day_label = msg.timestamp.strftime("%A, %B %d, %Y")
        time_str = msg.timestamp.strftime("%H:%M:%S")
    else:
        msg_date = "unknown"
        day_label = "Unknown Date"
        time_str = "??:??:??"
    return msg_date, day_label, time_str


def _export_script(split: bool = False) -> str:
    script = """
    <script>
    const splitMode = __SPLIT_MODE__;
    const chatButtons = Array.from(document.querySelectorAll('.chat-item'));
    const panels = Array.from(document.querySelectorAll('.chat-panel'));
    const frame = document.getElementById('chat-frame');
    const globalSearch = document.getElementById('global-search');
    const chatSearch = document.getElementById('chat-search');
    const localSearchInputs = Array.from(
      document.querySelectorAll('.local-chat-search')
    );
    const resultsBox = document.getElementById('search-results');
    const searchIndexEl = document.getElementById('search-index');
    const searchIndex = searchIndexEl
      ? JSON.parse(searchIndexEl.textContent || '[]')
      : [];

    const activeKind = () => {
      const active = document.querySelector('.filter-button.active');
      return active ? active.dataset.kind : 'all';
    };

    const activePanel = () => document.querySelector('.chat-panel.active') || document;

    const showMessage = (messageId) => {
      if (!messageId) return;
      const target = document.getElementById(messageId);
      if (!target) return;
      target.classList.add('highlight');
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      window.setTimeout(() => target.classList.remove('highlight'), 1800);
    };

    const sendSearchToFrame = () => {
      if (!splitMode || !frame || !frame.contentWindow) return;
      const query = chatSearch ? chatSearch.value : '';
      frame.contentWindow.postMessage({ type: 'chat-search', query }, '*');
    };

    const activateChat = (id, messageId = '') => {
      const selected = chatButtons.find((button) => button.dataset.chat === id);
      chatButtons.forEach((button) => {
        button.classList.toggle('active', button.dataset.chat === id);
      });
      if (splitMode && frame && selected) {
        const hash = messageId ? '#' + messageId : '';
        frame.src = selected.dataset.page + hash;
      } else {
        panels.forEach((panel) => {
          panel.classList.toggle('active', panel.id === id);
        });
        applyLocalSearch(chatSearch ? chatSearch.value : '');
        showMessage(messageId);
      }
      if (history.replaceState) {
        history.replaceState(null, '', '#' + id + (messageId ? ':' + messageId : ''));
      }
      window.scrollTo({ top: 0 });
    };

    const applyChatListFilter = () => {
      const kind = activeKind();
      const query = globalSearch ? globalSearch.value.trim().toLowerCase() : '';
      chatButtons.forEach((button) => {
        const kindOk = kind === 'all' || button.dataset.kind === kind;
        const textOk = !query || (button.dataset.search || '').includes(query);
        button.classList.toggle('hidden', !(kindOk && textOk));
      });
    };

    const renderGlobalResults = () => {
      if (!resultsBox || !globalSearch) return;
      const query = globalSearch.value.trim().toLowerCase();
      if (query.length < 2) {
        resultsBox.classList.remove('show');
        resultsBox.innerHTML = '';
        return;
      }
      const kind = activeKind();
      const matches = searchIndex.filter((item) => {
        const kindOk = kind === 'all' || item.kind === kind;
        const haystack = [item.title, item.speaker, item.text].join(' ').toLowerCase();
        return kindOk && haystack.includes(query);
      }).slice(0, 80);
      if (!matches.length) {
        resultsBox.classList.add('show');
        resultsBox.innerHTML = '<div class="empty-state">No matches</div>';
        return;
      }
      resultsBox.classList.add('show');
      resultsBox.innerHTML = matches.map((item) => {
        const snippet = escapeHtml(item.text).slice(0, 180);
        return `<button class="search-result" type="button"
          data-chat="${escapeHtml(item.chat)}"
          data-message="${escapeHtml(item.message)}">
          <div class="result-title">
            ${escapeHtml(item.title)} - ${escapeHtml(item.time)}
          </div>
          <div class="result-snippet">${snippet}</div>
        </button>`;
      }).join('');
    };

    const applyLocalSearch = (query) => {
      const root = activePanel();
      const normalized = (query || '').trim().toLowerCase();
      const items = Array.from(
        root.querySelectorAll('.msg, .library-item, .attachment')
      );
      items.forEach((item) => {
        const haystack = item.dataset.search || '';
        item.classList.toggle('hidden', !!normalized && !haystack.includes(normalized));
      });
    };

    const activateTab = (button) => {
      const panel = button.closest('.chat-panel') || document;
      const tab = button.dataset.tab;
      panel.querySelectorAll('.tab-button').forEach((item) => {
        item.classList.toggle('active', item === button);
      });
      panel.querySelectorAll('.tab-content').forEach((item) => {
        item.classList.toggle('active', item.dataset.tabPanel === tab);
      });
      const localSearch = panel.querySelector('.local-chat-search');
      applyLocalSearch(localSearch ? localSearch.value : '');
    };

    const escapeHtml = (value) => String(value || '').replace(/[&<>"']/g, (char) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    }[char]));

    chatButtons.forEach((button) => {
      button.addEventListener('click', () => activateChat(button.dataset.chat));
    });
    document.querySelectorAll('.filter-button').forEach((button) => {
      button.addEventListener('click', () => {
        document.querySelectorAll('.filter-button').forEach((item) => {
          item.classList.toggle('active', item === button);
        });
        applyChatListFilter();
        renderGlobalResults();
      });
    });
    document.addEventListener('click', (event) => {
      const result = event.target.closest('.search-result');
      if (result) {
        activateChat(result.dataset.chat, result.dataset.message);
      }
      const tab = event.target.closest('.tab-button');
      if (tab) {
        activateTab(tab);
      }
    });
    if (globalSearch) {
      globalSearch.addEventListener('input', () => {
        applyChatListFilter();
        renderGlobalResults();
      });
    }
    if (chatSearch) {
      chatSearch.addEventListener('input', () => {
        if (splitMode) {
          sendSearchToFrame();
        } else {
          applyLocalSearch(chatSearch.value);
        }
      });
    }
    localSearchInputs.forEach((input) => {
      input.addEventListener('input', () => applyLocalSearch(input.value));
    });
    if (frame) {
      frame.addEventListener('load', sendSearchToFrame);
    }
    window.addEventListener('message', (event) => {
      if (!event.data || event.data.type !== 'chat-search') return;
      applyLocalSearch(event.data.query || '');
    });
    if (location.hash) {
      const [target, messageId] = location.hash.slice(1).split(':');
      if (chatButtons.some((button) => button.dataset.chat === target)) {
        activateChat(target, messageId || '');
      } else if (panels.some((panel) => panel.id === target)) {
        activateChat(target, '');
      } else {
        showMessage(target);
      }
    }
    const back = document.getElementById('back-top');
    const toggleBack = () => {
      if (!back) return;
      if (window.scrollY > 360) {
        back.classList.add('show');
      } else {
        back.classList.remove('show');
      }
    };
    window.addEventListener('scroll', toggleBack);
    toggleBack();
    if (back) {
      back.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    }
    </script>
    """
    return script.replace("__SPLIT_MODE__", str(split).lower())


def _render_footer(handle) -> None:
    handle.write("<footer>Generated by Telegram Message Exporter</footer>")


def _avatar_initial(title: str) -> str:
    for char in title.strip():
        if char.isalnum():
            return char.upper()
    return "T"


def _chat_preview(group: ChatGroup) -> str:
    if not group.messages:
        return ""
    msg = group.messages[-1]
    if msg.text:
        return " ".join(msg.text.split())[:90]
    if msg.attachments:
        return msg.attachments[0].title
    return ""


def _group_time(group: ChatGroup) -> str:
    timestamps = [msg.timestamp for msg in group.messages if msg.timestamp]
    if not timestamps:
        return ""
    return max(timestamps).strftime("%Y-%m-%d")


def _kind_filters() -> tuple[tuple[str, str], ...]:
    return (
        ("all", "All"),
        ("private", "Private"),
        ("group", "Groups"),
        ("channel", "Channels"),
        ("bot", "Bots"),
        ("unknown", "Unknown"),
    )


def _kind_label(kind: str) -> str:
    labels = {
        "private": "Private",
        "group": "Group",
        "channel": "Channel",
        "bot": "Bot",
        "unknown": "Unknown",
    }
    return labels.get(kind, "Unknown")


def _message_dom_id(group: ChatGroup, message_index: int) -> str:
    return f"{group.key}-msg-{message_index}"


def _message_search_text(msg: Message, speaker: str) -> str:
    parts = [speaker, msg.text]
    parts.extend(_attachment_search_text(item) for item in msg.attachments)
    return " ".join(part for part in parts if part).lower()


def _chat_search_text(group: ChatGroup) -> str:
    parts = [group.title, group.kind, _chat_preview(group)]
    for msg in group.messages[-25:]:
        parts.append(msg.text)
        parts.extend(_attachment_search_text(item) for item in msg.attachments)
    return " ".join(part for part in parts if part).lower()


def _attachment_search_text(attachment: Attachment) -> str:
    return " ".join(
        part
        for part in (
            attachment.kind,
            attachment.title,
            attachment.file_name,
            attachment.mime_type,
            attachment.copied_path,
            attachment.reference,
        )
        if part
    ).lower()


def _render_search_index(
    handle,
    groups: tuple[ChatGroup, ...],
    peer_map: Optional[dict[int, str]],
    me_name: str,
) -> None:
    records = []
    for group in groups:
        for message_index, msg in enumerate(group.messages, start=1):
            speaker = resolve_speaker(msg, peer_map, me_name)
            text = " ".join(
                part
                for part in (
                    msg.text,
                    " ".join(attachment.title for attachment in msg.attachments),
                )
                if part
            )
            if not text:
                continue
            ts = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S") if msg.timestamp else ""
            records.append(
                {
                    "chat": group.key,
                    "page": group.page,
                    "kind": group.kind,
                    "title": group.title,
                    "message": _message_dom_id(group, message_index),
                    "speaker": speaker,
                    "time": ts,
                    "text": " ".join(text.split()),
                }
            )
    payload = html.escape(json.dumps(records, ensure_ascii=False), quote=False)
    handle.write(
        f'<script type="application/json" id="search-index">{payload}</script>'
    )


def _attachment_summary(attachment: Attachment) -> str:
    parts = [attachment.title]
    if attachment.mime_type:
        parts.append(attachment.mime_type)
    if attachment.size:
        parts.append(_format_size(attachment.size))
    if attachment.copied_path:
        parts.append(attachment.copied_path)
    elif attachment.reference:
        parts.append(attachment.reference)
    return " | ".join(parts)


def _markdown_attachment(attachment: Attachment) -> str:
    label = attachment.title
    if attachment.copied_path:
        label = f"[{attachment.title}]({attachment.copied_path})"
    details = []
    if attachment.mime_type:
        details.append(attachment.mime_type)
    if attachment.size:
        details.append(_format_size(attachment.size))
    if attachment.reference and not attachment.copied_path:
        details.append(attachment.reference)
    if not attachment.copied_path:
        details.append("not found locally")
    return f"{label} ({', '.join(details)})" if details else label


def _attachment_meta(attachment: Attachment) -> str:
    details = []
    if attachment.mime_type:
        details.append(attachment.mime_type)
    if attachment.size:
        details.append(_format_size(attachment.size))
    if attachment.copied_path:
        details.append("saved locally")
    elif attachment.reference:
        details.append(attachment.reference)
    else:
        details.append("not found locally")
    return " · ".join(details)


def _attachment_icon(attachment: Attachment) -> str:
    icons = {
        "photo": "IMG",
        "gif": "GIF",
        "video": "VID",
        "audio": "AUD",
        "voice": "AUD",
        "file": "DOC",
    }
    return icons.get(attachment.kind, "FILE")


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def _is_image_attachment(attachment: Attachment) -> bool:
    mime = attachment.mime_type or ""
    return attachment.kind in {"photo", "gif"} or mime.startswith("image/")


def _is_video_attachment(attachment: Attachment) -> bool:
    mime = attachment.mime_type or ""
    return attachment.kind == "video" or mime.startswith("video/")


def _is_audio_attachment(attachment: Attachment) -> bool:
    mime = attachment.mime_type or ""
    return attachment.kind in {"audio", "voice"} or mime.startswith("audio/")


def _is_media_attachment(attachment: Attachment) -> bool:
    return (
        _is_image_attachment(attachment)
        or _is_video_attachment(attachment)
        or _is_audio_attachment(attachment)
    )
