"""General utilities for parsing and formatting."""

from __future__ import annotations

import html
import re
from datetime import date, datetime, time

URL_RE = re.compile(r"(https?://[^\s<]+)")


def parse_timestamp(value: object) -> datetime | None:
    """Parse a unix timestamp (seconds or milliseconds) into datetime."""
    if value is None:
        return None
    try:
        ts = int(value)
    except (TypeError, ValueError):
        return None
    if ts <= 0:
        return None
    if ts > 10_000_000_000:
        ts = ts // 1000
    try:
        return datetime.fromtimestamp(ts)
    except (OverflowError, OSError, ValueError):
        return None


def parse_date_input(value: str | None, end: bool = False) -> int | None:
    """Convert a date string or timestamp to epoch seconds.

    Supports:
    - YYYY-MM-DD
    - YYYY-MM-DDTHH:MM:SS
    - Unix timestamps (seconds)
    """
    if not value:
        return None
    if value.isdigit():
        return int(value)

    has_time = "T" in value or " " in value
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        try:
            day = date.fromisoformat(value)
        except ValueError as exc:
            raise SystemExit(
                "Invalid date format. Use YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, "
                "or a Unix timestamp."
            ) from exc
        dt = datetime.combine(day, time.max if end else time.min)
        has_time = True

    if end and not has_time:
        dt = datetime.combine(dt.date(), time.max)
    if not end and not has_time:
        dt = datetime.combine(dt.date(), time.min)
    return int(dt.timestamp())


def split_trailing_punct(token: str) -> tuple[str, str]:
    """Split trailing punctuation from a token for clean linkification."""
    trailing = ""
    while token and token[-1] in '.,;:!?)"]':
        trailing = token[-1] + trailing
        token = token[:-1]
    return token, trailing


def linkify_markdown(text: str) -> str:
    """Wrap URLs in angle brackets for Markdown link detection."""

    def repl(match: re.Match[str]) -> str:
        url = match.group(1)
        core, trailing = split_trailing_punct(url)
        return f"<{core}>{trailing}"

    return URL_RE.sub(repl, text)


def linkify_html(text: str) -> str:
    """Convert URLs to anchor tags and preserve line breaks."""
    parts: list[str] = []
    last = 0
    for match in URL_RE.finditer(text):
        start, end = match.span(1)
        parts.append(html.escape(text[last:start]))
        url = match.group(1)
        core, trailing = split_trailing_punct(url)
        safe = html.escape(core, quote=True)
        parts.append(f'<a href="{safe}" target="_blank" rel="noopener">{safe}</a>')
        parts.append(html.escape(trailing))
        last = end
    parts.append(html.escape(text[last:]))
    return "".join(parts).replace("\n", "<br>")
