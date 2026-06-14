"""Export helpers for Markdown, CSV, and HTML."""

from __future__ import annotations

import csv
import html
import json
import os
from dataclasses import dataclass, replace
from datetime import datetime
from io import StringIO
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
html,
body {
  height: 100%;
  overflow-x: hidden;
}
body {
  margin: 0;
  background: var(--page);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  color: var(--ink);
  letter-spacing: 0;
  overflow: hidden;
}
.export-shell {
  display: grid;
  grid-template-rows: auto 1fr;
  height: 100vh;
  overflow: hidden;
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
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  margin: 0;
  font-size: 17px;
  font-weight: 600;
}
.title-area h1 > span:first-child {
  min-width: 0;
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
  height: calc(100vh - 56px);
  min-height: 0;
  overflow: hidden;
}
.export-layout.single {
  grid-template-columns: minmax(0, 980px);
  justify-content: center;
}
.chat-sidebar {
  background: var(--sidebar);
  border-right: 1px solid var(--sidebar-border);
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
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
.local-search-results {
  display: none;
  position: absolute;
  top: 38px;
  left: 0;
  right: 0;
  z-index: 6;
  max-height: 300px;
  overflow: auto;
  border: 1px solid var(--sidebar-border);
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 35, 55, 0.18);
}
.local-search-results.show { display: block; }
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
  min-width: 0;
}
.search-result:hover { background: #f1f5f8; }
.local-search-result {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: start;
}
.result-title {
  font-size: 12px;
  font-weight: 600;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.result-snippet {
  margin-top: 3px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.3;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}
.result-time {
  color: var(--muted);
  font-size: 11px;
  white-space: nowrap;
  text-align: right;
}
.chat-list {
  display: flex;
  flex-direction: column;
}
.chat-item {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: start;
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
  position: relative;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #2aabee, #77c65a);
  color: #ffffff;
  font-weight: 700;
  flex: 0 0 auto;
  overflow: hidden;
}
.avatar.has-image { background: #d8dee5; }
.avatar img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}
.avatar-fallback {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
}
.avatar.has-image .avatar-fallback { display: none; }
.avatar.has-image.broken .avatar-fallback { display: grid; }
.avatar.has-image.broken img { display: none; }
.chat-item.active .avatar { background: rgba(255, 255, 255, 0.22); }
.chat-item.active .avatar.has-image { background: rgba(255, 255, 255, 0.22); }
.chat-main {
  display: grid;
  gap: 3px;
  min-width: 0;
}
.chat-title-line {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.chat-username {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  color: var(--muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chat-item.active .chat-username {
  color: rgba(255, 255, 255, 0.78);
}
.chat-name {
  display: block;
  flex: 1 1 auto;
  min-width: 0;
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chat-preview {
  display: block;
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
  justify-self: end;
  white-space: nowrap;
}
.kind-badge {
  display: inline-flex;
  flex: 0 0 auto;
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
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
  overflow-anchor: none;
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
.chat-area.split-host { overflow: hidden; }
.chat-panel {
  display: none;
  min-width: 0;
  min-height: 100%;
  overflow-x: hidden;
}
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
  height: 100%;
  min-height: 0;
  border: 0;
}
.chat-tools {
  margin-left: auto;
  display: grid;
  gap: 6px;
  min-width: min(320px, 42vw);
  position: relative;
}
.chat-topbar .chat-meta { min-width: 0; }
.chat-topbar h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.chat-topbar h2 > span:first-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  min-width: 0;
  overflow-anchor: none;
}
.virtual-spacer {
  height: 0;
  min-height: 0;
  pointer-events: none;
}
.virtual-window {
  min-height: 1px;
}
.tab-content { display: none; }
.tab-content.active { display: block; }
.library-grid,
.file-list,
.pinned-list,
.analytics-panel {
  width: min(100%, 860px);
  margin: 0 auto;
  padding: 16px;
  min-width: 0;
}
.library-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
}
.media-library {
  width: min(100%, 900px);
  margin: 0 auto;
  padding: 6px 16px 16px;
  min-width: 0;
}
.library-section {
  margin-top: 12px;
  min-width: 0;
}
.library-heading {
  margin: 0 0 8px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
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
  content-visibility: auto;
  contain-intrinsic-size: 150px 142px;
}
.library-open {
  display: block;
  color: inherit;
  text-decoration: none;
}
.library-item.missing { opacity: 0.82; }
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
.library-thumb.sticker-thumb img {
  width: 100px;
  height: 100px;
  object-fit: contain;
}
.library-title {
  display: block;
  padding: 7px 8px;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.library-meta {
  display: block;
  padding: 0 8px 8px;
  color: var(--muted);
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.message-jump {
  display: block;
  width: calc(100% - 16px);
  margin: 0 8px 8px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--accent);
  cursor: pointer;
  font: inherit;
  font-size: 11px;
  overflow: hidden;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.message-jump:hover { text-decoration: underline; }
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
.msg {
  display: flex;
  margin: 6px 0;
  gap: 8px;
  overflow-anchor: none;
  content-visibility: auto;
  contain-intrinsic-size: 48px;
}
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
.message-badge,
.forwarded {
  width: fit-content;
  max-width: 100%;
  margin: 0 0 4px;
  padding-left: 7px;
  border-left: 3px solid var(--blue);
  color: var(--blue-dark);
  font-size: 12px;
  font-weight: 600;
}
.message-badge {
  border-left: 0;
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(42, 171, 238, 0.12);
}
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
  min-width: 0;
  content-visibility: auto;
  contain-intrinsic-size: 54px;
}
.attachment:hover .attachment-title { text-decoration: underline; }
.attachment.attachment-linked {
  align-items: start;
}
.attachment-title-link {
  display: block;
  color: inherit;
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.attachment-title-link:hover { text-decoration: underline; }
.attachment-message-link {
  width: auto;
  margin: 2px 0 0;
}
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
.attachment-body {
  display: block;
  min-width: 0;
  overflow: hidden;
}
.attachment-title {
  display: block;
  font-weight: 600;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.attachment-meta {
  display: block;
  margin-top: 2px;
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.missing-media {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  max-width: min(100%, 420px);
  padding: 10px;
  border: 1px dashed rgba(42, 171, 238, 0.45);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.58);
  color: var(--muted);
}
.missing-media strong {
  display: block;
  color: var(--ink);
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.missing-media span:last-child {
  display: block;
  min-width: 0;
  font-size: 12px;
}
.media-preview {
  display: block;
  overflow: hidden;
  border-radius: 8px;
  background: #eef3f7;
  max-width: min(100%, 420px);
  content-visibility: auto;
  contain-intrinsic-size: 260px 180px;
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
.media-preview.sticker-preview {
  display: inline-grid;
  place-items: center;
  width: 112px;
  height: 112px;
  padding: 6px;
  background: rgba(255, 255, 255, 0.46);
}
.media-preview.sticker-preview img,
.media-preview.sticker-preview video {
  width: 100px;
  height: 100px;
  object-fit: contain;
}
.pinned-list {
  display: grid;
  gap: 8px;
}
.pinned-item,
.analytics-card {
  display: block;
  min-width: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.78);
  color: inherit;
  text-decoration: none;
  box-shadow: 0 1px 2px var(--shadow);
}
.pinned-item:hover {
  background: #ffffff;
  text-decoration: none;
}
.analytics-panel {
  display: grid;
  gap: 10px;
}
.analytics-card h3 {
  margin: 0 0 8px;
  font-size: 13px;
}
.analytics-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  margin: 6px 0;
}
.analytics-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}
.analytics-value {
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}
.analytics-bar {
  grid-column: 1 / -1;
  height: 6px;
  border-radius: 999px;
  overflow: hidden;
  background: #e9f0f5;
}
.analytics-bar > span {
  display: block;
  height: 100%;
  min-width: 2px;
  background: var(--blue);
}
.sidebar-analytics {
  padding: 10px 12px 12px;
  border-bottom: 1px solid var(--sidebar-border);
  background: #fbfcfd;
}
.sidebar-analytics-title {
  margin-bottom: 7px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}
.sidebar-analytics .analytics-row {
  grid-template-columns: minmax(0, 1fr) auto;
  margin: 5px 0;
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
  html,
  body {
    height: auto;
    min-height: 100%;
  }
  body {
    overflow-y: auto;
    overflow-x: hidden;
  }
  .export-shell {
    height: auto;
    min-height: 100vh;
    overflow: visible;
  }
  .export-header { align-items: flex-start; flex-direction: column; }
  .stats-row { justify-content: flex-start; }
  .export-layout,
  .export-layout.single {
    display: block;
    height: auto;
    overflow: visible;
  }
  .chat-sidebar {
    max-height: 260px;
    border-right: 0;
    border-bottom: 1px solid var(--sidebar-border);
  }
  .chat-area { height: auto; overflow: visible; }
  .split-frame { height: 70vh; }
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
    username: Optional[str] = None
    avatar_path: Optional[str] = None
    page: Optional[str] = None


@dataclass(frozen=True)
class AttachmentItem:
    """Attachment plus the message context needed by library tabs."""

    attachment: Attachment
    message_id: str
    date_label: str


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
    return "Deleted Accounts"


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
                    else "Unknown Date"
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
            if msg.is_pinned:
                handle.write("_Pinned message_\n\n")
            forwarded_from = _forward_source_text(msg, peer_map)
            if forwarded_from:
                handle.write(f"_Forwarded from {forwarded_from}_\n\n")
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
                "forwarded_from",
                "pinned",
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
                    _forward_source_text(msg, peer_map),
                    "yes" if msg.is_pinned else "",
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
    me_info: Optional[PeerInfo] = None,
    split: bool = False,
) -> None:
    """Export messages to a styled HTML transcript."""
    stats = build_html_stats(messages, title, me_name)
    groups = build_chat_groups(messages, peer_map, peer_info, title, me_info=me_info)
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
        _render_header(handle, title, stats, me_info, me_name)
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
        _write_chat_page(page_path, page_group, peer_map, me_name, out_path.parent)
        updated_groups.append(page_group)
    return tuple(updated_groups)


def _write_chat_page(
    page_path: Path,
    group: ChatGroup,
    peer_map: Optional[dict[int, str]],
    me_name: str,
    export_root: Path,
) -> None:
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_group = _adjust_group_paths_for_page(group, export_root, page_path.parent)
    with page_path.open("w", encoding="utf-8") as handle:
        handle.write('<!doctype html><html lang="en"><head><meta charset="utf-8">')
        handle.write(
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
        )
        handle.write(f"<title>{html.escape(page_group.title)}</title>")
        handle.write(f"<style>{HTML_CSS}</style></head><body>")
        handle.write('<div class="chat-area">')
        _render_chat_panel(handle, page_group, True, peer_map, me_name)
        handle.write("</div>")
        handle.write(_export_script(split=False))
        handle.write("</body></html>")


def _adjust_group_paths_for_page(
    group: ChatGroup, export_root: Path, page_dir: Path
) -> ChatGroup:
    messages = []
    for msg in group.messages:
        attachments = []
        for attachment in msg.attachments:
            copied_path = _page_relative_path(
                attachment.copied_path,
                export_root,
                page_dir,
            )
            attachments.append(replace(attachment, copied_path=copied_path))
        messages.append(replace(msg, attachments=tuple(attachments)))
    avatar_path = _page_relative_path(group.avatar_path, export_root, page_dir)
    return replace(group, messages=tuple(messages), avatar_path=avatar_path)


def _page_relative_path(
    copied_path: Optional[str], export_root: Path, page_dir: Path
) -> Optional[str]:
    if not copied_path or "://" in copied_path or Path(copied_path).is_absolute():
        return copied_path
    target = export_root / copied_path
    return os.path.relpath(target, page_dir)


def build_chat_groups(
    messages: list[Message],
    peer_map: Optional[dict[int, str]],
    peer_info: Optional[dict[int, PeerInfo]],
    title: str,
    me_info: Optional[PeerInfo] = None,
) -> tuple[ChatGroup, ...]:
    """Group messages by peer for the Telegram-like all-chats view."""
    grouped: dict[str, list[Message]] = {}
    titles: dict[str, str] = {}
    kinds: dict[str, str] = {}
    usernames: dict[str, Optional[str]] = {}
    avatars: dict[str, Optional[str]] = {}
    for msg in messages:
        key = f"peer-{msg.peer_id}" if msg.peer_id is not None else "unknown"
        chat_title = _chat_title(msg.peer_id, peer_map, peer_info, title)
        chat_kind = _chat_kind(msg.peer_id, peer_info)
        if _is_saved_messages_title(chat_title) or (
            me_info is not None and msg.peer_id == me_info.peer_id
        ):
            chat_title = "Saved Messages"
            chat_kind = "saved"
        grouped.setdefault(key, []).append(msg)
        titles.setdefault(key, chat_title)
        kinds.setdefault(key, chat_kind)
        usernames.setdefault(key, _chat_username(msg.peer_id, peer_info))
        avatars.setdefault(key, _chat_avatar_path(msg.peer_id, peer_info))

    groups = [
        ChatGroup(
            key=key,
            title=titles[key],
            kind=kinds[key],
            messages=tuple(items),
            username=usernames.get(key),
            avatar_path=avatars.get(key),
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


def _chat_username(
    peer_id: Optional[int], peer_info: Optional[dict[int, PeerInfo]]
) -> Optional[str]:
    if peer_id is not None and peer_info and peer_id in peer_info:
        return peer_info[peer_id].username
    return None


def _chat_avatar_path(
    peer_id: Optional[int], peer_info: Optional[dict[int, PeerInfo]]
) -> Optional[str]:
    if peer_id is not None and peer_info and peer_id in peer_info:
        return peer_info[peer_id].avatar_path
    return None


def _latest_group_ts(group: ChatGroup) -> float:
    timestamps = [msg.timestamp.timestamp() for msg in group.messages if msg.timestamp]
    return max(timestamps) if timestamps else 0


def _render_header(
    handle,
    title: str,
    stats: HtmlStats,
    me_info: Optional[PeerInfo],
    me_name: str,
) -> None:
    handle.write('<header class="export-header">')
    handle.write('<div class="brand">')
    _render_avatar(
        handle,
        me_info.title if me_info else me_name,
        me_info.avatar_path if me_info else None,
    )
    handle.write('<div class="title-area">')
    handle.write(
        f"<h1><span>{html.escape(_header_title(title, me_info, me_name))}</span></h1>"
    )
    handle.write(
        '<p class="subtitle">Recovery export for Telegram Desktop (macOS).</p>'
    )
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


def _header_title(
    title: str,
    me_info: Optional[PeerInfo],
    me_name: str,
) -> str:
    nickname = me_info.title if me_info else me_name
    if me_info and me_info.username:
        return f"{title} - {nickname} ({me_info.username})"
    if nickname:
        return f"{title} - {nickname}"
    return title


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
    area_class = "chat-area split-host" if split else "chat-area"
    handle.write(f'<div class="{area_class}">')
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
    handle.write("</div>")
    _render_sidebar_analytics(handle, groups)
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
        _render_avatar(handle, group.title, group.avatar_path)
        handle.write('<span class="chat-main">')
        handle.write('<span class="chat-title-line">')
        handle.write(f'<span class="chat-name">{html.escape(group.title)}</span>')
        if group.username and group.username != group.title:
            handle.write(
                f'<span class="chat-username">{html.escape(group.username)}</span>'
            )
        handle.write(
            f'<span class="kind-badge">{html.escape(_kind_label(group.kind))}</span>'
        )
        handle.write("</span>")
        handle.write(
            f'<span class="chat-preview">{html.escape(_chat_preview(group))}</span>'
        )
        handle.write("</span>")
        handle.write(f'<span class="chat-time">{_group_time(group)}</span>')
        handle.write("</button>")
    handle.write("</div></aside>")


def _render_sidebar_analytics(handle, groups: tuple[ChatGroup, ...]) -> None:
    top_by_messages = sorted(
        groups,
        key=lambda group: len(group.messages),
        reverse=True,
    )[:5]
    if not top_by_messages:
        return
    rows = [(group.title, len(group.messages)) for group in top_by_messages]
    file_rows = sorted(
        (
            (group.title, sum(len(msg.attachments) for msg in group.messages))
            for group in groups
        ),
        key=lambda item: item[1],
        reverse=True,
    )[:5]
    handle.write('<div class="sidebar-analytics">')
    handle.write('<div class="sidebar-analytics-title">Top chats</div>')
    _render_analytics_rows(handle, rows)
    if any(value for _, value in file_rows):
        handle.write('<div class="sidebar-analytics-title">Top files</div>')
        _render_analytics_rows(handle, file_rows)
    handle.write("</div>")


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
    handle.write('<div class="tab-content urls-tab" data-tab-panel="urls">')
    _render_url_library(handle, group)
    handle.write("</div>")
    if any(msg.is_pinned for msg in group.messages):
        handle.write('<div class="tab-content pinned-tab" data-tab-panel="pinned">')
        _render_pinned_messages(handle, group, peer_map, me_name)
        handle.write("</div>")
    handle.write(
        '<div class="tab-content analytics-tab" data-tab-panel="analytics">'
    )
    _render_chat_analytics(handle, group)
    handle.write("</div>")


def _render_message_list(
    handle,
    group: ChatGroup,
    peer_map: Optional[dict[int, str]],
    me_name: str,
) -> None:
    if _should_virtualize_messages(group):
        _render_virtual_message_list(handle, group, peer_map, me_name)
        return

    handle.write('<div class="messages">')
    current_date = None
    for message_index, msg in enumerate(group.messages, start=1):
        current_date = _render_message_entry(
            handle,
            group,
            msg,
            message_index,
            peer_map,
            me_name,
            current_date,
        )
    handle.write("</div>")


def _should_virtualize_messages(group: ChatGroup) -> bool:
    return len(group.messages) > 300


def _render_virtual_message_list(
    handle,
    group: ChatGroup,
    peer_map: Optional[dict[int, str]],
    me_name: str,
) -> None:
    items = []
    current_date = None
    for message_index, msg in enumerate(group.messages, start=1):
        msg_date, day_label, time_str = _message_date_parts(msg)
        if current_date != msg_date:
            current_date = msg_date
            items.append(
                {
                    "type": "day",
                    "id": f"{group.key}-day-{msg_date}",
                    "html": _day_html(group, msg_date, day_label),
                    "height": 42,
                }
            )

        speaker = resolve_speaker(msg, peer_map, me_name)
        message_id = _message_dom_id(group, message_index)
        search_text = _message_search_text(msg, speaker, peer_map)
        snippet = _message_snippet(msg)
        items.append(
            {
                "type": "message",
                "id": message_id,
                "html": _message_entry_html(
                    group,
                    msg,
                    message_index,
                    peer_map,
                    me_name,
                    include_day=False,
                ),
                "search": search_text,
                "speaker": speaker,
                "time": [msg_date, time_str],
                "snippet": snippet or search_text,
                "height": _estimated_message_height(msg),
            }
        )

    payload = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    handle.write(
        '<div class="messages virtual-messages" data-virtual-messages="true">'
    )
    handle.write('<div class="virtual-spacer virtual-before"></div>')
    handle.write('<div class="virtual-window"></div>')
    handle.write('<div class="virtual-spacer virtual-after"></div>')
    handle.write(
        '<script class="virtual-message-data" type="application/json">'
        f"{payload}</script>"
    )
    handle.write("</div>")


def _estimated_message_height(msg: Message) -> int:
    text_height = min(220, max(0, len(msg.text)) // 4)
    attachment_height = sum(
        _estimated_attachment_height(item) for item in msg.attachments
    )
    metadata_height = 18
    if msg.is_pinned:
        metadata_height += 22
    if msg.forward_info:
        metadata_height += 22
    return max(48, 42 + metadata_height + text_height + attachment_height)


def _estimated_attachment_height(attachment: Attachment) -> int:
    if _is_media_attachment(attachment):
        return 180
    return 58


def _day_html(group: ChatGroup, msg_date: str, day_label: str) -> str:
    return (
        f'<div id="{html.escape(group.key)}-day-{html.escape(msg_date)}" '
        f'class="day">{html.escape(day_label)}</div>'
    )


def _message_entry_html(
    group: ChatGroup,
    msg: Message,
    message_index: int,
    peer_map: Optional[dict[int, str]],
    me_name: str,
    include_day: bool = False,
    current_date: Optional[str] = None,
) -> str:
    buffer = StringIO()
    _render_message_entry(
        buffer,
        group,
        msg,
        message_index,
        peer_map,
        me_name,
        current_date,
        include_day=include_day,
    )
    return buffer.getvalue()


def _render_message_entry(
    handle,
    group: ChatGroup,
    msg: Message,
    message_index: int,
    peer_map: Optional[dict[int, str]],
    me_name: str,
    current_date: Optional[str],
    include_day: bool = True,
) -> str:
    msg_date, day_label, time_str = _message_date_parts(msg)
    if include_day and current_date != msg_date:
        handle.write(_day_html(group, msg_date, day_label))
    speaker = resolve_speaker(msg, peer_map, me_name)
    direction = "out" if msg.outgoing is True else "in"
    pinned_class = " pinned" if msg.is_pinned else ""
    search_text = _message_search_text(msg, speaker, peer_map)
    message_id = _message_dom_id(group, message_index)
    forward_label = _forward_source_text(msg, peer_map)
    handle.write(
        f'<div id="{message_id}" class="msg {direction}{pinned_class}" '
        f'data-date="{html.escape(msg_date, quote=True)}" '
        f'data-time="{html.escape(time_str, quote=True)}" '
        f'data-search="{html.escape(search_text, quote=True)}">'
    )
    handle.write('<div class="bubble">')
    handle.write(f'<div class="meta">{html.escape(speaker)}</div>')
    if msg.is_pinned:
        handle.write('<div class="message-badge">Pinned</div>')
    if forward_label:
        handle.write(
            '<div class="forwarded">'
            f'Forwarded from {html.escape(forward_label)}</div>'
        )
    if msg.text:
        handle.write(f'<div class="message-text">{linkify_html(msg.text)}</div>')
    _render_attachments(handle, msg.attachments)
    handle.write(f'<span class="time">{html.escape(time_str)}</span>')
    handle.write("</div></div>")
    return msg_date


def _render_chat_topbar(handle, group: ChatGroup) -> None:
    attachment_count = sum(len(msg.attachments) for msg in group.messages)
    handle.write('<div class="chat-topbar">')
    _render_avatar(handle, group.title, group.avatar_path)
    handle.write('<div class="chat-meta">')
    handle.write("<h2>")
    handle.write(f"<span>{html.escape(group.title)}</span>")
    if group.username and group.username != group.title:
        handle.write(
            f'<span class="chat-username">{html.escape(group.username)}</span>'
        )
    handle.write("</h2>")
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
    handle.write('<div class="local-search-results"></div>')
    handle.write('<div class="tabs" aria-label="Chat sections">')
    tabs = [
        ("messages", "Messages"),
        ("media", "Media"),
        ("files", "Files"),
        ("urls", "Urls"),
    ]
    if any(msg.is_pinned for msg in group.messages):
        tabs.append(("pinned", "Pinned"))
    tabs.append(("analytics", "Analytics"))
    for tab, label in tabs:
        active = " active" if tab == "messages" else ""
        handle.write(
            f'<button class="tab-button{active}" type="button" '
            f'data-tab="{tab}">{label}</button>'
        )
    handle.write("</div></div>")
    handle.write("</div>")


def _render_avatar(handle, title: str, avatar_path: Optional[str] = None) -> None:
    initial = html.escape(_avatar_initial(title))
    if avatar_path:
        src = html.escape(avatar_path, quote=True)
        handle.write(
            '<span class="avatar has-image">'
            f'<span class="avatar-fallback">{initial}</span>'
            f'<img src="{src}" alt="" loading="lazy" decoding="async" '
            'onerror="this.parentElement.classList.add(\'broken\')">'
            "</span>"
        )
        return
    handle.write(
        '<span class="avatar missing" title="Avatar not found in local cache">'
        f"{initial}</span>"
    )


def _render_media_library(handle, group: ChatGroup) -> None:
    media_items = [
        item
        for item in _attachment_items(group)
        if _is_media_attachment(item.attachment)
    ]
    if not media_items:
        handle.write('<div class="empty-state">No media in this chat</div>')
        return
    sections = (
        ("Photos", _is_photo_attachment),
        ("GIFs", _is_gif_attachment),
        ("Stickers", _is_sticker_attachment),
        ("Videos", _is_video_only_attachment),
        ("Audio", _is_audio_attachment),
        ("Locations", lambda attachment: attachment.kind == "location"),
    )
    used_ids: set[int] = set()
    handle.write('<div class="media-library">')
    for label, predicate in sections:
        items = [item for item in media_items if predicate(item.attachment)]
        if not items:
            continue
        used_ids.update(id(item) for item in items)
        handle.write('<section class="library-section">')
        handle.write(f'<h3 class="library-heading">{html.escape(label)}</h3>')
        handle.write('<div class="library-grid">')
        for attachment in items:
            _render_library_item(handle, attachment)
        handle.write("</div></section>")
    leftovers = [item for item in media_items if id(item) not in used_ids]
    if leftovers:
        handle.write('<section class="library-section">')
        handle.write('<h3 class="library-heading">Other</h3>')
        handle.write('<div class="library-grid">')
        for attachment in leftovers:
            _render_library_item(handle, attachment)
        handle.write("</div></section>")
    handle.write("</div>")


def _render_file_library(handle, group: ChatGroup) -> None:
    file_items = [
        item
        for item in _attachment_items(group)
        if not _is_media_attachment(item.attachment)
        and not _is_url_attachment(item.attachment)
    ]
    if not file_items:
        handle.write('<div class="empty-state">No files in this chat</div>')
        return
    handle.write('<div class="file-list">')
    for item in file_items:
        _render_file_attachment(handle, item.attachment, item)
    handle.write("</div>")


def _render_url_library(handle, group: ChatGroup) -> None:
    url_items = [
        item
        for item in _attachment_items(group)
        if _is_url_attachment(item.attachment)
    ]
    if not url_items:
        handle.write('<div class="empty-state">No urls in this chat</div>')
        return
    handle.write('<div class="file-list">')
    for item in url_items:
        _render_file_attachment(handle, item.attachment, item)
    handle.write("</div>")


def _attachment_items(group: ChatGroup) -> list[AttachmentItem]:
    items = []
    for message_index, msg in enumerate(group.messages, start=1):
        date_label = _message_datetime_label(msg)
        message_id = _message_dom_id(group, message_index)
        for attachment in msg.attachments:
            items.append(AttachmentItem(attachment, message_id, date_label))
    return items


def _render_pinned_messages(
    handle,
    group: ChatGroup,
    peer_map: Optional[dict[int, str]],
    me_name: str,
) -> None:
    pinned = [
        (message_index, msg)
        for message_index, msg in enumerate(group.messages, start=1)
        if msg.is_pinned
    ]
    if not pinned:
        handle.write('<div class="empty-state">No pinned messages in this chat</div>')
        return
    handle.write('<div class="pinned-list">')
    for message_index, msg in pinned:
        speaker = resolve_speaker(msg, peer_map, me_name)
        date_label = (
            msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            if msg.timestamp
            else "Unknown date"
        )
        snippet = _message_snippet(msg)
        message_id = _message_dom_id(group, message_index)
        handle.write(
            f'<a class="pinned-item" href="#{message_id}" '
            f'data-message-link="{message_id}">'
        )
        handle.write(
            '<div class="result-title">'
            f"{html.escape(speaker)} - {html.escape(date_label)}</div>"
        )
        handle.write(
            f'<div class="result-snippet">{html.escape(snippet)}</div>'
        )
        handle.write("</a>")
    handle.write("</div>")


def _render_chat_analytics(handle, group: ChatGroup) -> None:
    message_count = len(group.messages)
    attachment_count = sum(len(msg.attachments) for msg in group.messages)
    pinned_count = sum(1 for msg in group.messages if msg.is_pinned)
    attachments = [
        attachment
        for msg in group.messages
        for attachment in msg.attachments
    ]
    rows = [
        ("Messages", message_count),
        ("Files and media", attachment_count),
        ("Pinned", pinned_count),
        ("Urls", sum(_is_url_attachment(item) for item in attachments)),
        ("Photos", sum(_is_photo_attachment(item) for item in attachments)),
        ("GIFs", sum(_is_gif_attachment(item) for item in attachments)),
        ("Stickers", sum(_is_sticker_attachment(item) for item in attachments)),
    ]
    handle.write('<div class="analytics-panel">')
    handle.write('<div class="analytics-card">')
    handle.write("<h3>Chat activity</h3>")
    _render_analytics_rows(handle, rows)
    handle.write("</div></div>")


def _render_analytics_rows(handle, rows: list[tuple[str, int]]) -> None:
    max_value = max((value for _, value in rows), default=0)
    for label, value in rows:
        if max_value:
            width = max(2, round(value / max_value * 100)) if value else 0
        else:
            width = 0
        handle.write('<div class="analytics-row">')
        handle.write(f'<span class="analytics-label">{html.escape(label)}</span>')
        handle.write(f'<span class="analytics-value">{value}</span>')
        handle.write(
            '<span class="analytics-bar">'
            f'<span style="width:{width}%"></span></span>'
        )
        handle.write("</div>")


def _render_library_item(handle, item: AttachmentItem) -> None:
    attachment = item.attachment
    if attachment.copied_path:
        open_tag = (
            '<a class="library-open" '
            f'href="{html.escape(attachment.copied_path, quote=True)}" '
            'target="_blank">'
        )
        close_tag = "</a>"
    else:
        open_tag = '<span class="library-open">'
        close_tag = "</span>"
    search_text = _attachment_search_text(attachment)
    missing_class = " missing" if not attachment.copied_path else ""
    sticker_class = " sticker-item" if _is_sticker_attachment(attachment) else ""
    handle.write(
        f'<div class="library-item{missing_class}{sticker_class}" '
        f'data-search="{html.escape(search_text, quote=True)}">'
    )
    handle.write(open_tag)
    thumb_class = "library-thumb sticker-thumb" if sticker_class else "library-thumb"
    handle.write(f'<span class="{thumb_class}">')
    if attachment.copied_path and _is_image_attachment(attachment):
        src = html.escape(attachment.copied_path, quote=True)
        title = html.escape(attachment.title, quote=True)
        handle.write(
            f'<img src="{src}" alt="{title}" loading="lazy" decoding="async">'
        )
    elif attachment.copied_path and _is_video_attachment(attachment):
        src = html.escape(attachment.copied_path, quote=True)
        handle.write(f'<video preload="none" src="{src}"></video>')
    else:
        handle.write(html.escape(_attachment_icon(attachment)))
    handle.write("</span>")
    handle.write(
        f'<span class="library-title">{html.escape(attachment.title)}</span>'
    )
    handle.write(close_tag)
    handle.write(
        '<button class="message-jump" type="button" '
        f'data-message-link="{html.escape(item.message_id, quote=True)}">'
        f"{html.escape(item.date_label)}</button>"
    )
    if not attachment.copied_path:
        handle.write('<span class="library-meta">not found locally</span>')
    handle.write("</div>")


def _render_attachments(handle, attachments: tuple[Attachment, ...]) -> None:
    if not attachments:
        return
    handle.write('<div class="attachments">')
    for attachment in attachments:
        if _render_media_preview(handle, attachment):
            continue
        if _is_media_attachment(attachment) and _is_downloadable_attachment(attachment):
            _render_missing_media(handle, attachment)
            continue
        _render_file_attachment(handle, attachment)
    handle.write("</div>")


def _render_media_preview(handle, attachment: Attachment) -> bool:
    if not attachment.copied_path:
        return False
    src = html.escape(attachment.copied_path, quote=True)
    title = html.escape(attachment.title, quote=True)
    if _is_image_attachment(attachment):
        preview_class = (
            "media-preview sticker-preview"
            if _is_sticker_attachment(attachment)
            else "media-preview"
        )
        handle.write(f'<a class="{preview_class}" href="{src}" target="_blank">')
        handle.write(
            f'<img src="{src}" alt="{title}" loading="lazy" decoding="async">'
        )
        handle.write("</a>")
        return True
    if _is_video_attachment(attachment):
        preview_class = (
            "media-preview sticker-preview"
            if _is_sticker_attachment(attachment)
            else "media-preview"
        )
        handle.write(f'<div class="{preview_class}">')
        handle.write(f'<video controls preload="none" src="{src}"></video>')
        handle.write("</div>")
        return True
    if _is_audio_attachment(attachment):
        handle.write('<div class="media-preview">')
        handle.write(f'<audio controls preload="none" src="{src}"></audio>')
        handle.write("</div>")
        return True
    return False


def _render_missing_media(handle, attachment: Attachment) -> None:
    title = html.escape(attachment.title)
    meta = html.escape(_attachment_meta(attachment))
    icon = html.escape(_attachment_icon(attachment))
    handle.write('<div class="missing-media">')
    handle.write(f'<span class="attachment-icon">{icon}</span>')
    handle.write("<span>")
    handle.write(f"<strong>{title}</strong>")
    handle.write(f"<span>{meta}</span>")
    handle.write("</span></div>")


def _render_file_attachment(
    handle,
    attachment: Attachment,
    context: Optional[AttachmentItem] = None,
) -> None:
    href = ""
    tag = "div"
    if attachment.copied_path:
        tag = "a"
        href = (
            f' href="{html.escape(attachment.copied_path, quote=True)}"'
            ' target="_blank"'
        )
    elif attachment.kind in {"location", "webpage"} and attachment.reference:
        tag = "a"
        href = (
            f' href="{html.escape(attachment.reference, quote=True)}"'
            ' target="_blank"'
        )
    if context is None:
        search_text = html.escape(_attachment_search_text(attachment), quote=True)
        handle.write(f'<{tag} class="attachment"{href} data-search="{search_text}">')
        _render_file_attachment_body(handle, attachment)
        handle.write(f"</{tag}>")
        return

    search_text = html.escape(_attachment_search_text(attachment), quote=True)
    handle.write(
        f'<div class="attachment attachment-linked" data-search="{search_text}">'
    )
    handle.write(f'<span class="attachment-icon">{_attachment_icon(attachment)}</span>')
    handle.write('<span class="attachment-body">')
    title = html.escape(attachment.title)
    if href:
        handle.write(f'<a class="attachment-title-link"{href}>{title}</a>')
    else:
        handle.write(f'<span class="attachment-title">{title}</span>')
    meta = html.escape(_attachment_meta(attachment))
    handle.write(f'<span class="attachment-meta">{meta}</span>')
    handle.write(
        '<button class="message-jump attachment-message-link" type="button" '
        f'data-message-link="{html.escape(context.message_id, quote=True)}">'
        f"{html.escape(context.date_label)}</button>"
    )
    handle.write("</span>")
    handle.write("</div>")


def _render_file_attachment_body(handle, attachment: Attachment) -> None:
    handle.write(f'<span class="attachment-icon">{_attachment_icon(attachment)}</span>')
    handle.write('<span class="attachment-body">')
    handle.write(
        f'<span class="attachment-title">{html.escape(attachment.title)}</span>'
    )
    meta = html.escape(_attachment_meta(attachment))
    handle.write(f'<span class="attachment-meta">{meta}</span>')
    handle.write("</span>")


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


def _message_datetime_label(msg: Message) -> str:
    if msg.timestamp:
        return msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    return "Unknown date"


def _export_script(split: bool = False) -> str:
    script = """
    <script>
    const splitMode = __SPLIT_MODE__;
    const chatButtons = Array.from(document.querySelectorAll('.chat-item'));
    const panels = Array.from(document.querySelectorAll('.chat-panel'));
    const frame = document.getElementById('chat-frame');
    const chatArea = document.querySelector('.chat-area');
    const globalSearch = document.getElementById('global-search');
    const localSearchInputs = Array.from(
      document.querySelectorAll('.local-chat-search')
    );
    const resultsBox = document.getElementById('search-results');
    const searchIndexEl = document.getElementById('search-index');
    const localSearchCache = new WeakMap();
    const virtualMessageStates = [];
    const virtualMessages = new WeakMap();
    let searchIndex = null;
    let virtualRenderFrame = 0;

    const getSearchIndex = () => {
      if (!searchIndexEl) return [];
      if (searchIndex === null) {
        searchIndex = JSON.parse(searchIndexEl.textContent || '[]');
        searchIndexEl.textContent = '';
      }
      return searchIndex;
    };

    const activeKind = () => {
      const active = document.querySelector('.filter-button.active');
      return active ? active.dataset.kind : 'all';
    };

    const activePanel = () => document.querySelector('.chat-panel.active') || document;

    const activeLocalSearchInput = () =>
      activePanel().querySelector('.local-chat-search');

    const isMobileLayout = () => window.matchMedia('(max-width: 760px)').matches;

    const pageScrollRoot = () =>
      document.scrollingElement || document.documentElement || document.body;

    const primaryScrollRoot = () => {
      if (isMobileLayout()) {
        return pageScrollRoot();
      }
      if (chatArea && chatArea.scrollHeight > chatArea.clientHeight) {
        return chatArea;
      }
      return pageScrollRoot();
    };

    const scrollTopOf = (root) =>
      root === document.body || root === document.documentElement
        ? Math.max(
            window.scrollY,
            document.documentElement.scrollTop,
            document.body.scrollTop
          )
        : root.scrollTop;

    const setScrollTop = (root, value) => {
      const top = Math.max(0, value);
      if (root === document.body || root === document.documentElement) {
        document.documentElement.scrollTop = top;
        document.body.scrollTop = top;
        window.scrollTo(0, top);
      } else {
        root.scrollTop = top;
      }
    };

    const scrollElementToCenter = (target, behavior = 'smooth') => {
      const root = primaryScrollRoot();
      const pageRoot = pageScrollRoot();
      const rootRect = root === pageRoot
        ? { top: 0, height: window.innerHeight }
        : root.getBoundingClientRect();
      const rect = target.getBoundingClientRect();
      const centeredTop = scrollTopOf(root)
        + rect.top
        - rootRect.top
        - (rootRect.height - rect.height) / 2;
      if (root === pageRoot && behavior === 'smooth') {
        window.scrollTo({ top: Math.max(0, centeredTop), behavior });
      } else if (root === pageRoot) {
        setScrollTop(root, centeredTop);
      } else if (root.scrollTo) {
        root.scrollTo({ top: Math.max(0, centeredTop), behavior });
      } else {
        setScrollTop(root, centeredTop);
      }
    };

    const findVirtualIndex = (prefix, value) => {
      let low = 0;
      let high = prefix.length - 1;
      while (low < high) {
        const middle = Math.floor((low + high) / 2);
        if (prefix[middle] < value) {
          low = middle + 1;
        } else {
          high = middle;
        }
      }
      return Math.max(0, low - 1);
    };

    const rebuildVirtualPrefix = (state) => {
      state.prefix = [0];
      state.heights.forEach((height) => {
        state.prefix.push(state.prefix[state.prefix.length - 1] + height);
      });
      state.totalHeight = state.prefix[state.prefix.length - 1];
    };

    const elementOuterHeight = (element) => {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      const marginTop = parseFloat(style.marginTop) || 0;
      const marginBottom = parseFloat(style.marginBottom) || 0;
      return Math.max(1, Math.ceil(rect.height + marginTop + marginBottom));
    };

    const currentVirtualAnchor = (state) => {
      const root = primaryScrollRoot();
      const pageRoot = pageScrollRoot();
      const rootRect = root === pageRoot
        ? { top: 0, height: window.innerHeight }
        : root.getBoundingClientRect();
      const children = Array.from(state.window.children);
      for (const child of children) {
        const rect = child.getBoundingClientRect();
        if (rect.bottom >= rootRect.top) {
          return { id: child.id, top: rect.top };
        }
      }
      return null;
    };

    const measureVirtualHeights = (state, anchor = null) => {
      let changed = false;
      Array.from(state.window.children).forEach((child) => {
        const index = state.itemIndex[child.id];
        if (index === undefined) return;
        const measured = elementOuterHeight(child);
        if (Math.abs((state.heights[index] || 0) - measured) > 1) {
          state.heights[index] = measured;
          changed = true;
        }
      });
      if (!changed) return;
      rebuildVirtualPrefix(state);
      state.before.style.height = `${state.prefix[state.start]}px`;
      state.after.style.height = `${state.totalHeight - state.prefix[state.end]}px`;
      if (!anchor || !anchor.id) return;
      const anchored = document.getElementById(anchor.id);
      if (!anchored) return;
      const delta = anchored.getBoundingClientRect().top - anchor.top;
      if (Math.abs(delta) > 1) {
        const root = primaryScrollRoot();
        setScrollTop(root, scrollTopOf(root) + delta);
      }
    };

    const renderVirtualRange = (state, start, end) => {
      const itemCount = state.items.length;
      const safeStart = Math.max(0, Math.min(itemCount, start));
      const safeEnd = Math.max(safeStart, Math.min(itemCount, end));
      if (state.start === safeStart && state.end === safeEnd) {
        measureVirtualHeights(state, currentVirtualAnchor(state));
        return;
      }
      const anchor = currentVirtualAnchor(state);
      state.before.style.height = `${state.prefix[safeStart]}px`;
      state.after.style.height = `${state.totalHeight - state.prefix[safeEnd]}px`;
      state.window.innerHTML = state.items
        .slice(safeStart, safeEnd)
        .map((item) => item.html)
        .join('');
      state.start = safeStart;
      state.end = safeEnd;
      measureVirtualHeights(state, anchor);
    };

    const renderVirtualWindow = (state) => {
      if (!state.container.offsetParent) return;
      const root = primaryScrollRoot();
      const pageRoot = pageScrollRoot();
      const rootRect = root === pageRoot
        ? { top: 0, height: window.innerHeight }
        : root.getBoundingClientRect();
      const containerRect = state.container.getBoundingClientRect();
      const rootTop = scrollTopOf(root);
      const containerTop = rootTop + containerRect.top - rootRect.top;
      const visibleTop = Math.max(0, rootTop - containerTop);
      const visibleBottom = visibleTop + rootRect.height;
      if (state.start >= 0 && state.end >= 0) {
        const renderedTop = state.prefix[state.start];
        const renderedBottom = state.prefix[state.end];
        const safeTop = renderedTop + state.edgeBuffer;
        const safeBottom = renderedBottom - state.edgeBuffer;
        if (visibleTop >= safeTop && visibleBottom <= safeBottom) {
          measureVirtualHeights(state, currentVirtualAnchor(state));
          return;
        }
      }
      const viewportTop = Math.max(0, visibleTop - state.overscan);
      const viewportBottom = rootTop
        - containerTop
        + rootRect.height
        + state.overscan;
      const start = findVirtualIndex(state.prefix, viewportTop);
      let end = findVirtualIndex(state.prefix, viewportBottom) + 1;
      end = Math.max(end, start + state.minItems);
      renderVirtualRange(state, start, end);
    };

    const scheduleVirtualRender = () => {
      if (virtualRenderFrame) return;
      virtualRenderFrame = window.requestAnimationFrame(() => {
        virtualRenderFrame = 0;
        virtualMessageStates.forEach(renderVirtualWindow);
      });
    };

    const initVirtualMessages = (root = document) => {
      root.querySelectorAll('.virtual-messages').forEach((container) => {
        if (virtualMessages.has(container)) return;
        const data = container.querySelector('.virtual-message-data');
        const before = container.querySelector('.virtual-before');
        const windowEl = container.querySelector('.virtual-window');
        const after = container.querySelector('.virtual-after');
        if (!data || !before || !windowEl || !after) return;
        const items = JSON.parse(data.textContent || '[]');
        data.textContent = '';
        const heights = [];
        const prefix = [0];
        const itemIndex = {};
        const messageIndex = {};
        const search = [];
        items.forEach((item, index) => {
          const height = item.height || 64;
          heights.push(height);
          prefix.push(prefix[prefix.length - 1] + height);
          itemIndex[item.id] = index;
          if (item.type === 'message') {
            messageIndex[item.id] = index;
            search.push({
              id: item.id,
              haystack: item.search || '',
              speaker: item.speaker || '',
              time: (item.time || []).filter(Boolean).join(' '),
              snippet: item.snippet || item.search || ''
            });
          }
        });
        const state = {
          after,
          before,
          container,
          edgeBuffer: 2200,
          end: -1,
          heights,
          itemIndex,
          items,
          messageIndex,
          minItems: 280,
          overscan: 7600,
          prefix,
          search,
          start: -1,
          totalHeight: prefix[prefix.length - 1],
          window: windowEl
        };
        virtualMessages.set(container, state);
        virtualMessageStates.push(state);
        renderVirtualWindow(state);
      });
    };

    const virtualStateForPanel = (panel) => {
      const container = panel ? panel.querySelector('.virtual-messages') : null;
      if (!container) return null;
      if (!virtualMessages.has(container)) {
        initVirtualMessages(panel);
      }
      return virtualMessages.get(container);
    };

    const ensureMessageRendered = (messageId) => {
      initVirtualMessages(activePanel());
      for (const state of virtualMessageStates) {
        const index = state.messageIndex[messageId];
        if (index === undefined) continue;
        const start = Math.max(0, index - 70);
        const end = Math.min(state.items.length, index + 110);
        renderVirtualRange(state, start, end);
        return document.getElementById(messageId);
      }
      return null;
    };

    const closeLocalSearch = (panel = document) => {
      panel.querySelectorAll('.local-search-results').forEach((box) => {
        box.classList.remove('show');
      });
      panel.querySelectorAll('.local-chat-search').forEach((input) => {
        input.blur();
      });
      if (document.activeElement && document.activeElement.blur) {
        document.activeElement.blur();
      }
    };

    const scrollChatTop = () => {
      closeLocalSearch();
      const roots = [
        primaryScrollRoot(),
        document.scrollingElement,
        document.documentElement,
        document.body,
        chatArea
      ].filter(Boolean);
      roots.forEach((root) => {
        if (root.scrollTo) {
          root.scrollTo({ top: 0, left: 0, behavior: 'smooth' });
        } else {
          root.scrollTop = 0;
          root.scrollLeft = 0;
        }
      });
      if (chatArea) {
        chatArea.scrollTop = 0;
        chatArea.scrollLeft = 0;
      }
      window.scrollTo({ top: 0, behavior: 'smooth' });
      window.requestAnimationFrame(() => {
        roots.forEach((root) => {
          setScrollTop(root, 0);
          root.scrollLeft = 0;
        });
        window.scrollTo(0, 0);
      });
    };

    const showMessage = (messageId) => {
      if (!messageId) return;
      let target = document.getElementById(messageId);
      const renderedFromVirtual = !target;
      if (!target) {
        target = ensureMessageRendered(messageId);
      }
      if (!target) return;
      target.classList.add('highlight');
      scrollElementToCenter(target, renderedFromVirtual ? 'auto' : 'smooth');
      const ensureVisible = () => {
        const freshTarget = document.getElementById(messageId)
          || ensureMessageRendered(messageId);
        if (!freshTarget) return;
        freshTarget.classList.add('highlight');
        const freshRect = freshTarget.getBoundingClientRect();
        if (freshRect.bottom < 0 || freshRect.top > window.innerHeight) {
          scrollElementToCenter(freshTarget, 'auto');
        }
      };
      window.setTimeout(ensureVisible, 450);
      window.setTimeout(ensureVisible, 950);
      window.setTimeout(() => {
        const freshTarget = document.getElementById(messageId);
        if (freshTarget) freshTarget.classList.remove('highlight');
      }, 1800);
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
        initVirtualMessages(activePanel());
        if (messageId) {
          closeLocalSearch(activePanel());
        } else {
          renderLocalResults(activeLocalSearchInput());
        }
        showMessage(messageId);
      }
      if (history.replaceState) {
        history.replaceState(null, '', '#' + id + (messageId ? ':' + messageId : ''));
      }
      if (!messageId) {
        scrollChatTop();
      }
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

    const visibleChatCount = () =>
      chatButtons.filter((button) => !button.classList.contains('hidden')).length;

    const renderGlobalResults = () => {
      if (!resultsBox || !globalSearch) return;
      const query = globalSearch.value.trim().toLowerCase();
      if (query.length < 2) {
        resultsBox.classList.remove('show');
        resultsBox.innerHTML = '';
        return;
      }
      const kind = activeKind();
      const matches = [];
      for (const item of getSearchIndex()) {
        const kindOk = kind === 'all' || item.kind === kind;
        const haystack = [item.title, item.username, item.speaker, item.text]
          .join(' ')
          .toLowerCase();
        if (kindOk && haystack.includes(query)) {
          matches.push(item);
          if (matches.length >= 80) break;
        }
      }
      if (!matches.length) {
        if (visibleChatCount() > 0) {
          resultsBox.classList.remove('show');
          resultsBox.innerHTML = '';
          return;
        }
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

    const searchPanelForInput = (input) =>
      input ? input.closest('.chat-panel') || document : activePanel();

    const localResultsBox = (panel) =>
      panel ? panel.querySelector('.local-search-results') : null;

    const localSearchIndexFor = (panel) => {
      if (!panel) return [];
      const virtualState = virtualStateForPanel(panel);
      if (virtualState) return virtualState.search;
      if (localSearchCache.has(panel)) return localSearchCache.get(panel);
      const index = Array.from(panel.querySelectorAll('.msg')).map((node) => {
        const text = node.querySelector('.message-text');
        const attachments = Array.from(node.querySelectorAll('.attachment-title'))
          .map((item) => item.textContent || '')
          .join(' ');
        const snippet = [text ? text.textContent : '', attachments]
          .join(' ')
          .replace(/\\s+/g, ' ')
          .trim();
        const speaker = node.querySelector('.meta');
        const date = node.dataset.date || '';
        const time = node.dataset.time || '';
        return {
          id: node.id,
          haystack: node.dataset.search || snippet.toLowerCase(),
          speaker: speaker ? speaker.textContent : '',
          time: [date, time].filter(Boolean).join(' '),
          snippet: snippet || node.dataset.search || ''
        };
      });
      localSearchCache.set(panel, index);
      return index;
    };

    const renderLocalResults = (input) => {
      if (!input) return;
      const panel = searchPanelForInput(input);
      const box = localResultsBox(panel);
      if (!box) return;
      const query = input.value.trim().toLowerCase();
      if (query.length < 2) {
        box.classList.remove('show');
        box.innerHTML = '';
        return;
      }
      const matches = [];
      for (const item of localSearchIndexFor(panel)) {
        if (item.haystack.includes(query)) {
          matches.push(item);
          if (matches.length >= 80) break;
        }
      }
      box.classList.add('show');
      if (!matches.length) {
        box.innerHTML = '<div class="empty-state">No matches</div>';
        return;
      }
      box.innerHTML = matches.map((item) => {
        const snippet = escapeHtml(item.snippet || item.haystack).slice(0, 180);
        return `<button class="search-result local-search-result" type="button"
          data-message="${escapeHtml(item.id)}">
          <div>
            <div class="result-title">${escapeHtml(item.speaker)}</div>
            <div class="result-snippet">${snippet}</div>
          </div>
          <span class="result-time">${escapeHtml(item.time)}</span>
        </button>`;
      }).join('');
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
      renderLocalResults(localSearch);
      scheduleVirtualRender();
    };

    const activateMessagesTab = (panel) => {
      const button = panel.querySelector('.tab-button[data-tab="messages"]');
      if (button) activateTab(button);
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
      const linkedMessage = event.target.closest('[data-message-link]');
      if (linkedMessage) {
        event.preventDefault();
        activateMessagesTab(linkedMessage.closest('.chat-panel') || document);
        showMessage(linkedMessage.dataset.messageLink);
        return;
      }
      const localResult = event.target.closest('.local-search-result');
      if (localResult) {
        const panel = localResult.closest('.chat-panel') || document;
        activateMessagesTab(panel);
        closeLocalSearch(panel);
        showMessage(localResult.dataset.message);
        return;
      }
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
    localSearchInputs.forEach((input) => {
      input.addEventListener('input', () => renderLocalResults(input));
    });
    initVirtualMessages(activePanel());
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
    const rootScrollTop = () =>
      Math.max(
        window.scrollY,
        document.documentElement.scrollTop,
        document.body.scrollTop,
        chatArea ? chatArea.scrollTop : 0
      );
    const handleMobileWheel = (event) => {
      if (!isMobileLayout()) return;
      if (!event.target.closest('.chat-area')) return;
      if (event.target.closest('.local-search-results, .search-results')) return;
      const root = pageScrollRoot();
      const maxScroll = root.scrollHeight - root.clientHeight;
      if (maxScroll <= 0) return;
      const currentTop = scrollTopOf(root);
      const nextTop = Math.max(0, Math.min(maxScroll, currentTop + event.deltaY));
      if (nextTop === currentTop) return;
      event.preventDefault();
      setScrollTop(root, nextTop);
      toggleBack();
    };
    const toggleBack = () => {
      if (!back) return;
      if (rootScrollTop() > 360) {
        back.classList.add('show');
      } else {
        back.classList.remove('show');
      }
    };
    window.addEventListener('scroll', toggleBack);
    document.addEventListener('wheel', handleMobileWheel, { passive: false });
    window.addEventListener('scroll', scheduleVirtualRender);
    window.addEventListener('resize', scheduleVirtualRender);
    if (chatArea) {
      chatArea.addEventListener('scroll', toggleBack);
      chatArea.addEventListener('scroll', scheduleVirtualRender);
    }
    toggleBack();
    if (back) {
      back.addEventListener('click', scrollChatTop);
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
        ("saved", "Saved"),
        ("private", "Private"),
        ("group", "Groups"),
        ("channel", "Channels"),
        ("bot", "Bots"),
        ("unknown", "Deleted Accounts"),
    )


def _kind_label(kind: str) -> str:
    labels = {
        "saved": "Saved",
        "private": "Private",
        "group": "Group",
        "channel": "Channel",
        "bot": "Bot",
        "unknown": "Deleted Accounts",
    }
    return labels.get(kind, "Deleted Accounts")


def _is_saved_messages_title(title: str) -> bool:
    return title.strip().lower() in {"saved messages", "saved", "избранное"}


def _message_dom_id(group: ChatGroup, message_index: int) -> str:
    return f"{group.key}-msg-{message_index}"


def _message_search_text(
    msg: Message,
    speaker: str,
    peer_map: Optional[dict[int, str]] = None,
) -> str:
    parts = [speaker, msg.text, _forward_source_text(msg, peer_map)]
    if msg.is_pinned:
        parts.append("pinned")
    parts.extend(_attachment_search_text(item) for item in msg.attachments)
    return " ".join(part for part in parts if part).lower()


def _message_snippet(msg: Message) -> str:
    if msg.text:
        return " ".join(msg.text.split())[:180]
    if msg.attachments:
        return msg.attachments[0].title
    return "Message"


def _forward_source_text(
    msg: Message,
    peer_map: Optional[dict[int, str]],
) -> str:
    info = msg.forward_info or {}
    signature = info.get("signature")
    if signature:
        return str(signature)
    for key in ("src_msg_peer", "src_id", "author"):
        peer_id = info.get(key)
        if peer_id and peer_map and peer_id in peer_map:
            return peer_map[peer_id]
    for key in ("src_msg_peer", "src_id", "author"):
        peer_id = info.get(key)
        if peer_id:
            return f"peer {peer_id}"
    return ""


def _chat_search_text(group: ChatGroup) -> str:
    parts = [group.title, group.username, group.kind, _chat_preview(group)]
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


def _is_url_attachment(attachment: Attachment) -> bool:
    if attachment.kind == "webpage":
        return True
    reference = attachment.reference or ""
    return reference.startswith(("http://", "https://", "tg://"))


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
                    _forward_source_text(msg, peer_map),
                    "Pinned" if msg.is_pinned else "",
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
                    "username": group.username,
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
    if not attachment.copied_path and _is_downloadable_attachment(attachment):
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
    elif _is_downloadable_attachment(attachment):
        details.append("not found locally")
    else:
        details.append("message metadata")
    return " · ".join(details)


def _attachment_icon(attachment: Attachment) -> str:
    icons = {
        "photo": "IMG",
        "sticker": "STK",
        "gif": "GIF",
        "video": "VID",
        "audio": "AUD",
        "voice": "AUD",
        "file": "DOC",
        "location": "LOC",
        "webpage": "WEB",
        "poll": "POLL",
        "contact": "CON",
        "dice": "DICE",
        "service": "SVC",
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
    if attachment.kind == "sticker":
        file_name = (attachment.file_name or attachment.copied_path or "").lower()
        return mime.startswith("image/") or file_name.endswith(
            (".webp", ".png", ".jpg", ".jpeg", ".gif")
        )
    if attachment.kind == "gif":
        file_name = (attachment.file_name or attachment.copied_path or "").lower()
        return mime.startswith("image/") or file_name.endswith(".gif")
    return attachment.kind == "photo" or mime.startswith("image/")


def _attachment_file_name(attachment: Attachment) -> str:
    return (attachment.file_name or attachment.copied_path or attachment.title).lower()


def _is_sticker_attachment(attachment: Attachment) -> bool:
    mime = attachment.mime_type or ""
    file_name = _attachment_file_name(attachment)
    return (
        attachment.kind == "sticker"
        or "sticker" in file_name
        or mime in {"application/x-tgsticker", "application/x-tgs"}
    )


def _is_gif_attachment(attachment: Attachment) -> bool:
    file_name = _attachment_file_name(attachment)
    return attachment.kind == "gif" or file_name.endswith((".gif", ".gif.mp4"))


def _is_photo_attachment(attachment: Attachment) -> bool:
    return (
        _is_image_attachment(attachment)
        and not _is_sticker_attachment(attachment)
        and not _is_gif_attachment(attachment)
    )


def _is_video_attachment(attachment: Attachment) -> bool:
    mime = attachment.mime_type or ""
    return attachment.kind == "video" or mime.startswith("video/")


def _is_video_only_attachment(attachment: Attachment) -> bool:
    return _is_video_attachment(attachment) and not _is_gif_attachment(attachment)


def _is_audio_attachment(attachment: Attachment) -> bool:
    mime = attachment.mime_type or ""
    return attachment.kind in {"audio", "voice"} or mime.startswith("audio/")


def _is_media_attachment(attachment: Attachment) -> bool:
    return (
        attachment.kind == "location"
        or _is_sticker_attachment(attachment)
        or _is_gif_attachment(attachment)
        or _is_image_attachment(attachment)
        or _is_video_attachment(attachment)
        or _is_audio_attachment(attachment)
    )


def _is_downloadable_attachment(attachment: Attachment) -> bool:
    return attachment.kind not in {
        "contact",
        "dice",
        "location",
        "poll",
        "service",
        "webpage",
    }
